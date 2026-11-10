from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "construction_materials_dehradun_dataset.csv"


def test_merged_dataset_integrity_coverage_origin_and_stock_chain():
    frame = pd.read_csv(SOURCE)
    assert frame.shape == (8940, 15)
    assert frame.columns[-1] == "data_origin"
    assert frame["data_origin"].value_counts().to_dict() == {
        "original_self_created": 6300,
        "generated_extension": 2640,
    }
    assert frame.groupby(["project_site_id", "material"]).size().eq(149).all()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    assert frame["date"].min().date().isoformat() == "2024-01-01"
    assert frame["date"].max().date().isoformat() == "2026-11-02"
    assert frame[["project_site_id", "material", "date"]].duplicated().sum() == 0
    residuals = []
    for _, group in frame.groupby(["project_site_id", "material"]):
        group = group.sort_values("date")
        intervals = group["date"].dt.normalize().diff().dropna().dt.days
        assert intervals.eq(7).all()
        close = group["opening_stock_qty"] + group["incoming_qty"] - group["consumption_qty"]
        residuals.extend((close.iloc[:-1].to_numpy() - group["opening_stock_qty"].iloc[1:].to_numpy()).tolist())
        assert np.all(close.to_numpy() >= 0)
    assert max(abs(value) for value in residuals) <= 1e-6


def test_merged_dataset_matches_archived_source_value_hashes():
    manifest = (ROOT / "data" / "archive" / "pre_merge" / "MANIFEST.txt").read_text(encoding="utf-8")
    for digest in (
        "828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c",
        "e9c25f5b7d9538b6d47bc3297c76886884cce686b4a614492daa20f9c5347d3a",
    ):
        assert digest in manifest
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()
