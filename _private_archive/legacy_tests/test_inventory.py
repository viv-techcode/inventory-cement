from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, func

from inventory_app.inventory import (
    DuplicateTransactionError,
    InventoryError,
    get_current_balance,
    local_today,
    record_inventory_transaction,
)
from inventory_app.models import HistoricalObservation, InventoryTransaction, Material, ProjectSite
from inventory_app.database import Database, initialize_database


def _ids(session):
    site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == "Jakhan, Dehradun"))
    material = session.scalar(select(Material).where(Material.name == "Cement"))
    return site.id, material.id, material.unit


def test_historical_rows_do_not_create_operational_stock(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        site_id, material_id, _ = _ids(session)
        assert session.scalar(select(func.count(HistoricalObservation.id))) > 0
        assert get_current_balance(session, site_id, material_id) is None
        assert session.scalar(select(func.count(InventoryTransaction.id))) == 0


def test_stock_formula_adjustments_validation_and_persistence(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        site_id, material_id, unit = _ids(session)
        record_inventory_transaction(session, idempotency_key="open-1", site_id=site_id, material_id=material_id, transaction_type="opening_balance", quantity="100", unit=unit, transaction_date=local_today(), notes="Physical count")
        session.commit()
    with db.session() as session:
        site_id, material_id, unit = _ids(session)
        record_inventory_transaction(session, idempotency_key="receipt-1", site_id=site_id, material_id=material_id, transaction_type="receipt", quantity="25", unit=unit, transaction_date=local_today())
        record_inventory_transaction(session, idempotency_key="consume-1", site_id=site_id, material_id=material_id, transaction_type="consumption", quantity="30", unit=unit, transaction_date=local_today())
        record_inventory_transaction(session, idempotency_key="adjust-1", site_id=site_id, material_id=material_id, transaction_type="adjustment", quantity="-5", unit=unit, transaction_date=local_today(), notes="Physical count correction")
        session.commit()
    with db.session() as session:
        site_id, material_id, _ = _ids(session)
        assert get_current_balance(session, site_id, material_id) == Decimal("90.0000")

    reopened = Database(db.url)
    initialize_database(reopened)
    with reopened.session() as session:
        site_id, material_id, _ = _ids(session)
        assert get_current_balance(session, site_id, material_id) == Decimal("90.0000")
    reopened.dispose()


def test_invalid_unit_negative_balance_duplicate_and_future_date(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        site_id, material_id, unit = _ids(session)
        record_inventory_transaction(session, idempotency_key="open-validation", site_id=site_id, material_id=material_id, transaction_type="opening_balance", quantity=10, unit=unit, transaction_date=local_today())
        session.commit()
    with db.session() as session:
        site_id, material_id, unit = _ids(session)
        with pytest.raises(InventoryError, match="Unit mismatch"):
            record_inventory_transaction(session, idempotency_key="wrong-unit", site_id=site_id, material_id=material_id, transaction_type="receipt", quantity=5, unit="m3", transaction_date=local_today())
        with pytest.raises(InventoryError, match="negative balance"):
            record_inventory_transaction(session, idempotency_key="over-consume", site_id=site_id, material_id=material_id, transaction_type="consumption", quantity=11, unit=unit, transaction_date=local_today())
        with pytest.raises(InventoryError, match="future"):
            record_inventory_transaction(session, idempotency_key="future", site_id=site_id, material_id=material_id, transaction_type="receipt", quantity=1, unit=unit, transaction_date=local_today() + timedelta(days=1))
        session.rollback()

    with db.session() as session:
        site_id, material_id, unit = _ids(session)
        record_inventory_transaction(session, idempotency_key="one-time", site_id=site_id, material_id=material_id, transaction_type="receipt", quantity=1, unit=unit, transaction_date=local_today())
        session.commit()
    with db.session() as session:
        site_id, material_id, unit = _ids(session)
        with pytest.raises(DuplicateTransactionError, match="already been posted"):
            record_inventory_transaction(session, idempotency_key="one-time", site_id=site_id, material_id=material_id, transaction_type="receipt", quantity=1, unit=unit, transaction_date=local_today())
