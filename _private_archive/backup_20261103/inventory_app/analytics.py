"""Unit-aware historical and operational consumption analytics."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

import numpy as np
import pandas as pd


def filter_history(
    frame: pd.DataFrame,
    *,
    start_date=None,
    end_date=None,
    sites: Iterable[str] | None = None,
    materials: Iterable[str] | None = None,
    project_types: Iterable[str] | None = None,
    phases: Iterable[str] | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    if start_date is not None:
        result = result.loc[result["date"].dt.date >= start_date]
    if end_date is not None:
        result = result.loc[result["date"].dt.date <= end_date]
    for column, selected in (
        ("project_site_id", sites),
        ("material", materials),
        ("project_type", project_types),
        ("project_phase", phases),
    ):
        if selected is not None:
            choices = set(selected)
            result = result.loc[result[column].isin(choices)] if choices else result.iloc[0:0]
    return result.sort_values("date").reset_index(drop=True)


def aggregate_consumption(frame: pd.DataFrame, frequency: str = "Weekly") -> pd.DataFrame:
    """Aggregate observations by period and compatible site/material/unit groups."""
    if frame.empty:
        return pd.DataFrame(columns=["period", "project_site_id", "material", "unit", "consumption_qty", "records"])
    frequency_map = {"Daily": "D", "Weekly": "W-SUN", "Monthly": "MS"}
    if frequency not in frequency_map:
        raise ValueError("Frequency must be Daily, Weekly or Monthly.")
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result = result.dropna(subset=["date"])
    if frequency == "Daily":
        result["period"] = result["date"].dt.floor("D")
    elif frequency == "Weekly":
        result["period"] = result["date"].dt.to_period("W-SUN").dt.start_time
    else:
        result["period"] = result["date"].dt.to_period("M").dt.start_time
    return (
        result.groupby(["period", "project_site_id", "material", "unit"], as_index=False, dropna=False)
        .agg(consumption_qty=("consumption_qty", "sum"), records=("consumption_qty", "size"))
        .sort_values(["period", "project_site_id", "material"])
        .reset_index(drop=True)
    )


def add_rolling_average(frame: pd.DataFrame, windows: int = 4) -> pd.DataFrame:
    """Add a trailing observation average; no centered/future window is used."""
    if frame.empty:
        output = frame.copy()
        output["rolling_mean"] = pd.Series(dtype=float)
        return output
    result = frame.copy().sort_values(["project_site_id", "material", "date"])
    result["rolling_mean"] = result.groupby(["project_site_id", "material"], dropna=False)["consumption_qty"].transform(
        lambda values: values.rolling(window=windows, min_periods=1).mean()
    )
    return result


def material_usage(frame: pd.DataFrame) -> pd.DataFrame:
    """Group totals by material and unit; never sum incompatible physical units."""
    if frame.empty:
        return pd.DataFrame(columns=["material", "unit", "consumption_qty", "records"])
    return (
        frame.groupby(["material", "unit"], as_index=False, dropna=False)
        .agg(consumption_qty=("consumption_qty", "sum"), records=("consumption_qty", "size"))
        .sort_values("consumption_qty", ascending=False)
        .reset_index(drop=True)
    )


def site_material_usage(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["project_site_id", "material", "unit", "consumption_qty", "records"])
    return (
        frame.groupby(["project_site_id", "material", "unit"], as_index=False, dropna=False)
        .agg(consumption_qty=("consumption_qty", "sum"), records=("consumption_qty", "size"))
        .sort_values("consumption_qty", ascending=False)
        .reset_index(drop=True)
    )


def historical_stock_snapshots(frame: pd.DataFrame) -> pd.DataFrame:
    """Latest source observation per site/material as a dated, explicitly historical estimate."""
    if frame.empty:
        return pd.DataFrame(columns=["site", "material", "unit", "snapshot_date", "opening_stock", "incoming", "consumption", "estimated_closing_stock"])
    ordered = frame.copy()
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce")
    ordered = ordered.dropna(subset=["date"]).sort_values("date")
    latest = ordered.groupby(["project_site_id", "material"], as_index=False, sort=False).tail(1).copy()
    latest["estimated_closing_stock"] = latest["opening_stock_qty"] + latest["incoming_qty"] - latest["consumption_qty"]
    return latest.rename(
        columns={
            "project_site_id": "site",
            "date": "snapshot_date",
            "unit": "unit",
            "opening_stock_qty": "opening_stock",
            "incoming_qty": "incoming",
            "consumption_qty": "consumption",
        }
    )[["site", "material", "unit", "snapshot_date", "opening_stock", "incoming", "consumption", "estimated_closing_stock"]].reset_index(drop=True)


def volatility_by_material(frame: pd.DataFrame) -> pd.DataFrame:
    """Coefficient of variation over observed consumption; values with zero mean are undefined."""
    if frame.empty:
        return pd.DataFrame(columns=["material", "unit", "mean", "std", "cv_pct", "observations"])
    grouped = frame.groupby(["material", "unit"], as_index=False)["consumption_qty"].agg(["mean", "std", "count"]).reset_index()
    grouped["cv_pct"] = np.where(grouped["mean"].abs() > 1e-12, grouped["std"] / grouped["mean"].abs() * 100, np.nan)
    return grouped.rename(columns={"count": "observations"}).sort_values("cv_pct", ascending=False, na_position="last")
