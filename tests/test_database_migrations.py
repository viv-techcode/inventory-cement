from __future__ import annotations

from datetime import date

from sqlalchemy import inspect, select, text

from inventory_app.database import Database, initialize_database
from inventory_app.models import InventoryTransaction, Material, ProjectSite, SchemaVersion


def test_v3_additive_migration_is_idempotent_and_preserves_legacy_rows(tmp_path):
    db = Database(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    initialize_database(db)
    with db.session() as session:
        site = ProjectSite(identifier="Legacy Site", name="Legacy Site", city="Moradabad", state="Uttar Pradesh")
        material = Material(name="Legacy Material", unit="pieces")
        session.add_all([site, material])
        session.flush()
        session.add(InventoryTransaction(
            idempotency_key="legacy-opening",
            site_id=site.id,
            material_id=material.id,
            transaction_type="opening_balance",
            quantity=12,
            unit=material.unit,
            transaction_date=date(2025, 1, 1),
            source="manual",
            notes="legacy row preserved",
        ))
        session.commit()

    # Simulate a pre-v3 database: the v2 cost field and all source-tag columns are absent.
    legacy_tag_tables = (
        "historical_observations",
        "inventory_transactions",
        "customers",
        "sales_records",
        "reorder_rules",
    )
    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE inventory_transactions DROP COLUMN unit_cost_inr"))
        for table in legacy_tag_tables:
            connection.execute(text(f"ALTER TABLE {table} DROP COLUMN source_tag"))
        connection.execute(text("UPDATE schema_version SET version = 1 WHERE id = 1"))
    assert "unit_cost_inr" not in {column["name"] for column in inspect(db.engine).get_columns("inventory_transactions")}
    for table in legacy_tag_tables:
        assert "source_tag" not in {column["name"] for column in inspect(db.engine).get_columns(table)}

    initialize_database(db)
    initialize_database(db)
    assert "unit_cost_inr" in {column["name"] for column in inspect(db.engine).get_columns("inventory_transactions")}
    for table in legacy_tag_tables:
        assert "source_tag" in {column["name"] for column in inspect(db.engine).get_columns(table)}
    with db.session() as session:
        txn = session.scalar(select(InventoryTransaction).where(InventoryTransaction.idempotency_key == "legacy-opening"))
        assert txn is not None
        assert txn.quantity == 12
        assert txn.notes == "legacy row preserved"
        assert txn.unit_cost_inr is None
        assert txn.source_tag == "operator"
        assert session.get(SchemaVersion, 1).version == 3
    db.dispose()
