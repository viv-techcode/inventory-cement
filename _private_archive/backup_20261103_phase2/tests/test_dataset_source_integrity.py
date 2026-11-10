from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "construction_materials_dehradun_dataset.csv"
EXPECTED_COLUMNS = [
    "date", "project_site_id", "city", "state", "project_type", "project_phase",
    "material", "unit", "consumption_qty", "opening_stock_qty", "incoming_qty",
    "unit_price_inr", "supplier_lead_time_days", "wpi_reference_month",
]

def test_dataset_integrity_coverage_and_stock_chain():
    frame = pd.read_csv(SOURCE)
    assert frame.shape == (8940, 14)
    assert frame.columns.tolist() == EXPECTED_COLUMNS
    assert frame.groupby(["project_site_id", "material"]).size().eq(149).all()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    assert frame["date"].min().date().isoformat() == "2024-01-01"
    assert frame["date"].max().date().isoformat() == "2026-11-02"
    assert frame[["project_site_id", "material", "date"]].duplicated().sum() == 0
    residuals = []
    for _, group in frame.groupby(["project_site_id", "material"]):
        group = group.sort_values("date")
        assert group["date"].dt.normalize().diff().dropna().dt.days.eq(7).all()
        close = group["opening_stock_qty"] + group["incoming_qty"] - group["consumption_qty"]
        residuals.extend((close.iloc[:-1].to_numpy() - group["opening_stock_qty"].iloc[1:].to_numpy()).tolist())
        assert np.all(close.to_numpy() >= 0)
    assert max(abs(value) for value in residuals) <= 1e-6

def test_dataset_hash_and_rebuild_are_deterministic():
    from scripts.build_dataset import build
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert build() == before
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == before
