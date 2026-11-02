"""SQLite connection management and idempotent schema initialization."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from inventory_app.models import ApplicationSetting, Base, SchemaVersion

SCHEMA_VERSION = 3
DEFAULT_SETTINGS: dict[str, object] = {
    "safety_stock_days_default": 7,
    "default_forecast_frequency": "weekly",
    "default_forecast_horizon_days": 30,
    "replenishment_risk_days": 7,
    "currency": "INR",
}


class Database:
    """Small SQLAlchemy wrapper; callers own each session and transaction."""

    def __init__(self, url: str):
        self.url = url
        parsed = make_url(url)
        if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, ":memory:"):
            Path(parsed.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False, "timeout": 30} if parsed.get_backend_name() == "sqlite" else {}
        self.engine = create_engine(url, future=True, connect_args=connect_args, pool_pre_ping=True)
        if parsed.get_backend_name() == "sqlite":
            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()
        self._sessions = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False, autoflush=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def _apply_additive_migrations(db: Database) -> None:
    """Apply idempotent SQLite-compatible ALTERs that ``create_all`` cannot perform."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        if "inventory_transactions" in tables:
            columns = {column["name"] for column in inspector.get_columns("inventory_transactions")}
            if "unit_cost_inr" not in columns:
                # Nullable by design: legacy movements have no recorded cost basis and are not
                # backfilled from historical CSV prices or catalogue reference prices.
                connection.execute(text(
                    "ALTER TABLE inventory_transactions ADD COLUMN unit_cost_inr NUMERIC(18, 4)"
                ))
        source_tag_defaults = {
            "historical_observations": "historical_csv",
            "inventory_transactions": "operator",
            "customers": "operator",
            "sales_records": "operator",
            "reorder_rules": "operator",
        }
        for table, default in source_tag_defaults.items():
            if table not in tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "source_tag" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN source_tag VARCHAR(40) NOT NULL DEFAULT '{default}'"
                ))


def initialize_database(db: Database) -> None:
    """Create missing tables and apply documented, additive schema migrations."""
    Base.metadata.create_all(db.engine)
    _apply_additive_migrations(db)
    with db.session() as session:
        version = session.get(SchemaVersion, 1)
        if version is None:
            session.add(SchemaVersion(id=1, version=SCHEMA_VERSION))
        elif version.version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version.version} is newer than this app ({SCHEMA_VERSION})."
            )
        elif version.version < SCHEMA_VERSION:
            # Migrations only add columns/tables; no existing rows are deleted or rewritten.
            version.version = SCHEMA_VERSION
        for key, value in DEFAULT_SETTINGS.items():
            if session.get(ApplicationSetting, key) is None:
                import json
                session.add(ApplicationSetting(key=key, value_json=json.dumps(value)))
        session.commit()
