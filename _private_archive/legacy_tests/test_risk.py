from __future__ import annotations

from datetime import date

import pytest

from inventory_app.risk import calculate_inventory_risk


def _risk(**overrides):
    inputs = {
        "on_hand_stock": 100.0,
        "forecast_weekly_demand": 70.0,
        "forecast_error_sigma": 8.0,
        "lead_time_days": 7,
        "order_cost_inr": 500.0,
        "unit_price_inr": 400.0,
        "interval_lower_weekly": 55.0,
        "interval_upper_weekly": 85.0,
        "as_of": date(2026, 11, 3),
    }
    inputs.update(overrides)
    return calculate_inventory_risk(**inputs)


def test_high_stockout_precedes_medium_and_gives_order_now():
    result = _risk(on_hand_stock=10)
    assert result["risk_level"] == "HIGH"
    assert result["suggestion"]["action"] == "Order now"
    assert result["suggestion"]["quantity"] > 0
    assert result["suggestion"]["order_by_date"] == "2026-11-03"
    assert result["suggestion"]["expected_arrival_date"] == "2026-11-10"


def test_exact_safety_stock_is_not_below_safety_stock():
    safety = 1.6448536269514722 * 2.0
    result = _risk(on_hand_stock=safety, forecast_weekly_demand=0, forecast_error_sigma=2, lead_time_days=7,
                   interval_lower_weekly=0, interval_upper_weekly=0)
    assert result["on_hand_stock"] == pytest.approx(result["safety_stock"])
    assert result["risk_level"] == "MEDIUM"


def test_exact_reorder_point_is_medium():
    result = _risk(on_hand_stock=70, forecast_weekly_demand=70, forecast_error_sigma=0, lead_time_days=7,
                   interval_lower_weekly=70, interval_upper_weekly=70)
    assert result["on_hand_stock"] == result["reorder_point"]
    assert result["risk_level"] == "MEDIUM"


def test_zero_demand_has_undefined_cover_and_hold_suggestion():
    result = _risk(on_hand_stock=0, forecast_weekly_demand=0, forecast_error_sigma=0, lead_time_days=7,
                   interval_lower_weekly=0, interval_upper_weekly=0)
    assert result["days_of_cover"] is None
    assert result["risk_level"] == "LOW"
    assert result["suggestion"]["action"] == "Hold"
    assert result["order_quantity"] == 0


@pytest.mark.parametrize("stock,status", [(None, "needs_stock_count"), (-1, "invalid_stock")])
def test_missing_or_negative_stock_is_high_and_withholds_quantity(stock, status):
    result = _risk(on_hand_stock=stock)
    assert result["status"] == status
    assert result["risk_level"] == "HIGH"
    assert result["suggestion"]["quantity"] == 0


def test_zero_lead_time_is_supported_and_arrival_is_same_day():
    result = _risk(on_hand_stock=0, forecast_weekly_demand=70, forecast_error_sigma=0, lead_time_days=0,
                   interval_lower_weekly=70, interval_upper_weekly=70)
    assert result["lead_time_weeks"] == 0
    assert result["suggestion"]["expected_arrival_date"] == "2026-11-03"


def test_very_wide_interval_is_medium_and_overstock_is_separate():
    result = _risk(on_hand_stock=1000, interval_lower_weekly=0, interval_upper_weekly=200)
    assert result["risk_level"] == "MEDIUM"
    assert result["overstock"] is True
    assert result["suggestion"]["action"] == "Reduce next order"
    assert result["suggestion"]["quantity"] == 0


@pytest.mark.parametrize("field,value", [("forecast_weekly_demand", -1), ("lead_time_days", -1), ("order_cost_inr", -1)])
def test_negative_required_input_is_rejected(field, value):
    with pytest.raises(ValueError):
        _risk(**{field: value})


def test_pack_rounding_and_eoq_are_visible_in_suggestion():
    result = _risk(on_hand_stock=150, forecast_error_sigma=12, lead_time_days=14, pack_size=50)
    assert result["order_quantity"] % 50 == 0
    assert result["order_quantity"] >= result["eoq_quantity"]
    assert result["suggestion"]["quantity"] == result["order_quantity"]
    assert result["suggestion"]["reason"]
