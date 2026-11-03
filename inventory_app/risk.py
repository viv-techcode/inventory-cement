"""Shared inventory risk and purchase-suggestion calculation."""
from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import NormalDist
from typing import Any

from inventory_app.policy_config import DEFAULT_HOLDING_RATE, DEFAULT_REVIEW_PERIOD_WEEKS, DEFAULT_SERVICE_LEVEL, MAX_COVER_DAYS, ORDER_COST_BY_MATERIAL_CLASS, MATERIAL_CLASSES, ORDER_PACK_SIZES


def _finite(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _round_up(quantity: float, pack_size: float) -> float:
    if quantity <= 0:
        return 0.0
    pack = max(float(pack_size), 1e-9)
    return math.ceil((quantity - 1e-12) / pack) * pack


def calculate_inventory_risk(
    *,
    on_hand_stock: float | None,
    forecast_weekly_demand: float | None,
    forecast_error_sigma: float | None,
    lead_time_days: int | None,
    order_cost_inr: float,
    unit_price_inr: float | None,
    interval_lower_weekly: float | None = None,
    interval_upper_weekly: float | None = None,
    incoming_qty: float = 0.0,
    minimum_order_qty: float = 0.0,
    pack_size: float = 1.0,
    service_level: float = DEFAULT_SERVICE_LEVEL,
    holding_rate: float = DEFAULT_HOLDING_RATE,
    review_period_weeks: float = DEFAULT_REVIEW_PERIOD_WEEKS,
    max_cover_days: float = MAX_COVER_DAYS,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Compute risk, coverage, reorder point, and a rounded order suggestion.

    Risk precedence is High → Medium → Low. Overstock is an independent flag.
    Exactly at the reorder point is Medium; exact safety-stock equality is not
    by itself High, although insufficient days of cover can still take precedence.
    """
    today = as_of or date.today()
    if not 0 < float(service_level) < 1:
        raise ValueError("service_level must be strictly between 0 and 1.")
    if lead_time_days is not None and (not float(lead_time_days).is_integer() or int(lead_time_days) < 0):
        raise ValueError("lead_time_days must be a non-negative whole number.")
    for name, value in (
        ("forecast_weekly_demand", forecast_weekly_demand),
        ("forecast_error_sigma", forecast_error_sigma),
        ("order_cost_inr", order_cost_inr),
        ("incoming_qty", incoming_qty),
        ("minimum_order_qty", minimum_order_qty),
        ("pack_size", pack_size),
        ("holding_rate", holding_rate),
        ("review_period_weeks", review_period_weeks),
        ("max_cover_days", max_cover_days),
    ):
        if value is not None and _finite(value) and float(value) < 0:
            raise ValueError(f"{name} cannot be negative.")
    if not _finite(order_cost_inr):
        raise ValueError("order_cost_inr must be a finite number.")
    if pack_size == 0:
        raise ValueError("pack_size must be greater than zero.")
    if interval_lower_weekly is not None and not _finite(interval_lower_weekly):
        raise ValueError("interval_lower_weekly must be finite when provided.")
    if interval_upper_weekly is not None and not _finite(interval_upper_weekly):
        raise ValueError("interval_upper_weekly must be finite when provided.")
    if interval_lower_weekly is not None and interval_upper_weekly is not None and interval_lower_weekly > interval_upper_weekly:
        raise ValueError("Forecast interval lower bound cannot exceed upper bound.")

    lead_days = int(lead_time_days) if lead_time_days is not None else None
    demand = float(forecast_weekly_demand) if _finite(forecast_weekly_demand) else None
    sigma = float(forecast_error_sigma) if _finite(forecast_error_sigma) else 0.0
    stock = float(on_hand_stock) if _finite(on_hand_stock) else None
    incoming = float(incoming_qty) if _finite(incoming_qty) else 0.0
    z_score = NormalDist().inv_cdf(float(service_level))

    interval_width = None
    interval_relative_width = None
    if interval_lower_weekly is not None and interval_upper_weekly is not None:
        interval_width = max(0.0, float(interval_upper_weekly) - float(interval_lower_weekly))
        interval_relative_width = interval_width / max(demand or 0.0, 1.0)
    wide_interval = interval_relative_width is not None and interval_relative_width >= 1.0
    confidence = "wide" if interval_relative_width is not None and interval_relative_width >= 0.5 else "narrow"

    lead_weeks = (lead_days / 7.0) if lead_days is not None else None
    lead_time_demand = demand * lead_weeks if demand is not None and lead_weeks is not None else None
    safety_stock = z_score * sigma * math.sqrt(lead_weeks) if lead_weeks is not None else None
    reorder_point = lead_time_demand + safety_stock if lead_time_demand is not None and safety_stock is not None else None
    days_cover = (stock / (demand / 7.0)) if stock is not None and demand is not None and demand > 0 else None
    overstock = bool(days_cover is not None and days_cover > float(max_cover_days))

    missing = stock is None or demand is None or lead_days is None
    negative_stock = stock is not None and stock < 0
    if missing or negative_stock:
        level = "HIGH"
    elif demand == 0 and sigma == 0 and not wide_interval:
        level = "LOW"
    elif days_cover is not None and days_cover < lead_days:
        level = "HIGH"
    elif stock < safety_stock - 1e-9:
        level = "HIGH"
    elif stock <= reorder_point + 1e-9 or (days_cover is not None and days_cover <= lead_days * 1.25) or wide_interval:
        level = "MEDIUM"
    else:
        level = "LOW"

    status = "needs_stock_count" if stock is None else "invalid_stock" if negative_stock else "forecast_unavailable" if demand is None or lead_days is None else "ready"
    quantity = 0.0
    eoq = 0.0
    target_level = None
    if status == "ready" and level in {"HIGH", "MEDIUM"}:
        target_level = demand * (lead_weeks + float(review_period_weeks)) + safety_stock
        gap = max(0.0, target_level - max(stock, 0.0) - incoming)
        if _finite(unit_price_inr) and float(unit_price_inr) > 0 and holding_rate > 0:
            annual_demand = demand * 52.0
            eoq = math.sqrt(2.0 * annual_demand * float(order_cost_inr) / (float(unit_price_inr) * float(holding_rate)))
        raw_quantity = max(gap, eoq, float(minimum_order_qty))
        if raw_quantity > 0:
            quantity = _round_up(raw_quantity, float(pack_size))

    if missing:
        reason = "On-hand stock, demand forecast, or lead time is unavailable; verify inputs before ordering."
    elif negative_stock:
        reason = "Recorded on-hand stock is negative; reconcile the physical count and plan an immediate order."
    elif level == "HIGH":
        reason = f"Stock covers {days_cover:.0f} days; lead time is {lead_days} days." if days_cover is not None else "Stock is below safety stock; order now."
    elif wide_interval and level == "MEDIUM":
        reason = "Forecast interval is wide; review the demand plan before placing the suggested order."
    elif level == "MEDIUM":
        reason = f"Stock is at or near the reorder point; plan replenishment for lead time {lead_days} days."
    elif overstock:
        reason = f"Stock covers more than the {max_cover_days:g}-day overstock limit; reduce the next order."
    else:
        reason = "Stock is above the reorder point with comfortable coverage; no order is needed now."

    if status != "ready":
        action = "Order now" if level == "HIGH" else "Plan order"
        quantity = 0.0
        reduction = 0.0
        order_by = None
        arrival = None
    elif overstock and level != "HIGH":
        action = "Reduce next order"
        quantity = 0.0
        reduction = max(0.0, stock - float(max_cover_days) * demand / 7.0)
        order_by = None
        arrival = None
    elif level == "HIGH":
        action = "Order now"
        reduction = 0.0
        order_by = today
        arrival = today + timedelta(days=lead_days)
    elif level == "MEDIUM":
        action = "Order soon" if days_cover is not None and days_cover <= lead_days * 1.25 else "Plan order"
        reduction = 0.0
        wait_days = max(0, int(math.floor((days_cover or 0) - lead_days)))
        order_by = today + timedelta(days=wait_days)
        arrival = order_by + timedelta(days=lead_days)
    else:
        action = "Hold"
        reduction = 0.0
        order_by = None
        arrival = None

    return {
        "status": status,
        "risk_level": level,
        "overstock": overstock,
        "confidence": confidence,
        "service_level": float(service_level),
        "z_score": z_score,
        "on_hand_stock": stock,
        "forecast_weekly_demand": demand,
        "forecast_error_sigma": sigma,
        "lead_time_days": lead_days,
        "lead_time_weeks": lead_weeks,
        "lead_time_demand": lead_time_demand,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "days_of_cover": days_cover,
        "forecast_interval_width": interval_width,
        "forecast_interval_relative_width": interval_relative_width,
        "target_stock_level": target_level,
        "eoq_quantity": eoq,
        "order_quantity": quantity,
        "order_cost_inr": float(order_cost_inr),
        "suggestion": {
            "action": action,
            "quantity": quantity,
            "reduce_next_order_by": reduction,
            "order_by_date": order_by.isoformat() if order_by else None,
            "expected_arrival_date": arrival.isoformat() if arrival else None,
            "reason": reason,
            "confidence": confidence,
        },
    }


def material_order_parameters(material: str, *, unit_price_inr: float | None = None) -> dict[str, float]:
    """Return one configured pack size and order cost by material class."""
    material_class = MATERIAL_CLASSES.get(material, "general")
    return {
        "order_cost_inr": float(ORDER_COST_BY_MATERIAL_CLASS[material_class]),
        "pack_size": float(ORDER_PACK_SIZES.get(material, 1.0)),
        "holding_rate": DEFAULT_HOLDING_RATE,
        "unit_price_inr": float(unit_price_inr) if _finite(unit_price_inr) else 0.0,
    }
