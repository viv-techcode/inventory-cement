"""Single expanding-window definition for demand and price level labels."""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

LEVELS = ("Low", "Medium", "High")


def expanding_level_labels(values: Iterable[float], *, min_history: int = 12) -> list[str]:
    """Classify each value against that series' past-only 33rd/67th percentiles.

    Until ``min_history`` prior finite values are available, the label is Medium.
    Threshold ties remain Medium. The current observation is never used to set
    its own thresholds.
    """
    if min_history < 1:
        raise ValueError("min_history must be positive")
    numeric = np.asarray(list(values), dtype=float)
    output: list[str] = []
    history: list[float] = []
    for value in numeric:
        if not np.isfinite(value):
            output.append("Medium")
            continue
        if len(history) < min_history:
            output.append("Medium")
        else:
            low, high = np.quantile(history, [1 / 3, 2 / 3])
            output.append("Low" if value < low else "High" if value > high else "Medium")
        history.append(float(value))
    return output


def add_series_levels(frame):
    """Return a copy with demand_level and price_level computed by series."""
    result = frame.copy()
    if result.empty:
        result["demand_level"] = []
        result["price_level"] = []
        return result
    required = {"project_site_id", "material", "date", "consumption_qty", "unit_price_inr"}
    missing = required - set(result.columns)
    if missing:
        raise ValueError(f"Cannot classify levels; missing fields: {', '.join(sorted(missing))}.")
    result["demand_level"] = "Medium"
    result["price_level"] = "Medium"
    result["_level_position"] = range(len(result))
    for _, group in result.sort_values(["project_site_id", "material", "date"]).groupby(
        ["project_site_id", "material"], sort=False, dropna=False
    ):
        indices = group.index
        result.loc[indices, "demand_level"] = expanding_level_labels(group["consumption_qty"])
        result.loc[indices, "price_level"] = expanding_level_labels(group["unit_price_inr"])
    return result.drop(columns=["_level_position"])
