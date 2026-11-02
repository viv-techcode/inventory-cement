"""Transparent dataset diagnostics; all summaries are derived from actual records."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.models import HistoricalObservation

HISTORY_COLUMNS = [
    "date",
    "project_site_id",
    "city",
    "state",
    "project_type",
    "project_phase",
    "material",
    "unit",
    "consumption_qty",
    "opening_stock_qty",
    "incoming_qty",
    "unit_price_inr",
    "supplier_lead_time_days",
    "wpi_reference_month",
]


def history_to_frame(session: Session) -> pd.DataFrame:
    """Read imported historical observations as an analysis DataFrame."""
    rows = session.scalars(
        select(HistoricalObservation).order_by(HistoricalObservation.observation_datetime)
    ).all()
    records = []
    for row in rows:
        records.append(
            {
                "date": row.observation_datetime,
                "project_site_id": row.project_site_id,
                "city": row.city,
                "state": row.state,
                "project_type": row.project_type,
                "project_phase": row.project_phase,
                "material": row.material,
                "unit": row.unit,
                "consumption_qty": float(row.consumption_qty),
                "opening_stock_qty": float(row.opening_stock_qty),
                "incoming_qty": float(row.incoming_qty),
                "unit_price_inr": float(row.unit_price_inr),
                "supplier_lead_time_days": int(row.supplier_lead_time_days),
                "wpi_reference_month": row.wpi_reference_month,
                "source_tag": row.source_tag,
                "source_row_number": row.source_row_number,
                "import_id": row.import_id,
            }
        )
    frame = pd.DataFrame.from_records(records)
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date").reset_index(drop=True)
    return frame


def build_data_quality_report(frame: pd.DataFrame, *, as_of: date | None = None) -> dict[str, Any]:
    """Summarize quality and infer row cadence/stock-flow consistency conservatively."""
    current_day = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    if frame.empty:
        return {
            "row_count": 0,
            "column_count": len(HISTORY_COLUMNS),
            "date_min": None,
            "date_max": None,
            "site_count": 0,
            "material_count": 0,
            "series_count": 0,
            "source_tag_distribution": {},
            "warnings": ["No historical observations are loaded."],
            "missing_by_column": {name: 0 for name in HISTORY_COLUMNS},
        }

    missing = {name: int(frame[name].isna().sum()) if name in frame else len(frame) for name in HISTORY_COLUMNS}
    dates = pd.to_datetime(frame["date"], errors="coerce")
    numeric = ["consumption_qty", "opening_stock_qty", "incoming_qty", "unit_price_inr", "supplier_lead_time_days"]
    ranges: dict[str, dict[str, float | int | None]] = {}
    for col in numeric:
        values = pd.to_numeric(frame[col], errors="coerce")
        ranges[col] = {
            "min": float(values.min()) if values.notna().any() else None,
            "max": float(values.max()) if values.notna().any() else None,
            "invalid_or_missing": int((~np.isfinite(values.fillna(np.nan))).sum()),
            "negative": int((values < 0).sum()),
        }

    group_cols = ["project_site_id", "material"]
    ordered = frame.sort_values(group_cols + ["date"]).copy()
    grouped = ordered.groupby(group_cols, dropna=False, sort=False)
    intervals = grouped["date"].diff().dt.total_seconds().div(86400)
    observed_intervals = intervals.dropna()
    gaps = observed_intervals[observed_intervals > 10]
    short_gaps = observed_intervals[observed_intervals < 3]

    previous_opening = grouped["opening_stock_qty"].shift(1)
    previous_incoming = grouped["incoming_qty"].shift(1)
    previous_consumption = grouped["consumption_qty"].shift(1)
    previous_date = grouped["date"].shift(1)
    days_between = (ordered["date"] - previous_date).dt.total_seconds().div(86400)
    flow_error = ordered["opening_stock_qty"] - (previous_opening + previous_incoming - previous_consumption)
    comparable = flow_error.notna() & days_between.between(3, 10, inclusive="both")
    comparable_errors = flow_error[comparable].abs()
    within_tolerance = int((comparable_errors <= 0.01).sum())
    comparable_count = int(comparable_errors.count())
    flow_pct = (100.0 * within_tolerance / comparable_count) if comparable_count else None

    duplicate_exact = int(frame.duplicated(subset=[name for name in HISTORY_COLUMNS if name in frame]).sum())
    expected_wpi_month = dates.dt.strftime("%Y-%m")
    wpi_mismatch_count = int((frame["wpi_reference_month"].astype(str) != expected_wpi_month.astype(str)).sum())
    series_counts = frame.groupby(group_cols, dropna=False).size()
    unit_counts = frame.groupby(["material", "unit"], dropna=False).size().rename("records").reset_index()
    project_type_counts = frame["project_type"].value_counts(dropna=False).to_dict()
    phase_counts = frame["project_phase"].value_counts(dropna=False).to_dict()

    warnings: list[str] = []
    if any(missing.values()):
        warnings.append("One or more source columns contain missing values; affected rows require review.")
    if duplicate_exact:
        warnings.append(f"{duplicate_exact:,} exact duplicate source row(s) are present in the loaded history.")
    if len(gaps):
        warnings.append(f"{len(gaps):,} inter-observation interval(s) exceed 10 days; missing observations are not treated as zero consumption.")
    if comparable_count and flow_pct is not None and flow_pct < 95:
        warnings.append("Opening-stock roll-forward checks do not consistently match prior opening + incoming − consumption; historical stock snapshots should be treated cautiously.")
    if comparable_count and flow_pct >= 95:
        warnings.append("Historical stock-flow values are internally consistent for comparable adjacent observations.")
    if wpi_mismatch_count:
        warnings.append(f"{wpi_mismatch_count:,} wpi_reference_month value(s) do not match the observation calendar month and need review.")
    warnings.append("wpi_reference_month is only a month key; no WPI index value is present in this dataset.")
    warnings.append("The source contains no supplier identities or delivery schedules; source lead times are planning estimates, not supplier-confirmed commitments.")
    warnings.append("Historical unit prices are source observations/estimates, not audited procurement expenditure.")
    if dates.notna().any():
        age_days = (current_day - dates.max().date()).days
        if age_days > 7:
            warnings.append(f"The latest observation is {age_days} days old; current demand coverage is outside the seven-day freshness window.")

    median_interval = float(observed_intervals.median()) if len(observed_intervals) else None
    min_interval = float(observed_intervals.min()) if len(observed_intervals) else None
    max_interval = float(observed_intervals.max()) if len(observed_intervals) else None
    return {
        "row_count": int(len(frame)),
        "column_count": int(len([c for c in HISTORY_COLUMNS if c in frame.columns])),
        "date_min": dates.min().isoformat() if dates.notna().any() else None,
        "date_max": dates.max().isoformat() if dates.notna().any() else None,
        "site_count": int(frame["project_site_id"].nunique(dropna=True)),
        "material_count": int(frame["material"].nunique(dropna=True)),
        "project_type_count": int(frame["project_type"].nunique(dropna=True)),
        "phase_count": int(frame["project_phase"].nunique(dropna=True)),
        "series_count": int(len(series_counts)),
        "source_tag_distribution": {
            str(k): int(v) for k, v in frame.get("source_tag", pd.Series(dtype=str)).fillna("unknown").value_counts().items()
        },
        "series_observations_min": int(series_counts.min()) if len(series_counts) else 0,
        "series_observations_max": int(series_counts.max()) if len(series_counts) else 0,
        "missing_by_column": missing,
        "numeric_ranges": ranges,
        "duplicate_exact_rows": duplicate_exact,
        "wpi_reference_month_mismatches": wpi_mismatch_count,
        "unit_distribution": {str(k): int(v) for k, v in frame["unit"].value_counts(dropna=False).items()},
        "material_units": unit_counts.to_dict(orient="records"),
        "project_type_counts": {str(k): int(v) for k, v in project_type_counts.items()},
        "phase_counts": {str(k): int(v) for k, v in phase_counts.items()},
        "median_observation_interval_days": median_interval,
        "minimum_observation_interval_days": min_interval,
        "maximum_observation_interval_days": max_interval,
        "intervals_over_10_days": int(len(gaps)),
        "intervals_under_3_days": int(len(short_gaps)),
        "stock_rollforward_comparable_pairs": comparable_count,
        "stock_rollforward_pairs_within_0_01": within_tolerance,
        "stock_rollforward_consistency_pct": flow_pct,
        "warnings": warnings,
    }
