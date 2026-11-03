"""Deterministic re-basing of teaching prices to November 2026 levels."""
from __future__ import annotations

import hashlib
from datetime import date

import numpy as np
import pandas as pd

from inventory_app.price_config import (
    ANCHOR_DATE,
    ANNUAL_INFLATION,
    BASE_FACTOR,
    HEAVY_MATERIALS,
    MATERIAL_REFERENCES,
    MONSOON_FACTOR,
    MONSOON_MONTHS,
    NOVEMBER_ADJUSTMENT,
    NOISE_LIMIT,
    PEAK_FACTOR,
    PEAK_MONTHS,
    SEED,
    SITE_FACTORS,
)


def _season_factor(month: int) -> float:
    if month in MONSOON_MONTHS:
        return MONSOON_FACTOR
    if month in PEAK_MONTHS:
        return PEAK_FACTOR
    return BASE_FACTOR


def _noise(site: str, material: str, day: date) -> float:
    token = f"{SEED}|{site}|{material}|{day.isoformat()}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
    uniform = integer / (2**64 - 1)
    return 1.0 + NOISE_LIMIT * (2.0 * uniform - 1.0)


def reference_unit_price(material: str, site: str) -> float:
    """Return the adjusted November anchor in the dataset's unit."""
    if material not in MATERIAL_REFERENCES:
        raise ValueError(f"No November 2026 price reference is configured for {material!r}.")
    reference = MATERIAL_REFERENCES[material]
    category = reference["category"]
    anchor = float(reference["anchor"])
    adjustment = NOVEMBER_ADJUSTMENT[category]
    anchor = anchor + float(adjustment["value"]) if adjustment["kind"] == "add" else anchor * float(adjustment["value"])
    anchor *= float(reference["conversion"])
    site_factor = float(SITE_FACTORS.get(site, 1.0))
    if material in HEAVY_MATERIALS:
        anchor *= site_factor
    return anchor


def rebase_unit_prices(frame: pd.DataFrame) -> pd.DataFrame:
    """Rebase only unit prices, preserving every non-price measurement cell."""
    required = {"date", "project_site_id", "material", "unit_price_inr"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Cannot rebase prices; missing fields: {', '.join(sorted(missing))}.")
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    anchor_date = pd.Timestamp(ANCHOR_DATE).date()
    for (site, material), group in result.groupby(["project_site_id", "material"], sort=False):
        reference = MATERIAL_REFERENCES.get(str(material))
        if reference is None:
            raise ValueError(f"No price reference is configured for material {material!r}.")
        latest = group["date"].max().date()
        latest_factor = _season_factor(latest.month) * _noise(str(site), str(material), latest)
        target = reference_unit_price(str(material), str(site))
        year_rate = float(ANNUAL_INFLATION[reference["category"]])
        indices = group.index
        prices = []
        for timestamp in group["date"]:
            observation_day = timestamp.date()
            drift = (1.0 + year_rate) ** ((observation_day - anchor_date).days / 365.25)
            seasonal_noise = _season_factor(observation_day.month) * _noise(str(site), str(material), observation_day)
            prices.append(target * drift * seasonal_noise / latest_factor)
        result.loc[indices, "unit_price_inr"] = np.round(prices, 4)
    if not np.isfinite(pd.to_numeric(result["unit_price_inr"], errors="coerce")).all():
        raise ValueError("Price rebasing produced a non-finite value.")
    if (result["unit_price_inr"] <= 0).any():
        raise ValueError("Price rebasing produced a non-positive value.")
    return result


def validate_rebased_prices(frame: pd.DataFrame) -> dict[str, dict[str, float | bool]]:
    """Check values against a broad ±15% historical envelope around anchors."""
    results: dict[str, dict[str, float | bool]] = {}
    for material, group in frame.groupby("material", sort=True):
        material_sites = group["project_site_id"].drop_duplicates().tolist()
        targets = [reference_unit_price(str(material), str(site)) for site in material_sites]
        low, high = min(targets) * 0.82, max(targets) * 1.18
        values = pd.to_numeric(group["unit_price_inr"], errors="coerce")
        results[str(material)] = {
            "min": float(values.min()),
            "max": float(values.max()),
            "plausible_min": low,
            "plausible_max": high,
            "within_plausible_range": bool(values.between(low, high).all()),
        }
    return results
