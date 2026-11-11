from __future__ import annotations

import pandas as pd
from sqlalchemy import select, func

from inventory_app.data_quality import build_data_quality_report, history_to_frame
from inventory_app.ingestion import import_dataframe, read_csv_bytes, validate_frame
from inventory_app.models import HistoricalObservation, ImportRun, Material, ProjectSite, RejectedRow
from conftest import SOURCE_CSV


def test_supplied_csv_schema_and_quality(seeded_db):
    db, result = seeded_db
    assert result.total_rows == 8940
    assert result.accepted_rows == 8940
    assert result.rejected_rows == 0
    with db.session() as session:
        history = history_to_frame(session)
        report = build_data_quality_report(history)
        assert report["row_count"] == 8940
        assert report["column_count"] == 16
        assert report["site_count"] == 6
        assert report["material_count"] == 10
        assert report["series_count"] == 60
        assert report["series_observations_min"] == 149
        assert report["series_observations_max"] == 149
        assert report["date_min"].startswith("2024-01-01")
        assert report["date_max"].startswith("2026-11-02")
        assert sum(report["missing_by_column"].values()) == 0
        assert report["stock_rollforward_comparable_pairs"] == 8880
        assert report["stock_rollforward_consistency_pct"] == 100.0
        assert report["wpi_reference_month_mismatches"] == 0
        assert session.scalar(select(func.count(HistoricalObservation.id))) == 8940
        assert session.scalar(select(func.count(Material.id))) == 10
        assert session.scalar(select(func.count(ProjectSite.id))) == 6


def test_same_file_import_is_idempotent(seeded_db):
    db, initial = seeded_db
    raw = SOURCE_CSV.read_bytes()
    duplicate = import_dataframe(db, read_csv_bytes(raw), file_name=SOURCE_CSV.name, file_bytes=raw)
    assert duplicate.duplicate_file is True
    assert duplicate.accepted_rows == 8940
    with db.session() as session:
        assert session.scalar(select(func.count(ImportRun.id))) == 1
        assert session.scalar(select(func.count(HistoricalObservation.id))) == 8940


def test_invalid_rows_are_reported_not_silently_removed(fresh_db):
    rows = pd.DataFrame([
        {
            "date": "not-a-date", "project_site_id": "Site A", "city": "City", "state": "State",
            "project_type": "Residential", "project_phase": "Foundation", "material": "Test cement", "unit": "bag",
            "consumption_qty": -1, "opening_stock_qty": 10, "incoming_qty": 0, "unit_price_inr": 4,
            "supplier_lead_time_days": 4, "wpi_reference_month": "2025-02",
        },
        {
            "date": "2025-02-01", "project_site_id": "Site B", "city": "City", "state": "State",
            "project_type": "Residential", "project_phase": "Structure", "material": "Test cement", "unit": "bag",
            "consumption_qty": 2, "opening_stock_qty": 10, "incoming_qty": 0, "unit_price_inr": 4,
            "supplier_lead_time_days": 4, "wpi_reference_month": "2025-02",
        },
    ])
    valid, rejected, summary = validate_frame(rows)
    assert len(valid) == 1
    assert len(rejected) == 1
    assert "date" in rejected[0]["reason"]
    assert "consumption_qty cannot be negative" in rejected[0]["reason"]
    assert summary["total_rows"] == 2
    raw = rows.to_csv(index=False).encode()
    result = import_dataframe(fresh_db, rows, file_name="bad.csv", file_bytes=raw)
    assert result.accepted_rows == 1
    assert result.rejected_rows == 1
    with fresh_db.session() as session:
        rejected_row = session.scalar(select(RejectedRow))
        assert rejected_row is not None
        assert "not-a-date" in rejected_row.raw_json
        assert session.scalar(select(func.count(HistoricalObservation.id))) == 1


def test_schema_mapping_rejects_missing_required_columns():
    frame = pd.DataFrame({"date": ["2025-01-01"], "material": ["Cement"]})
    valid, rejected, summary = validate_frame(frame)
    assert valid == []
    assert rejected == []
    assert len(summary["schema_errors"]) > 1


def test_freshness_warning_starts_only_after_seven_full_days():
    source = read_csv_bytes(SOURCE_CSV.read_bytes())
    frame = source.iloc[[0]].copy()
    frame["date"] = pd.to_datetime(["2026-01-05 12:00:00"])
    frame.loc[:, "wpi_reference_month"] = "2026-01"
    seven_days = build_data_quality_report(frame, as_of=pd.Timestamp("2026-01-12").date())
    eight_days = build_data_quality_report(frame, as_of=pd.Timestamp("2026-01-13").date())
    assert not any("latest observation" in warning.lower() for warning in seven_days["warnings"])
    assert any("latest observation is 8 days old" in warning.lower() for warning in eight_days["warnings"])

