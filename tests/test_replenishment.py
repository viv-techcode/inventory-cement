from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from inventory_app.replenishment import calculate_replenishment, estimate_historical_daily_rate, save_replenishment_review
from inventory_app.models import Material, ProjectSite, PurchaseOrder, ReplenishmentReview
from sqlalchemy import select, func


def test_lead_time_safety_stock_incoming_constraints_and_cost():
    today = date(2026, 1, 1)
    result = calculate_replenishment(
        unit="bags",
        current_stock=60,
        current_stock_basis="operational ledger",
        lead_time_days=10,
        safety_stock_days=2,
        historical_daily_rate=10,
        forecast_values=[70, 70, 70],
        forecast_step_days=7,
        incoming_deliveries=[
            {"quantity": 20, "unit": "bags", "expected_date": today + timedelta(days=8), "status": "Approved", "reference": "PO-ON-TIME"},
            {"quantity": 40, "unit": "bags", "expected_date": today + timedelta(days=11), "status": "Approved", "reference": "PO-LATE"},
            {"quantity": 50, "unit": "bags", "expected_date": today + timedelta(days=3), "status": "Draft", "reference": "PO-DRAFT"},
        ],
        unit_price=5,
        price_unit="bags",
        price_basis="historical dataset median (estimate)",
        minimum_order_qty=30,
        order_multiple=10,
        as_of=today,
    )
    assert result["lead_time_demand"] == Decimal("100")
    assert result["safety_stock_qty"] == Decimal("20")
    assert result["eligible_incoming_qty"] == Decimal("20")
    assert result["excluded_late_incoming_qty"] == Decimal("40")
    assert result["recommended_order_qty"] == Decimal("40")
    assert result["estimated_order_cost_inr"] == Decimal("200.00")
    assert result["status"] == "At risk"
    assert result["provisional"] is False
    assert any("estimate" in warning.lower() for warning in result["warnings"])


def test_user_confirmed_incoming_scenario_can_reduce_recommendation_without_a_po():
    today = date(2026, 1, 1)
    result = calculate_replenishment(
        unit="bags",
        current_stock=0,
        current_stock_basis="operational ledger",
        lead_time_days=7,
        safety_stock_days=0,
        historical_daily_rate=1,
        forecast_values=[7],
        forecast_step_days=7,
        incoming_deliveries=[{"quantity": 3, "unit": "bags", "expected_date": today + timedelta(days=3), "status": "Confirmed", "reference": "User-entered confirmed delivery"}],
        as_of=today,
    )
    assert result["lead_time_demand"] == Decimal("7")
    assert result["eligible_incoming_qty"] == Decimal("3")
    assert result["recommended_order_qty"] == Decimal("4")


def test_missing_stock_and_unit_mismatch_are_transparent():
    result = calculate_replenishment(
        unit="kg",
        current_stock=None,
        current_stock_basis="not initialized",
        lead_time_days=5,
        safety_stock_days=3,
        historical_daily_rate=2,
        forecast_values=None,
        incoming_deliveries=[{"quantity": 100, "unit": "m3", "status": "Approved", "expected_date": date(2026, 1, 2)}],
        unit_price=10,
        price_unit="kg",
        as_of=date(2026, 1, 1),
    )
    assert result["recommended_order_qty"] is None
    assert result["status"] == "Needs physical count"
    assert result["eligible_incoming_qty"] == 0
    assert any("unit 'm3'" in warning for warning in result["warnings"])
    assert any("not initialized" in warning for warning in result["warnings"])


def test_minimum_order_multiple_and_maximum_stock_conflict():
    adjusted = calculate_replenishment(
        unit="pieces", current_stock=0, current_stock_basis="operational ledger",
        lead_time_days=5, safety_stock_days=0, historical_daily_rate=2,
        minimum_order_qty=12, order_multiple=5, as_of=date(2026, 1, 1),
    )
    assert adjusted["net_requirement_before_constraints"] == Decimal("10")
    assert adjusted["recommended_order_qty"] == Decimal("15")

    conflict = calculate_replenishment(
        unit="pieces", current_stock=0, current_stock_basis="operational ledger",
        lead_time_days=5, safety_stock_days=0, historical_daily_rate=2,
        maximum_stock_qty=5, as_of=date(2026, 1, 1),
    )
    assert conflict["recommended_order_qty"] == Decimal("10")
    assert conflict["capacity_conflict"] is True
    assert conflict["status"] == "Capacity conflict"


def test_historical_daily_rate_uses_observed_intervals_not_zero_fill():
    frame = pd.DataFrame({
        "project_site_id": ["Site A", "Site A", "Site A"],
        "material": ["Cement", "Cement", "Cement"],
        "date": pd.to_datetime(["2025-01-01", "2025-01-08", "2025-01-15"]),
        "consumption_qty": [10, 14, 1000],
    })
    rate, warnings = estimate_historical_daily_rate(frame, site="Site A", material="Cement")
    assert rate == Decimal(str((10 / 7 + 14 / 7) / 2))
    assert any("fewer than the 13 interval target" in warning for warning in warnings)


def test_replenishment_review_persists_without_creating_a_purchase_order(seeded_db):
    db, _ = seeded_db
    recommendation = calculate_replenishment(
        unit="50-kg bags",
        current_stock=100,
        current_stock_basis="operational ledger",
        lead_time_days=4,
        safety_stock_days=7,
        historical_daily_rate=5,
        as_of=date(2026, 1, 1),
        unit_price=380,
        price_unit="50-kg bags",
    )
    with db.session() as session:
        site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == "Jakhan, Dehradun"))
        material = session.scalar(select(Material).where(Material.name == "Cement"))
        record = save_replenishment_review(
            session,
            review_key="review-example-1",
            site_id=site.id,
            material_id=material.id,
            decision="Accepted",
            recommendation=recommendation,
            accepted_quantity=recommendation["recommended_order_qty"],
            reviewer_note="Reviewed in a test database.",
        )
        session.commit()
        assert record.status == "Accepted"
        assert session.scalar(select(func.count(PurchaseOrder.id))) == 0
    with db.session() as session:
        assert session.scalar(select(func.count(ReplenishmentReview.id))) == 1
