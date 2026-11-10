"""Deterministically rebuild the unified Dehradun construction-material dataset."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "archive" / "pre_merge"
ORIGINAL = ARCHIVE / "Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv"
EXTENSION = ARCHIVE / "Dehradun_Inventory_Dataset_Sample_Extension.csv"
OUTPUT = ROOT / "data" / "construction_materials_dehradun_dataset.csv"
SOURCE_COLUMNS = [
    "date", "project_site_id", "city", "state", "project_type", "project_phase",
    "material", "unit", "consumption_qty", "opening_stock_qty", "incoming_qty",
    "unit_price_inr", "supplier_lead_time_days", "wpi_reference_month",
]
KEY = ["project_site_id", "material", "date"]
EXPECTED_HASHES = {
    "Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv": "828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c",
    "Dehradun_Inventory_Dataset_Sample_Extension.csv": "e9c25f5b7d9538b6d47bc3297c76886884cce686b4a614492daa20f9c5347d3a",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild() -> pd.DataFrame:
    for source in (ORIGINAL, EXTENSION):
        actual = _sha256(source)
        if actual != EXPECTED_HASHES[source.name]:
            raise ValueError(f"Archived input hash changed for {source.name}: {actual}")
    original = pd.read_csv(ORIGINAL)
    extension = pd.read_csv(EXTENSION)
    if list(original.columns) != SOURCE_COLUMNS:
        raise ValueError("Archived original schema or column order changed.")
    if list(extension.columns) != [*SOURCE_COLUMNS, "source_tag"]:
        raise ValueError("Archived extension schema or column order changed.")
    if len(original) != 6300 or len(extension) != 2640:
        raise ValueError(f"Expected 6,300 + 2,640 source rows, found {len(original)} + {len(extension)}.")
    if extension["source_tag"].astype(str).ne("sample_extension").any():
        raise ValueError("Archived extension has unexpected source tags.")
    original_out = original.copy()
    original_out["data_origin"] = "original_self_created"
    extension_out = extension.loc[:, SOURCE_COLUMNS].copy()
    extension_out["data_origin"] = "generated_extension"
    merged = pd.concat([original_out, extension_out], ignore_index=True)
    merged["_sort_date"] = pd.to_datetime(merged["date"], errors="raise")
    merged = merged.sort_values(["project_site_id", "material", "_sort_date"], kind="stable")
    merged = merged.drop(columns="_sort_date").reset_index(drop=True)
    if len(merged) != 8940 or merged["data_origin"].value_counts().to_dict() != {
        "original_self_created": 6300, "generated_extension": 2640
    }:
        raise ValueError("Merged row count or origin counts do not match the audited totals.")
    if merged.duplicated(KEY).any():
        raise ValueError("Merged dataset contains duplicate site/material/date keys.")
    if len(merged.groupby(["project_site_id", "material"], dropna=False)) != 60:
        raise ValueError("Expected exactly 60 site/material series.")
    for (site, material), group in merged.groupby(["project_site_id", "material"], sort=False):
        group = group.sort_values("date")
        if len(group) != 149:
            raise ValueError(f"Expected 149 rows for {site} / {material}, found {len(group)}.")
        calendar_steps = pd.to_datetime(group["date"], errors="raise").dt.normalize().diff().dropna().dt.days
        if not calendar_steps.eq(7).all():
            raise ValueError(f"Calendar dates are not weekly for {site} / {material}.")
        if group["unit"].nunique() != 1:
            raise ValueError(f"Unit changes within {site} / {material}.")
    if merged.groupby("material")["unit"].nunique().gt(1).any():
        raise ValueError("A material is recorded with inconsistent units across sites.")
    numeric = merged[["consumption_qty", "opening_stock_qty", "incoming_qty", "unit_price_inr", "supplier_lead_time_days"]].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or (numeric[["consumption_qty", "opening_stock_qty", "incoming_qty"]] < 0).any().any():
        raise ValueError("Missing/non-numeric or negative quantity fields found.")
    if (numeric["consumption_qty"] <= 0).any() or (numeric["unit_price_inr"] <= 0).any() or (numeric["supplier_lead_time_days"] <= 0).any():
        raise ValueError("Zero consumption, nonpositive price, or nonpositive lead time found.")
    closing = numeric["opening_stock_qty"] + numeric["incoming_qty"] - numeric["consumption_qty"]
    if (closing < -1e-6).any():
        raise ValueError("Negative calculated closing stock found.")
    ordered = merged.assign(_closing=closing).sort_values(KEY, kind="stable")
    previous_close = ordered.groupby(["project_site_id", "material"], sort=False)["_closing"].shift()
    chain_error = (ordered["opening_stock_qty"].reset_index(drop=True) - previous_close.reset_index(drop=True)).abs()
    if chain_error.dropna().gt(1e-6).any():
        raise ValueError("Adjacent stock chain exceeds tolerance 1e-6.")
    # The final 30 observations are the evaluation holdout for each 149-row series.
    holdout = merged.sort_values(KEY, kind="stable").groupby(["project_site_id", "material"], sort=False).tail(30)
    if len(holdout) != 1800 or not holdout["data_origin"].eq("generated_extension").all():
        raise ValueError("Expected all 1,800 rows in the final 30-week holdout to be generated.")
    # Compare every original measurement value after key sorting; only provenance is added.
    actual_original = merged.loc[merged.data_origin.eq("original_self_created"), SOURCE_COLUMNS].reset_index(drop=True)
    expected_original = original.sort_values(KEY, kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual_original, expected_original, check_dtype=False, check_exact=True)
    actual_extension = merged.loc[merged.data_origin.eq("generated_extension"), SOURCE_COLUMNS].reset_index(drop=True)
    expected_extension = extension.loc[:, SOURCE_COLUMNS].sort_values(KEY, kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual_extension, expected_extension, check_dtype=False, check_exact=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".csv.tmp")
    merged.to_csv(temporary, index=False, lineterminator="\n")
    temporary.replace(OUTPUT)
    reread = pd.read_csv(OUTPUT)
    if len(reread) != 8940 or reread.duplicated(KEY).any():
        raise ValueError("Written merged file failed row-count/key verification.")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: rows={len(reread)}, original=6300, generated=2640, duplicate_keys=0")
    print(f"Archived original SHA-256: {_sha256(ORIGINAL)}")
    return reread


if __name__ == "__main__":
    rebuild()
