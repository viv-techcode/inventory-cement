"""Initialize the application schema and import the canonical historical CSV once."""
from __future__ import annotations

from inventory_app import config
from inventory_app.database import Database, initialize_database
from inventory_app.ingestion import ensure_primary_dataset_import


def main() -> int:
    database = Database(config.DATABASE_URL)
    try:
        initialize_database(database)
        result = ensure_primary_dataset_import(database, str(config.SOURCE_CSV))
        print(
            f"Database ready: schema initialized; historical rows={result.accepted_rows}; "
            f"duplicate_file={result.duplicate_file}. No operational stock transactions were created."
        )
    finally:
        database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
