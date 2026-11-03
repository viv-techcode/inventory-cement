"""Paths and environment-backed configuration for local deployment."""
from __future__ import annotations

import os
from pathlib import Path
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATASET_NAME = "Construction Materials Dehradun Dataset"
DATASET_SOURCE_KIND = "construction_materials_dehradun_dataset"
SOURCE_CSV = DATA_DIR / "construction_materials_dehradun_dataset.csv"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "models"
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_DATABASE_URL = f"sqlite:///{(DATA_DIR / 'inventory.db').as_posix()}"
DATABASE_URL = os.getenv("INVENTORY_DB_URL", DEFAULT_DATABASE_URL)


def ensure_runtime_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_URL.startswith("sqlite:"):
        url = make_url(DATABASE_URL)
        database = url.database
        if database and database != ":memory:":
            Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def get_artifacts_dir() -> Path:
    custom = os.getenv("INVENTORY_ARTIFACTS_DIR")
    path = Path(custom).expanduser() if custom else ARTIFACTS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path
