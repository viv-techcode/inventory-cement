from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from inventory_app.costing import inventory_cost_summary
from inventory_app.database import Database, initialize_database
from inventory_app.inventory import InventoryError, get_current_balance, local_today, record_inventory_transaction
from inventory_app.models import Customer, InventoryTransaction, Material, ProjectSite, SalesRecord
from inventory_app.sales import DuplicateSaleError, SalesError, create_customer, create_sale


def _catalog(session):
    site = ProjectSite(identifier="North Yard", name="North Yard", city="Moradabad", state="Uttar Pradesh")
    material = Material(name="Cement Test", unit="50-kg bags", safety_stock_days=7)
    session.add_all([site, material])
    session.flush()
    return site, material


def _opening(session, site, material, *, quantity, unit_cost=None, key="open-sale"):
    return record_inventory_transaction(
        session,
        idempotency_key=key,
        site_id=site.id,
        material_id=material.id,
        transaction_type="opening_balance",
        quantity=quantity,
        unit=material.unit,
        transaction_date=local_today(),
        unit_cost_inr=unit_cost,
        notes="Verified physical count",
    )


def test_sale_uses_recorded_fifo_cost_and_persists_with_stock_movement(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        site, material = _catalog(session)
        _opening(session, site, material, quantity=5, unit_cost=8)
        record_inventory_transaction(
            session, idempotency_key="sale-receipt", site_id=site.id, material_id=material.id,
            transaction_type="receipt", quantity=5, unit=material.unit,
            transaction_date=local_today(), unit_cost_inr=10, reference="RCPT-1",
        )
        customer = create_customer(session, name="Verified Customer", email="buyer@example.test")
        sale, created = create_sale(
            session, idempotency_key="sale-fifo-1", site_id=site.id, material_id=material.id,
            customer_id=customer.id, quantity=7, unit=material.unit, unit_sale_price_inr=15,
            sale_date=local_today(), reference="INV-1",
        )
        assert created is True
        assert sale.revenue_inr == Decimal("105.00")
        assert sale.cost_of_goods_sold_inr == Decimal("60.00")
        assert sale.unit_cost_basis_inr == Decimal("8.5714")
        assert sale.gross_margin_inr == Decimal("45.00")
        sale_id = sale.id
        site_id, material_id = site.id, material.id
        session.commit()

    with db.session() as session:
        sale = session.get(SalesRecord, sale_id)
        assert sale is not None
        assert session.get(Customer, sale.customer_id).name == "Verified Customer"
        assert get_current_balance(session, site_id, material_id) == Decimal("3.0000")
        value = inventory_cost_summary(session, site_id=site_id, material_id=material_id, as_of=local_today())
        assert value["stock_value_inr"] == Decimal("30.00")
        assert value["cost_basis_status"] == "Fully costed"
        assert session.scalar(select(func.count(SalesRecord.id))) == 1
        assert session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source == "sale")) == 1

    reopened = Database(db.url)
    initialize_database(reopened)
    with reopened.session() as session:
        assert session.scalar(select(func.count(SalesRecord.id))) == 1
        assert get_current_balance(session, site_id, material_id) == Decimal("3.0000")
    reopened.dispose()


def test_unknown_recorded_cost_makes_margin_and_total_value_unavailable(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        site, material = _catalog(session)
        _opening(session, site, material, quantity=4, unit_cost=None, key="open-unknown")
        sale, _ = create_sale(
            session, idempotency_key="sale-unknown-cost", site_id=site.id, material_id=material.id,
            customer_id=None, quantity=2, unit=material.unit, unit_sale_price_inr=12,
            sale_date=local_today(),
        )
        assert sale.revenue_inr == Decimal("24.00")
        assert sale.cost_of_goods_sold_inr is None
        assert sale.gross_margin_inr is None
        site_id, material_id = site.id, material.id
        session.commit()
    with db.session() as session:
        value = inventory_cost_summary(session, site_id=site_id, material_id=material_id, as_of=local_today())
        assert value["current_stock"] == Decimal("2.0000")
        assert value["stock_value_inr"] is None
        assert value["cost_basis_status"] == "No recorded cost basis"


def test_sale_idempotency_and_integrity_validation(fresh_db):
    with fresh_db.session() as session:
        site, material = _catalog(session)
        _opening(session, site, material, quantity=5, unit_cost=3, key="open-validation")
        session.commit()

    payload = dict(
        idempotency_key="sale-idempotency",
        site_id=site.id,
        material_id=material.id,
        customer_id=None,
        quantity=2,
        unit=material.unit,
        unit_sale_price_inr=7,
        sale_date=local_today(),
        reference="IDEM-1",
    )
    with fresh_db.session() as session:
        first, created = create_sale(session, **payload)
        session.commit()
        assert created is True
        sale_id = first.id
    with fresh_db.session() as session:
        repeated, created = create_sale(session, **payload)
        assert repeated.id == sale_id
        assert created is False
        with pytest.raises(DuplicateSaleError, match="different sale"):
            create_sale(session, **{**payload, "quantity": 1})
        with pytest.raises(SalesError, match="Unit mismatch"):
            create_sale(session, **{**payload, "idempotency_key": "bad-unit", "unit": "m3"})
        with pytest.raises(SalesError, match="negative balance"):
            create_sale(session, **{**payload, "idempotency_key": "too-much", "quantity": 10})
        with pytest.raises(SalesError, match="future"):
            create_sale(session, **{**payload, "idempotency_key": "future-sale", "sale_date": local_today() + timedelta(days=1)})
        assert session.scalar(select(func.count(SalesRecord.id))) == 1
        session.rollback()


def test_adjustment_requires_a_reason(fresh_db):
    with fresh_db.session() as session:
        site, material = _catalog(session)
        _opening(session, site, material, quantity=5, unit_cost=2, key="open-adjust")
        session.commit()
    with fresh_db.session() as session:
        with pytest.raises(InventoryError, match="reason is required"):
            record_inventory_transaction(
                session, idempotency_key="adjust-no-reason", site_id=site.id, material_id=material.id,
                transaction_type="adjustment", quantity=-1, unit=material.unit, transaction_date=local_today(),
            )
        session.rollback()
