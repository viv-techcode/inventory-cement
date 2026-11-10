"""Validate and reproducibly rewrite the canonical construction-material dataset."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "construction_materials_dehradun_dataset.csv"
EXPECTED_COLUMNS = [
    "date", "project_site_id", "city", "state", "project_type", "project_phase",
    "material", "unit", "consumption_qty", "opening_stock_qty", "incoming_qty",
    "unit_price_inr", "supplier_lead_time_days", "wpi_reference_month",
]
KEY_COLUMNS = ("date", "project_site_id", "material")

def build() -> str:
    with DATASET.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or list(rows[0]) != EXPECTED_COLUMNS:
        raise ValueError("Dataset columns do not match the documented schema.")
    if len(rows) != 8940:
        raise ValueError(f"Expected 8,940 rows, found {len(rows)}.")
    keys = [tuple(row[name] for name in KEY_COLUMNS) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate date/site/material keys found.")
    temporary = DATASET.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(DATASET)
    return hashlib.sha256(DATASET.read_bytes()).hexdigest()

if __name__ == "__main__":
    print(f"Dataset ready: rows=8940, series=60, sha256={build()}")
