"""Explicit, non-mixing policy for the construction dataset versus operational sales forecasts."""
from __future__ import annotations

from typing import Literal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.data_quality import history_to_frame
from inventory_app.models import Material, ProjectSite, SalesRecord

ForecastSource = Literal["auto", "historical_csv", "operational_sales"]
MIN_OPERATIONAL_SALES_PERIODS = {"weekly": 26, "monthly": 18}


class ForecastSourceError(ValueError):
    def __init__(self, message: str, *, observed_periods: int, required_periods: int, frequency: str):
        super().__init__(message)
        self.observed_periods = observed_periods
        self.required_periods = required_periods
        self.frequency = frequency


def operational_sales_history(session: Session) -> pd.DataFrame:
    """Return only posted sale quantities, never manual consumption or CSV observations."""
    rows = session.execute(
        select(SalesRecord, ProjectSite, Material)
        .join(ProjectSite, SalesRecord.site_id == ProjectSite.id)
        .join(Material, SalesRecord.material_id == Material.id)
        .where(SalesRecord.source_tag != "sample_ledger")
        .order_by(SalesRecord.sale_date, SalesRecord.id)
    ).all()
    return pd.DataFrame.from_records(
        [
            {
                "date": sale.sale_date,
                "project_site_id": site.identifier,
                "material": material.name,
                "consumption_qty": float(sale.quantity),
                "unit": sale.unit,
            }
            for sale, site, material in rows
        ],
        columns=["date", "project_site_id", "material", "consumption_qty", "unit"],
    )


def observed_sales_periods(frame: pd.DataFrame, *, site: str, material: str, frequency: str) -> int:
    if frequency not in MIN_OPERATIONAL_SALES_PERIODS or frame.empty:
        return 0
    subset = frame.loc[
        (frame["project_site_id"] == site) & (frame["material"] == material),
        ["date", "consumption_qty"],
    ].copy()
    if subset.empty:
        return 0
    subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
    subset["consumption_qty"] = pd.to_numeric(subset["consumption_qty"], errors="coerce")
    subset = subset.dropna(subset=["date", "consumption_qty"])
    subset = subset.loc[subset["consumption_qty"] >= 0]
    if subset.empty:
        return 0
    period_freq = "W-SUN" if frequency == "weekly" else "M"
    return int(subset["date"].dt.to_period(period_freq).nunique())


def source_eligibility(
    session: Session,
    *,
    site: str,
    material: str,
    frequency: str,
) -> dict[str, object]:
    sales = operational_sales_history(session)
    required = MIN_OPERATIONAL_SALES_PERIODS.get(frequency)
    observed = observed_sales_periods(sales, site=site, material=material, frequency=frequency)
    eligible = bool(required is not None and observed >= required)
    return {
        "frequency": frequency,
        "observed_operational_sales_periods": observed,
        "minimum_operational_sales_periods": required,
        "operational_sales_eligible": eligible,
        "source_label_if_auto": "Operational sales" if eligible else "Construction Materials Dehradun Dataset",
        "source_kind_if_auto": "operational_sales" if eligible else "historical_csv",
        "note": (
            f"Operational sales has {observed} observed {frequency} periods; at least {required} are required."
            if required is not None
            else "Select weekly or monthly frequency to check operational-sales eligibility."
        ),
    }


def resolve_forecast_source(
    session: Session,
    *,
    site: str,
    material: str,
    frequency: str,
    requested_source: ForecastSource = "auto",
) -> tuple[pd.DataFrame, str, str, dict[str, object]]:
    """Choose exactly one source. Auto uses sales only after the explicit history gate."""
    eligibility = source_eligibility(session, site=site, material=material, frequency=frequency)
    eligible = bool(eligibility["operational_sales_eligible"])
    if requested_source == "auto":
        resolved = "operational_sales" if eligible else "historical_csv"
    elif requested_source == "operational_sales":
        if not eligible:
            raise ForecastSourceError(
                "Operational sales cannot be selected until the series has at least "
                f"{eligibility['minimum_operational_sales_periods']} observed {frequency} periods "
                f"with recorded sales (currently {eligibility['observed_operational_sales_periods']}).",
                observed_periods=int(eligibility["observed_operational_sales_periods"]),
                required_periods=int(eligibility["minimum_operational_sales_periods"] or 0),
                frequency=frequency,
            )
        resolved = "operational_sales"
    else:
        resolved = "historical_csv"

    if resolved == "operational_sales":
        frame = operational_sales_history(session)
        label = "Operational sales"
        reason = (
            f"Uses operational sale quantities only: {eligibility['observed_operational_sales_periods']} "
            f"observed {frequency} periods meets the minimum of {eligibility['minimum_operational_sales_periods']}. "
            "Historical observations are excluded from this calculation."
        )
    else:
        frame = history_to_frame(session)
        label = "Construction Materials Dehradun Dataset"
        if requested_source == "auto" and not eligible:
            reason = (
                f"Operational sales is not eligible yet: {eligibility['observed_operational_sales_periods']} "
                f"observed {frequency} periods; {eligibility['minimum_operational_sales_periods']} are required. "
                "The evaluation uses historical observations until enough operational sales periods are available."
            )
        else:
            reason = "The evaluation uses historical observations."
    return frame, resolved, label, {**eligibility, "source_reason": reason}
