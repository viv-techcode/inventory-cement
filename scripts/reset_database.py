"""Restore the loaded baseline by rebuilding the configured database."""
from inventory_app import config
from inventory_app.database import Base, Database, initialize_database
from scripts.load_operations import ensure_baseline_planner_history, ensure_ledger_baseline

def reset() -> dict[str, int] | None:
    database = Database(config.DATABASE_URL)
    try:
        Base.metadata.drop_all(database.engine)
        initialize_database(database)
        result = ensure_ledger_baseline(database, config.SOURCE_CSV)
        result = result or {}
        result["planner_history_rows"] = ensure_baseline_planner_history(database, config.SOURCE_CSV)
        return result
    finally:
        database.dispose()

if __name__ == "__main__":
    print(reset() or "Baseline restored")
