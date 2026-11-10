"""Lead-time-aware replenishment with explicit inputs and auditable arithmetic."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from typing import Any, Iterable

import pandas as pd

from inventory_app.inventory import decimal_value
from inventory_app.models import ReplenishmentReview
import json

# These are eligible delivery inputs, not necessarily purchase-order records. "Confirmed"
# supports an explicitly user-entered delivery scenario in the focused planner.
APPROVED_PIPELINE_STATUSES = {"Approved", "Partially received", "Confirmed"}


def estimate_historical_daily_rate(
    history: pd.DataFrame,
    *,
    site: str,
    material: str,
    lookback_intervals: int = 13,
) -> tuple[Decimal | None, list[str]]:
    """Estimate a daily run-rate from recorded observation intervals, without zero filling."""
    warnings: list[str] = []
    if history.empty:
        return None, ["No historical observations are available for a demand-rate estimate."]
    series = history.loc[
        (history["project_site_id"] == site) & (history["material"] == material),
        ["date", "consumption_qty"],
    ].copy()
    if len(series) < 2:
        return None, ["At least two dated observations are required to estimate a consumption rate."]
    series["date"] = pd.to_datetime(series["date"], errors="coerce")
    series["consumption_qty"] = pd.to_numeric(series["consumption_qty"], errors="coerce")
    series = series.dropna().sort_values("date").drop_duplicates("date", keep="last")
    days = series["date"].diff().dt.total_seconds().div(86400)
    # A row's incoming/consumption quantities roll forward into the next opening
    # balance, so its consumption is paired with the following observed interval.
    prior_consumption = series["consumption_qty"].shift(1)
    rates = (prior_consumption / days).where(days.between(3, 10, inclusive="both")).dropna()
    if rates.empty:
        return None, ["No adjacent observation intervals in the expected 3–10 day range; the rate was not inferred."]
    recent = rates.tail(lookback_intervals)
    if len(rates) < lookback_intervals:
        warnings.append(f"Daily run-rate uses {len(rates)} comparable interval(s), fewer than the {lookback_intervals} interval target.")
    if (days > 10).any():
        warnings.append("Long gaps were excluded rather than treated as zero consumption.")
    rate = Decimal(str(float(recent.mean())))
    if rate < 0:
        return None, warnings + ["The estimated historical daily rate is invalid."]
    return rate, warnings


def _as_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def calculate_replenishment(
    *,
    unit: str,
    current_stock: Decimal | int | float | str | None,
    current_stock_basis: str,
    lead_time_days: int,
    safety_stock_days: int,
    historical_daily_rate: Decimal | int | float | str | None,
    forecast_values: Iterable[Decimal | int | float] | None = None,
    forecast_step_days: int = 7,
    incoming_deliveries: Iterable[dict[str, Any]] = (),
    unit_price: Decimal | int | float | str | None = None,
    price_unit: str | None = None,
    price_basis: str | None = None,
    minimum_order_qty: Decimal | int | float | str = 0,
    order_multiple: Decimal | int | float | str = 0,
    maximum_stock_qty: Decimal | int | float | str | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Compute a recommendation using explicit, unit-consistent stock and demand inputs.

    Policy: lead-time demand is forecast where available; safety stock is a separate
    historical mean daily demand × configured safety-stock days. Eligible pipeline
    is subtracted only for approved/part-received lines due no later than the new
    supplier lead-time window. An unknown stock basis prevents a numeric order.
    """
    warnings: list[str] = []
    today = as_of or date.today()
    if lead_time_days <= 0:
        raise ValueError("Supplier lead time must be a positive number of days.")
    if safety_stock_days < 0:
        raise ValueError("Safety-stock days cannot be negative.")
    if forecast_step_days <= 0:
        raise ValueError("Forecast interval must be greater than zero days.")
    rate = decimal_value(historical_daily_rate, field="historical daily demand") if historical_daily_rate is not None else None
    stock = decimal_value(current_stock, field="current stock") if current_stock is not None else None
    if stock is not None and stock < 0:
        warnings.append("Current stock is negative; reconcile the operational ledger before ordering.")
    if current_stock_basis != "operational ledger":
        warnings.append(f"Stock input is provisional ({current_stock_basis}); verify with a physical count.")

    lead_demand = Decimal("0")
    forecast = list(forecast_values) if forecast_values is not None else []
    forecast_inputs: list[Decimal] = []
    if forecast:
        remaining_days = Decimal(lead_time_days)
        for raw_value in forecast:
            if remaining_days <= 0:
                break
            value = decimal_value(raw_value, field="forecast demand")
            if value < 0:
                warnings.append("Negative forecast was clipped to zero for replenishment arithmetic.")
                value = Decimal("0")
            forecast_inputs.append(value)
            covered = min(remaining_days, Decimal(forecast_step_days))
            lead_demand += value * covered / Decimal(forecast_step_days)
            remaining_days -= covered
        if remaining_days > 0:
            if rate is None:
                warnings.append("Forecast does not cover the full supplier lead time and no historical run-rate is available for the remainder.")
            else:
                lead_demand += rate * remaining_days
                warnings.append("The lead-time window exceeds the forecast horizon; the uncovered days use the historical daily run-rate.")
        demand_basis = f"Forecast, prorated to {lead_time_days} lead-time days"
    elif rate is not None:
        lead_demand = rate * Decimal(lead_time_days)
        demand_basis = "Historical daily run-rate × lead time (forecast unavailable)"
        warnings.append("No compatible forecast was supplied; lead-time demand uses the historical run-rate.")
    else:
        demand_basis = "Unavailable"
        warnings.append("Neither forecast nor historical demand rate is available.")

    safety_stock = (rate * Decimal(safety_stock_days)) if rate is not None else Decimal("0")
    if rate is None and safety_stock_days:
        warnings.append("Safety-stock quantity is zero because a reliable historical daily rate is unavailable.")
    if lead_demand == 0 and (rate is None or rate == 0):
        warnings.append("Observed demand is zero or unavailable; the demand-based order quantity may be zero. Check source coverage before acting.")
    if stock == 0:
        warnings.append("Current usable stock is zero; the recommendation uses a verified zero ledger balance.")
    due_by = today + timedelta(days=lead_time_days)
    eligible_incoming = Decimal("0")
    eligible_lines: list[dict[str, Any]] = []
    excluded_incoming = Decimal("0")
    for delivery in incoming_deliveries:
        qty = decimal_value(delivery.get("quantity", 0), field="incoming quantity")
        delivery_unit = delivery.get("unit") or unit
        status = str(delivery.get("status") or "")
        expected_date = _as_date(delivery.get("expected_date"))
        if delivery_unit != unit:
            warnings.append(f"Incoming line {delivery.get('reference', '')!r} has unit '{delivery_unit}' and was excluded.")
            continue
        eligible = status in APPROVED_PIPELINE_STATUSES and expected_date is not None and expected_date <= due_by and qty > 0
        if eligible:
            eligible_incoming += qty
            eligible_lines.append({
                "reference": delivery.get("reference", ""),
                "quantity": qty,
                "unit": unit,
                "expected_date": expected_date,
                "status": status,
            })
        else:
            if status in APPROVED_PIPELINE_STATUSES and expected_date is not None and expected_date > due_by:
                excluded_incoming += qty
            if status in APPROVED_PIPELINE_STATUSES and expected_date is None and qty > 0:
                warnings.append(f"Approved incoming line {delivery.get('reference', '')!r} has no expected delivery date and was excluded.")

    min_qty = decimal_value(minimum_order_qty, field="minimum order quantity")
    multiple = decimal_value(order_multiple, field="order multiple")
    max_stock = decimal_value(maximum_stock_qty, field="maximum stock") if maximum_stock_qty is not None else None
    if min_qty < 0 or multiple < 0 or (max_stock is not None and max_stock < 0):
        raise ValueError("Order constraints cannot be negative.")

    net_before_constraints: Decimal | None = None
    recommended: Decimal | None = None
    capacity_conflict = False
    if stock is None:
        warnings.append("Operational opening stock is not initialized; a quantity recommendation cannot be stated as current-stock-aware.")
        status = "Needs physical count"
    elif stock < 0:
        status = "Ledger review required"
    else:
        net_before_constraints = max(Decimal("0"), lead_demand + safety_stock - stock - eligible_incoming)
        recommended = net_before_constraints
        if recommended > 0 and min_qty > 0:
            recommended = max(recommended, min_qty)
        if recommended > 0 and multiple > 0:
            recommended = (recommended / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple
        # Inventory and procurement quantities are persisted as Numeric(..., 4).
        # Round upward so DB precision cannot turn a recommendation into a short PO.
        if recommended > 0:
            recommended = recommended.quantize(Decimal("0.0001"), rounding=ROUND_CEILING)
        if max_stock is not None and stock + eligible_incoming + recommended > max_stock:
            capacity_conflict = True
            warnings.append(
                f"Configured maximum stock ({max_stock} {unit}) is below the post-order balance required by this recommendation. Resolve the cap/need conflict before placing an order."
            )
            status = "Capacity conflict"
        elif recommended == 0:
            status = "Covered"
        elif stock + eligible_incoming < lead_demand:
            status = "At risk"
        else:
            status = "Reorder"

    price: Decimal | None = None
    estimated_cost: Decimal | None = None
    if unit_price is not None and price_unit == unit:
        price = decimal_value(unit_price, field="unit price")
        if price >= 0 and recommended is not None:
            estimated_cost = (recommended * price).quantize(Decimal("0.01"))
        if price_basis and "estimate" in price_basis.lower():
            warnings.append(f"Cost uses {price_basis}; it is an estimate, not audited expenditure.")
    elif unit_price is not None:
        warnings.append("Unit price unit is incompatible or unknown; estimated cost was omitted.")
    else:
        warnings.append("No compatible unit-price reference is configured; estimated cost is unavailable.")

    is_provisional = current_stock_basis != "operational ledger"
    return {
        "status": status,
        "site": None,
        "material": None,
        "unit": unit,
        "current_stock": stock,
        "current_stock_basis": current_stock_basis,
        "lead_time_days": lead_time_days,
        "lead_time_demand": lead_demand,
        "forecast_values": forecast_inputs,
        "forecast_step_days": forecast_step_days,
        "demand_basis": demand_basis,
        "historical_daily_rate": rate,
        "safety_stock_days": safety_stock_days,
        "safety_stock_qty": safety_stock,
        "eligible_incoming_qty": eligible_incoming,
        "excluded_late_incoming_qty": excluded_incoming,
        "eligible_incoming_lines": eligible_lines,
        "reorder_point_qty": lead_demand + safety_stock,
        "net_requirement_before_constraints": net_before_constraints,
        "recommended_order_qty": recommended,
        "minimum_order_qty": min_qty,
        "order_multiple": multiple,
        "maximum_stock_qty": max_stock,
        "capacity_conflict": capacity_conflict,
        "expected_arrival_date": due_by,
        "unit_price": price,
        "price_basis": price_basis,
        "estimated_order_cost_inr": estimated_cost,
        "provisional": is_provisional,
        "warnings": list(dict.fromkeys(warnings)),
        "explanation": (
            "max(0, lead-time demand + safety stock − current usable stock − eligible incoming), "
            "then apply the configured minimum order and order multiple. Safety stock is historical mean daily demand × safety-stock days."
        ),
    }


def save_replenishment_review(
    session,
    *,
    review_key: str,
    site_id: int,
    material_id: int,
    decision: str,
    recommendation: dict[str, Any],
    accepted_quantity: Decimal | int | float | str | None,
    reviewer_note: str | None = None,
):
    """Persist a review decision; accepting never submits a purchase order."""
    from sqlalchemy import select
    if decision not in {"Accepted", "Adjusted", "Rejected"}:
        raise ValueError("Decision must be Accepted, Adjusted or Rejected.")
    if not review_key.strip():
        raise ValueError("A review idempotency key is required.")
    if session.scalar(select(ReplenishmentReview.id).where(ReplenishmentReview.review_key == review_key)):
        raise ValueError("This replenishment review has already been saved.")
    recommended = recommendation.get("recommended_order_qty")
    recommended = decimal_value(recommended) if recommended is not None else None
    accepted = decimal_value(accepted_quantity) if accepted_quantity is not None else None
    if decision == "Rejected":
        accepted = None
    elif accepted is None or accepted < 0:
        raise ValueError("An accepted quantity must be zero or greater.")
    elif recommendation.get("capacity_conflict") and accepted > 0:
        raise ValueError("Resolve the maximum-stock conflict before accepting an order quantity.")
    unit_price = recommendation.get("unit_price")
    estimated_cost = accepted * Decimal(unit_price) if accepted is not None and unit_price is not None else None
    record = ReplenishmentReview(
        review_key=review_key,
        site_id=site_id,
        material_id=material_id,
        status=decision,
        recommended_qty=recommended,
        accepted_qty=accepted,
        unit=recommendation.get("unit", ""),
        estimated_cost_inr=estimated_cost.quantize(Decimal("0.01")) if estimated_cost is not None else None,
        calculation_json=json.dumps(recommendation, default=lambda value: str(value), sort_keys=True),
        reviewer_note=reviewer_note.strip() if reviewer_note else None,
    )
    session.add(record)
    session.flush()
    return record
