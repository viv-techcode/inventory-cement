from __future__ import annotations

from inventory_app import config
from inventory_app.ingestion import ensure_primary_dataset_import, import_dataframe, read_csv_bytes
from inventory_app.models import HistoricalObservation
from sqlalchemy import func, inspect, select


def test_dataset_import_is_idempotent(seeded_db):
    db, initial = seeded_db
    assert initial.accepted_rows == 8940
    duplicate = ensure_primary_dataset_import(db, str(config.SOURCE_CSV))
    assert duplicate is not None and duplicate.duplicate_file is True
    frame = read_csv_bytes(config.SOURCE_CSV.read_bytes())
    second = import_dataframe(db, frame, file_name=config.SOURCE_CSV.name, file_bytes=config.SOURCE_CSV.read_bytes())
    assert second.duplicate_file is True
    with db.session() as session:
        assert session.scalar(select(func.count(HistoricalObservation.id))) == 8940
        assert "source_tag" not in {column["name"] for column in inspect(session.bind).get_columns("historical_observations")}
