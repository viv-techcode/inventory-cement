from __future__ import annotations

from inventory_app import config
from inventory_app.ingestion import ensure_primary_dataset_import, import_dataframe, read_csv_bytes
from inventory_app.models import HistoricalObservation
from scripts.merge_dataset import rebuild
from sqlalchemy import func, select


def test_merged_rebuild_is_deterministic_and_preserves_origin_counts():
    first = rebuild()
    first_bytes = config.SOURCE_CSV.read_bytes()
    second = rebuild()
    assert config.SOURCE_CSV.read_bytes() == first_bytes
    assert len(first) == len(second) == 8940
    assert first["data_origin"].value_counts().to_dict() == {
        "original_self_created": 6300,
        "generated_extension": 2640,
    }
    assert second[["project_site_id", "material", "date"]].duplicated().sum() == 0


def test_merged_import_is_idempotent(seeded_db):
    db, initial = seeded_db
    assert initial.accepted_rows == 8940
    duplicate = ensure_primary_dataset_import(db, str(config.SOURCE_CSV))
    assert duplicate is not None and duplicate.duplicate_file is True
    frame = read_csv_bytes(config.SOURCE_CSV.read_bytes())
    second = import_dataframe(db, frame, file_name=config.SOURCE_CSV.name, file_bytes=config.SOURCE_CSV.read_bytes())
    assert second.duplicate_file is True
    with db.session() as session:
        assert session.scalar(select(func.count(HistoricalObservation.id))) == 8940
        counts = dict(session.execute(
            select(HistoricalObservation.source_tag, func.count(HistoricalObservation.id))
            .group_by(HistoricalObservation.source_tag)
        ).all())
        assert counts == {"original_self_created": 6300, "generated_extension": 2640}
