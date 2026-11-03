"""Reprice and validate the canonical weekly construction-material dataset."""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

import numpy as np
import pandas as pd

from inventory_app.levels import add_series_levels
from inventory_app.pricing import rebase_unit_prices, validate_rebased_prices

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "construction_materials_dehradun_dataset.csv"
BASE_COLUMNS = [
    "date", "project_site_id", "city", "state", "project_type", "project_phase",
    "material", "unit", "consumption_qty", "opening_stock_qty", "incoming_qty",
    "unit_price_inr", "supplier_lead_time_days", "wpi_reference_month",
]
DERIVED_COLUMNS = ["demand_level", "price_level"]
EXPECTED_COLUMNS = BASE_COLUMNS[:12] + DERIVED_COLUMNS + BASE_COLUMNS[12:]
PREVIOUS_DERIVED_ORDER = BASE_COLUMNS + DERIVED_COLUMNS
KEY_COLUMNS = ("date", "project_site_id", "material")
TOLERANCE = 1e-6


def _validate_frame(frame: pd.DataFrame) -> dict:
    if len(frame) != 8940:
        raise ValueError(f"Expected 8,940 rows, found {len(frame)}.")
    if frame.duplicated(subset=list(KEY_COLUMNS)).any():
        raise ValueError("Duplicate date/site/material keys found.")
    if frame.isna().any().any():
        raise ValueError("Missing values found after rebuilding the dataset.")
    numeric = ["consumption_qty", "opening_stock_qty", "incoming_qty", "unit_price_inr", "supplier_lead_time_days"]
    for column in numeric:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.astype(float)).all():
            raise ValueError(f"Nonnumeric or non-finite value in {column}.")
        if (values < 0).any():
            raise ValueError(f"Negative value in {column}.")
    if (pd.to_numeric(frame["supplier_lead_time_days"]) <= 0).any():
        raise ValueError("Supplier lead times must be positive.")
    if frame.groupby("material")["unit"].nunique().max() != 1:
        raise ValueError("A material is recorded with inconsistent units.")

    ordered = frame.copy()
    ordered["date"] = pd.to_datetime(ordered["date"], errors="raise")
    ordered = ordered.sort_values(["project_site_id", "material", "date"])
    closing = ordered["opening_stock_qty"].astype(float) + ordered["incoming_qty"].astype(float) - ordered["consumption_qty"].astype(float)
    if (closing < -TOLERANCE).any():
        raise ValueError("Calculated closing stock is negative.")
    expected_opening = closing.groupby([ordered["project_site_id"], ordered["material"]], sort=False).shift(1)
    actual_opening = ordered["opening_stock_qty"].astype(float)
    comparable = expected_opening.notna()
    stock_error_count = int(((actual_opening[comparable] - expected_opening[comparable]).abs() > TOLERANCE).sum())
    if stock_error_count:
        raise ValueError(f"Stock-chain validation found {stock_error_count} mismatch(es).")
    ranges = validate_rebased_prices(frame)
    if any(not details["within_plausible_range"] for details in ranges.values()):
        raise ValueError("One or more rebased prices fall outside configured plausible bounds.")
    return {
        "rows": len(frame),
        "sites": int(frame["project_site_id"].nunique()),
        "materials": int(frame["material"].nunique()),
        "series": int(frame.groupby(["project_site_id", "material"]).ngroups),
        "missing_values": int(frame.isna().sum().sum()),
        "duplicate_keys": int(frame.duplicated(subset=list(KEY_COLUMNS)).sum()),
        "stock_chain_pairs": int(comparable.sum()),
        "stock_chain_mismatches": stock_error_count,
        "negative_closing_balances": int((closing < -TOLERANCE).sum()),
        "price_ranges": ranges,
    }


def build(*, write: bool = True) -> tuple[str, dict]:
    with DATASET.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        input_columns = list(reader.fieldnames or [])
    if input_columns not in (BASE_COLUMNS, EXPECTED_COLUMNS, PREVIOUS_DERIVED_ORDER):
        raise ValueError(f"Dataset columns do not match the expected schema: {input_columns!r}")
    if not rows:
        raise ValueError("The canonical dataset is empty.")
    source = pd.DataFrame(rows)
    repriced = rebase_unit_prices(source)
    labeled = add_series_levels(repriced)
    output_rows = []
    for position, row in enumerate(rows):
        updated = {column: row.get(column, "") for column in BASE_COLUMNS}
        updated["unit_price_inr"] = f"{float(labeled.iloc[position]['unit_price_inr']):.4f}"
        updated["demand_level"] = str(labeled.iloc[position]["demand_level"])
        updated["price_level"] = str(labeled.iloc[position]["price_level"])
        output_rows.append(updated)
    result = pd.DataFrame(output_rows, columns=EXPECTED_COLUMNS)
    audit = _validate_frame(result)
    encoded_temp = DATASET.with_suffix(".csv.tmp")
    if write:
        with encoded_temp.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(output_rows)
        digest = hashlib.sha256(encoded_temp.read_bytes()).hexdigest()
        encoded_temp.replace(DATASET)
    else:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
        digest = hashlib.sha256(buffer.getvalue().encode("utf-8")).hexdigest()
    return digest, audit


if __name__ == "__main__":
    digest, result = build()
    print(
        f"Dataset ready: rows={result['rows']}, series={result['series']}, "
        f"stock_chain_mismatches={result['stock_chain_mismatches']}, "
        f"sha256={digest}"
    )
