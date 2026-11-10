from __future__ import annotations

from pathlib import Path

import pytest

from inventory_app.database import Database, initialize_database
from inventory_app.ingestion import import_dataframe, read_csv_bytes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = PROJECT_ROOT / "data" / "construction_materials_dehradun_dataset.csv"


@pytest.fixture
def fresh_db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'project_test.db').as_posix()}"
    database = Database(url)
    initialize_database(database)
    yield database
    database.dispose()


@pytest.fixture
def seeded_db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'seeded_test.db').as_posix()}"
    database = Database(url)
    initialize_database(database)
    raw = SOURCE_CSV.read_bytes()
    frame = read_csv_bytes(raw)
    result = import_dataframe(
        database,
        frame,
        file_name=SOURCE_CSV.name,
        file_bytes=raw,
        source_kind="test_fixture",
    )
    yield database, result
    database.dispose()
