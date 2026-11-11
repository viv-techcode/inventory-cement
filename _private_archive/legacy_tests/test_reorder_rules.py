from __future__ import annotations

from decimal import Decimal

import pytest

from inventory_app.catalog import create_material, create_site
from inventory_app.inventory import InventoryError, get_current_balance, local_today, record_inventory_transaction
from inventory_app.reorder import ReorderRuleError, save_reorder_rule, stock_reorder_status


def test_pair_rule_drives_low_stock_alert_and_recovers_after_receipt(fresh_db):
    with fresh_db.session() as session:
        site = create_site(session, identifier="Yard A", name="Yard A", city="Moradabad", state="Uttar Pradesh")
        material = create_material(session, name="Bricks", unit="pieces", safety_stock_days=3)
        save_reorder_rule(
            session,
            site_id=site.id,
            material_id=material.id,
            unit="pieces",
            reorder_point_qty=10,
            lead_time_days=6,
            safety_stock_days=4,
            minimum_order_qty=12,
            order_multiple=4,
        )
        record_inventory_transaction(
            session, idempotency_key="reorder-open", site_id=site.id, material_id=material.id,
            transaction_type="opening_balance", quantity=5, unit="pieces", transaction_date=local_today(),
            notes="Verified physical count",
        )
        session.commit()
        site_id, material_id = site.id, material.id

    with fresh_db.session() as session:
        status = stock_reorder_status(session, site_id, material_id)
        assert status["current_stock"] == Decimal("5.0000")
        assert status["reorder_point_qty"] == Decimal("10.0000")
        assert status["status"] == "Below reorder point"
        assert status["alert"] is True
        session.commit()

    with fresh_db.session() as session:
        record_inventory_transaction(
            session, idempotency_key="reorder-receipt", site_id=site_id, material_id=material_id,
            transaction_type="receipt", quantity=6, unit="pieces", transaction_date=local_today(),
        )
        session.commit()
    with fresh_db.session() as session:
        status = stock_reorder_status(session, site_id, material_id)
        assert get_current_balance(session, site_id, material_id) == Decimal("11.0000")
        assert status["status"] == "At/above reorder point"
        assert status["alert"] is False


def test_rule_validates_units_and_nonnegative_threshold(fresh_db):
    with fresh_db.session() as session:
        site = create_site(session, identifier="Yard B", name="Yard B", city="Moradabad", state="Uttar Pradesh")
        material = create_material(session, name="Sand", unit="m3")
        with pytest.raises(ReorderRuleError, match="Unit mismatch"):
            save_reorder_rule(session, site_id=site.id, material_id=material.id, unit="kg", reorder_point_qty=2)
        with pytest.raises(ReorderRuleError, match="cannot be negative"):
            save_reorder_rule(session, site_id=site.id, material_id=material.id, unit="m3", reorder_point_qty=-2)
