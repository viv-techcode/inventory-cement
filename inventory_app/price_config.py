"""Reproducible November 2026 indicative price assumptions.

Reference values are Dehradun dealer-to-retail midpoints; conversions and site
factors are explicit scenario assumptions, not supplier quotations.
"""
from __future__ import annotations

SEED = 20261103
ANCHOR_DATE = "2026-11-02"
MONSOON_MONTHS = {6, 7, 8, 9}
PEAK_MONTHS = {10, 11, 12, 1, 2, 3}
MONSOON_FACTOR = 0.99
PEAK_FACTOR = 1.01
BASE_FACTOR = 1.0
NOISE_LIMIT = 0.004
LEVEL_MIN_HISTORY = 12

# Dataset material → August anchor, source range, category, unit conversion.
MATERIAL_REFERENCES = {
    "AAC Blocks": {"anchor": 82.0, "range": (63.0, 100.0), "category": "blocks", "conversion": 1.0, "basis": "piece (600x200x200 mm)"},
    "Binding Wire": {"anchor": 62.0, "range": (58.0, 65.0), "category": "steel", "conversion": 1.0, "basis": "kg"},
    "Bricks": {"anchor": 9.0, "range": (7.0, 10.0), "category": "blocks", "conversion": 1.0, "basis": "red-clay brick, piece"},
    "Cement": {"anchor": 428.0, "range": (407.0, 449.0), "category": "cement", "conversion": 1.0, "basis": "OPC 43, 50-kg bag"},
    "Coarse Aggregate": {"anchor": 1289.0, "range": (1000.0, 1578.0), "category": "bulk", "conversion": 1.5, "basis": "20-mm aggregate, per tonne × 1.5 t/m³"},
    "PVC Pipes": {"anchor": 348.0, "range": (300.0, 400.0), "category": "finishes", "conversion": 3.0, "basis": "4-in PVC SWR, per metre × 3-m piece"},
    "Ready-Mix Concrete": {"anchor": 5211.0, "range": (4632.0, 5789.0), "category": "bulk", "conversion": 1.0, "basis": "M20, m³"},
    "River Sand": {"anchor": 2478.0, "range": (2124.0, 2832.0), "category": "bulk", "conversion": 1.6, "basis": "river sand, per tonne × 1.6 t/m³"},
    "TMT Steel": {"anchor": 63.0, "range": (60.0, 66.0), "category": "steel", "conversion": 1.0, "basis": "12-mm Fe500D, kg"},
    "Tiles": {"anchor": 87.0, "range": (62.0, 112.0), "category": "finishes", "conversion": 10.7639104167, "basis": "vitrified 2×2 tile per sqft × 10.7639104167 sqft/m²"},
}

# Indicative year-on-year drift used only to construct earlier scenario prices.
ANNUAL_INFLATION = {
    "cement": 0.05,
    "steel": 0.04,
    "bulk": 0.035,
    "blocks": 0.03,
    "finishes": 0.03,
}

# November versus August 2026. Cement uses the brief's central +₹15/bag.
NOVEMBER_ADJUSTMENT = {
    "cement": {"kind": "add", "value": 15.0},
    "steel": {"kind": "multiply", "value": 1.04},
    "bulk": {"kind": "multiply", "value": 1.015},
    "blocks": {"kind": "multiply", "value": 1.01},
    "finishes": {"kind": "multiply", "value": 1.01},
}

HEAVY_MATERIALS = {"AAC Blocks", "Bricks", "Cement", "Coarse Aggregate", "Ready-Mix Concrete", "River Sand", "TMT Steel"}
DEFAULT_SITE_FACTOR = 1.0
SITE_FACTORS = {
    "Clement Town, Dehradun": 1.0,
    "GMS Road, Dehradun": 1.0,
    "ISBT Transport Nagar, Dehradun": 1.0,
    "ISBT�Transport Nagar, Dehradun": 1.0,
    "Jakhan, Dehradun": 1.0,
    "Paltan Bazaar, Dehradun": 1.0,
    "Sahastradhara Road, Dehradun": 1.06,
}
