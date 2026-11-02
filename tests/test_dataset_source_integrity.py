from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv"
BASELINE_SHA256 = "828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c"


def test_original_dataset_bytes_weekly_coverage_and_stock_chain():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASELINE_SHA256
    frame = pd.read_csv(SOURCE)
    assert frame.shape == (6300, 14)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    assert frame["date"].min().date().isoformat() == "2024-01-01"
    assert frame["date"].max().date().isoformat() == "2025-12-29"
    assert frame.groupby(["project_site_id", "material"]).size().eq(105).all()
    assert frame[["project_site_id", "material", "date"]].duplicated().sum() == 0

    residuals = []
    for _, group in frame.groupby(["project_site_id", "material"]):
        group = group.sort_values("date")
        intervals = group["date"].dt.normalize().diff().dropna().dt.days
        assert intervals.eq(7).all()
        close = group["opening_stock_qty"] + group["incoming_qty"] - group["consumption_qty"]
        residuals.extend((close.iloc[:-1].to_numpy() - group["opening_stock_qty"].iloc[1:].to_numpy()).tolist())
        assert np.all(group["opening_stock_qty"].to_numpy() >= 0)
        assert np.all(close.to_numpy() >= 0)
    assert residuals
    assert max(abs(value) for value in residuals) <= 0.01
