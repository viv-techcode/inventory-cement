"""Documented inventory-policy assumptions used by risk and simulation code."""
from __future__ import annotations

DEFAULT_SERVICE_LEVEL = 0.95
DEFAULT_HOLDING_RATE = 0.20
HOLDING_RATE_SENSITIVITY = (0.15, 0.20, 0.30)
DEFAULT_SHORTAGE_COST_MULTIPLE = 2.0
SHORTAGE_COST_SENSITIVITY = (1.5, 2.0, 3.0)
MAX_COVER_DAYS = 90.0
DEFAULT_REVIEW_PERIOD_WEEKS = 1.0

ORDER_COST_BY_MATERIAL_CLASS = {
    "cement": 500.0,
    "steel": 1500.0,
    "bulk": 1200.0,
    "masonry": 700.0,
    "finishes": 500.0,
    "general": 750.0,
}

MATERIAL_CLASSES = {
    "AAC Blocks": "masonry",
    "Binding Wire": "steel",
    "Bricks": "masonry",
    "Cement": "cement",
    "Coarse Aggregate": "bulk",
    "PVC Pipes": "general",
    "Ready-Mix Concrete": "bulk",
    "River Sand": "bulk",
    "TMT Steel": "steel",
    "Tiles": "finishes",
}

# Pack rounding is in the dataset's material unit, not package mass/volume.
ORDER_PACK_SIZES = {
    "AAC Blocks": 100.0,
    "Binding Wire": 25.0,
    "Bricks": 500.0,
    "Cement": 50.0,
    "Coarse Aggregate": 1.0,
    "PVC Pipes": 10.0,
    "Ready-Mix Concrete": 1.0,
    "River Sand": 1.0,
    "TMT Steel": 100.0,
    "Tiles": 1.0,
}
