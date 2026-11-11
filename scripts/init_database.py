"""Initialize the application schema and import the canonical historical CSV once."""
from __future__ import annotations

from inventory_app import config
from inventory_app.database import Database, initialize_database
from scripts.load_operations import ensure_baseline_planner_history, ensure_ledger_baseline


def main() -> int:
    database = Database(config.DATABASE_URL)
    try:
        initialize_database(database)
        result = ensure_ledger_baseline(database, config.SOURCE_CSV)
        planner_history = ensure_baseline_planner_history(database, config.SOURCE_CSV)
        print(f"Database ready: {result or 'baseline already loaded'}")
        print(f"Planner history rows added: {planner_history}")
    finally:
        database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
