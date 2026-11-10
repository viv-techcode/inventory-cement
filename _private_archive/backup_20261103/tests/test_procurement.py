from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, func

from inventory_app.inventory import InventoryError, get_current_balance, local_today, record_inventory_transaction
from inventory_app.models import (
    InventoryTransaction,
    Material,
    ProjectSite,
    PurchaseOrder,
    PurchaseOrderLine,
    ReceiptRecord,
    Supplier,
)
from inventory_app.procurement import (
    ProcurementError,
    create_purchase_order,
    create_supplier,
    post_receipt,
    purchase_order_lines,
    transition_purchase_order,
)


def _catalog(session):
    site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == "Jakhan, Dehradun"))
    material = session.scalar(select(Material).where(Material.name == "Cement"))
    supplier = create_supplier(session, name="Test Supplier Ltd", email="buyer@example.test")
    return site, material, supplier


def test_purchase_order_partial_receipts_update_inventory_exactly_once(seeded_db):
    db, _ = seeded_db
    today = local_today()
    with db.session() as session:
        site, material, supplier = _catalog(session)
        record_inventory_transaction(session, idempotency_key="po-test-opening", site_id=site.id, material_id=material.id, transaction_type="opening_balance", quantity=100, unit=material.unit, transaction_date=today)
        order = create_purchase_order(
            session,
            idempotency_key="po-create-1",
            supplier_id=supplier.id,
            site_id=site.id,
            order_date=today,
            expected_delivery_date=today + timedelta(days=4),
            lines=[{"material_id": material.id, "quantity": 100, "unit": material.unit, "unit_price_inr": 400}],
        )
        order_id = order.id
        line = session.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id))
        line_id = line.id
        assert order.status == "Draft"
        session.commit()

    with db.session() as session:
        transition_purchase_order(session, order_id, "Pending approval")
        transition_purchase_order(session, order_id, "Approved")
        session.commit()

    with db.session() as session:
        receipt = post_receipt(
            session,
            idempotency_key="grn-001",
            receipt_reference="GRN-001",
            purchase_order_line_id=line_id,
            quantity=30,
            unit="50-kg bags",
            receipt_date=today,
        )
        session.commit()

    with db.session() as session:
        order = session.get(PurchaseOrder, order_id)
        line = session.get(PurchaseOrderLine, line_id)
        assert order.status == "Partially received"
        assert line.quantity_received == Decimal("30.0000")
        assert purchase_order_lines(session, order_id)[0]["outstanding"] == Decimal("70.0000")
        site_id = order.site_id
        material_id = line.material_id
        assert get_current_balance(session, site_id, material_id) == Decimal("130.0000")
        assert session.scalar(select(func.count(ReceiptRecord.id))) == 1
        assert session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source == "purchase_order")) == 1
        with pytest.raises(InventoryError, match="already been posted"):
            post_receipt(session, idempotency_key="grn-001", receipt_reference="GRN-001", purchase_order_line_id=line_id, quantity=30, unit="50-kg bags", receipt_date=today)
        session.rollback()

    with db.session() as session:
        with pytest.raises(ProcurementError, match="exceeds outstanding"):
            post_receipt(session, idempotency_key="grn-too-much", receipt_reference="GRN-OVER", purchase_order_line_id=line_id, quantity=71, unit="50-kg bags", receipt_date=today)
        session.rollback()

    with db.session() as session:
        post_receipt(session, idempotency_key="grn-002", receipt_reference="GRN-002", purchase_order_line_id=line_id, quantity=70, unit="50-kg bags", receipt_date=today)
        session.commit()
    with db.session() as session:
        order = session.get(PurchaseOrder, order_id)
        line = session.get(PurchaseOrderLine, line_id)
        assert order.status == "Received"
        assert line.quantity_received == Decimal("100.0000")
        assert get_current_balance(session, order.site_id, line.material_id) == Decimal("200.0000")
        assert session.scalar(select(func.count(ReceiptRecord.id))) == 2
        assert session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source == "purchase_order")) == 2


def test_purchase_order_requires_valid_supplier_unit_and_status(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        site, material, supplier = _catalog(session)
        with pytest.raises(ProcurementError, match="Unit mismatch"):
            create_purchase_order(session, idempotency_key="bad-unit", supplier_id=supplier.id, site_id=site.id, order_date=local_today(), expected_delivery_date=None, lines=[{"material_id": material.id, "quantity": 5, "unit": "kg", "unit_price_inr": 2}])
        order = create_purchase_order(session, idempotency_key="po-status-test", supplier_id=supplier.id, site_id=site.id, order_date=local_today(), expected_delivery_date=None, lines=[{"material_id": material.id, "quantity": 5, "unit": material.unit, "unit_price_inr": 2}])
        order_id = order.id
        session.commit()
    with db.session() as session:
        with pytest.raises(ProcurementError, match="not allowed"):
            transition_purchase_order(session, order_id, "Approved")
        session.rollback()


def test_receipt_cannot_post_without_initialized_stock(seeded_db):
    db, _ = seeded_db
    today = local_today()
    with db.session() as session:
        site, material, supplier = _catalog(session)
        order = create_purchase_order(session, idempotency_key="po-no-stock", supplier_id=supplier.id, site_id=site.id, order_date=today, expected_delivery_date=today + timedelta(days=2), lines=[{"material_id": material.id, "quantity": 5, "unit": material.unit, "unit_price_inr": 10}])
        line = session.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id))
        transition_purchase_order(session, order.id, "Pending approval")
        transition_purchase_order(session, order.id, "Approved")
        line_id = line.id
        session.commit()
    with db.session() as session:
        with pytest.raises(InventoryError, match="Initialize the operational opening balance"):
            post_receipt(session, idempotency_key="no-open-grn", receipt_reference="NO-OPEN-GRN", purchase_order_line_id=line_id, quantity=1, unit="50-kg bags", receipt_date=today)
        session.rollback()
        assert session.scalar(select(func.count(ReceiptRecord.id))) == 0
