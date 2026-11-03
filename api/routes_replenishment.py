"""Live-ledger replenishment calculation and alert endpoints."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.dependencies import get_database, get_session
from api.errors import APIProblem
from api.routes_forecasting import _selected_pair
from api.schemas import ReplenishmentCalculate
from inventory_app.forecast_sources import ForecastSourceError, resolve_forecast_source
from inventory_app.forecasting import (
    MAX_WEEKLY_FORECAST_HORIZON_DAYS,
    ForecastUnavailable,
    assess_demand_source_recency,
    load_or_naive_assessment,
)
from inventory_app.inventory import get_current_balance, local_today
from inventory_app.reorder import get_reorder_rule, stock_reorder_status
from inventory_app.replenishment import estimate_historical_daily_rate
from inventory_app.risk import calculate_inventory_risk, material_order_parameters
from inventory_app.procurement import eligible_incoming_for_material

router = APIRouter(prefix="/api", tags=["replenishment"])


def _result(
    *,
    status: str,
    site: str,
    material: str,
    unit: str,
    source_label: str,
    source_kind: str,
    source_details: dict,
    source_recency: dict | None,
    current_stock,
    reorder_status: dict,
    lead_time_days: int | None,
    safety_stock_days: int | None,
    recommendation: dict | None = None,
    risk: dict | None = None,
    warnings: list[str] | None = None,
    model_name: str | None = None,
    daily_rate=None,
    daily_rate_warnings: list[str] | None = None,
):
    return {
        "status": status,
        "site": site,
        "material": material,
        "unit": unit,
        "source_label": source_label,
        "source_kind": source_kind,
        "source_details": source_details,
        "source_freshness": source_recency,
        "current_stock": float(current_stock) if current_stock is not None else None,
        "stock_basis": "operational ledger",
        "reorder": {
            **reorder_status,
            "current_stock": float(reorder_status["current_stock"]) if reorder_status["current_stock"] is not None else None,
            "reorder_point_qty": float(reorder_status["reorder_point_qty"]) if reorder_status["reorder_point_qty"] is not None else None,
        },
        "lead_time_days": lead_time_days,
        "safety_stock_days": safety_stock_days,
        "historical_daily_rate": float(daily_rate) if daily_rate is not None else None,
        "daily_rate_warnings": daily_rate_warnings or [],
        "model_name": model_name,
        "risk": risk,
        "warnings": warnings or [],
        "recommendation": recommendation,
    }


def _risk_result(
    material: Material,
    *,
    on_hand: float | None,
    demand: float | None = None,
    error_sigma: float | None = None,
    lead_time_days: int | None,
    service_level: float,
    as_of,
    interval_lower: float | None = None,
    interval_upper: float | None = None,
    incoming_qty: float = 0.0,
    minimum_order_qty: float = 0.0,
    pack_size: float | None = None,
):
    params = material_order_parameters(material.name, unit_price_inr=material.benchmark_unit_price_inr)
    return calculate_inventory_risk(
        on_hand_stock=on_hand,
        forecast_weekly_demand=demand,
        forecast_error_sigma=error_sigma,
        lead_time_days=lead_time_days,
        order_cost_inr=params["order_cost_inr"],
        unit_price_inr=params["unit_price_inr"],
        interval_lower_weekly=interval_lower,
        interval_upper_weekly=interval_upper,
        incoming_qty=incoming_qty,
        minimum_order_qty=minimum_order_qty,
        pack_size=pack_size or params["pack_size"],
        service_level=service_level,
        holding_rate=params["holding_rate"],
        as_of=as_of,
    )


@router.post("/replenishment/calculate")
def calculate_replenishment_api(
    body: ReplenishmentCalculate,
    request: Request,
    session: Session = Depends(get_session),
):
    site, material = _selected_pair(session, body.site_id, body.material_id)
    try:
        source_frame, source_kind, source_label, source_details = resolve_forecast_source(
            session,
            site=site.identifier,
            material=material.name,
            frequency="weekly",
            requested_source=body.source,
        )
    except ForecastSourceError as exc:
        raise APIProblem(409, "operational_sales_history_insufficient", str(exc), {
            "observed_periods": exc.observed_periods,
            "required_periods": exc.required_periods,
            "source_label_if_auto": "Construction Materials Dehradun Dataset",
        }) from exc

    today = local_today()
    operational_stock = get_current_balance(session, site.id, material.id, as_of=today)
    reorder = stock_reorder_status(session, site.id, material.id, as_of=today)
    rule = get_reorder_rule(session, site.id, material.id)

    lead_time = body.lead_time_days or (rule.lead_time_days if rule and rule.is_active else None) or material.default_lead_time_days
    safety_days = body.safety_stock_days
    if safety_days is None:
        safety_days = (rule.safety_stock_days if rule and rule.is_active and rule.safety_stock_days is not None else material.safety_stock_days)

    recency = assess_demand_source_recency(
        source_frame,
        site=site.identifier,
        material=material.name,
        as_of=today,
    )
    if operational_stock is None:
        return _result(
            status="needs_physical_count",
            site=site.identifier,
            material=material.name,
            unit=material.unit,
            source_label=source_label,
            source_kind=source_kind,
            source_details=source_details,
            source_recency=recency,
            current_stock=None,
            reorder_status=reorder,
            lead_time_days=lead_time,
            safety_stock_days=safety_days,
            risk=_risk_result(material, on_hand=None, lead_time_days=lead_time, service_level=body.service_level, as_of=today),
            warnings=["No operational opening count is recorded. A historical stock value is never substituted."],
        )
    if lead_time is None:
        return _result(
            status="lead_time_required",
            site=site.identifier,
            material=material.name,
            unit=material.unit,
            source_label=source_label,
            source_kind=source_kind,
            source_details=source_details,
            source_recency=recency,
            current_stock=operational_stock,
            reorder_status=reorder,
            lead_time_days=None,
            safety_stock_days=safety_days,
            risk=_risk_result(material, on_hand=operational_stock, lead_time_days=None, service_level=body.service_level, as_of=today),
            warnings=["Enter a planning lead-time assumption or configure one on the site/material reorder rule."],
        )
    if lead_time > MAX_WEEKLY_FORECAST_HORIZON_DAYS:
        return _result(
            status="lead_time_exceeds_forecast_horizon",
            site=site.identifier,
            material=material.name,
            unit=material.unit,
            source_label=source_label,
            source_kind=source_kind,
            source_details=source_details,
            source_recency=recency,
            current_stock=operational_stock,
            reorder_status=reorder,
            lead_time_days=lead_time,
            safety_stock_days=safety_days,
            risk=_risk_result(material, on_hand=operational_stock, lead_time_days=lead_time, service_level=body.service_level, as_of=today),
            warnings=[f"Lead time exceeds the supported weekly forecast horizon of {MAX_WEEKLY_FORECAST_HORIZON_DAYS} days; no numeric order recommendation is shown."],
        )
    if not recency["is_current"]:
        latest = recency["latest_observation_date"]
        age = recency["age_days"]
        if latest is None:
            warning = "No usable dated demand observation exists for this source; no current replenishment recommendation is shown."
        elif age is not None and age < 0:
            warning = f"The latest valid observation ({latest}) is after today ({today}); verify the source dates."
        else:
            warning = f"Dataset coverage is outside the current-planning window: latest observation {latest} is {age} days old; the limit is {recency['max_age_days']} days."
        return _result(
            status="stale_demand_source",
            site=site.identifier,
            material=material.name,
            unit=material.unit,
            source_label=source_label,
            source_kind=source_kind,
            source_details=source_details,
            source_recency=recency,
            current_stock=operational_stock,
            reorder_status=reorder,
            lead_time_days=lead_time,
            safety_stock_days=safety_days,
            risk=_risk_result(material, on_hand=operational_stock, lead_time_days=lead_time, service_level=body.service_level, as_of=today),
            warnings=[warning, "Model evaluation remains available; no numeric replenishment recommendation is shown until the source is current."],
        )

    daily_rate, rate_warnings = estimate_historical_daily_rate(
        source_frame,
        site=site.identifier,
        material=material.name,
    )
    if daily_rate is None:
        return _result(
            status="demand_rate_unavailable",
            site=site.identifier,
            material=material.name,
            unit=material.unit,
            source_label=source_label,
            source_kind=source_kind,
            source_details=source_details,
            source_recency=recency,
            current_stock=operational_stock,
            reorder_status=reorder,
            lead_time_days=lead_time,
            safety_stock_days=safety_days,
            risk=_risk_result(material, on_hand=operational_stock, lead_time_days=lead_time, service_level=body.service_level, as_of=today),
            warnings=rate_warnings + ["A supported historical daily-rate estimate is unavailable; no numeric recommendation is shown."],
            daily_rate_warnings=rate_warnings,
        )

    database = get_database(request)
    forecast_params = {
        "site": site.identifier,
        "material": material.name,
        "frequency": "weekly",
        "horizon_days": int(lead_time),
        "source_label": source_label,
    }
    try:
        assessment = load_or_naive_assessment(database, source_frame, **forecast_params)
    except ForecastUnavailable as exc:
        raise APIProblem(422, "forecast_unavailable", str(exc), {"source_label": source_label}) from exc

    model_name = assessment["best_model"]
    forecast_frame = assessment["forecasts"][model_name]
    incoming = eligible_incoming_for_material(session, site.id, material.id)
    if body.incoming_quantity is not None and body.incoming_quantity > 0:
        incoming.append({
            "quantity": body.incoming_quantity,
            "unit": material.unit,
            "expected_date": body.incoming_date,
            "status": "Confirmed",
            "reference": body.incoming_reference or "User-confirmed scenario",
        })
    minimum_order = rule.minimum_order_qty if rule and rule.is_active and rule.minimum_order_qty is not None else material.minimum_order_qty
    order_multiple = rule.order_multiple if rule and rule.is_active and rule.order_multiple is not None else material.order_multiple
    maximum_stock = rule.maximum_stock_qty if rule and rule.is_active and rule.maximum_stock_qty is not None else material.maximum_stock_qty
    lead_arrival = today + timedelta(days=int(lead_time))
    eligible_incoming_qty = 0.0
    for delivery in incoming:
        expected_date = delivery.get("expected_date")
        if isinstance(expected_date, str):
            try:
                expected_date = date.fromisoformat(expected_date[:10])
            except ValueError:
                expected_date = None
        if (
            delivery.get("unit", material.unit) == material.unit
            and delivery.get("status") in {"Approved", "Partially received", "Confirmed"}
            and expected_date is not None
            and expected_date <= lead_arrival
        ):
            eligible_incoming_qty += float(delivery.get("quantity", 0))

    forecast_values = forecast_frame["forecast"].astype(float).clip(lower=0).tolist()
    weekly_demand = float(sum(forecast_values) / len(forecast_values)) if forecast_values else None
    selected_metric = next(row for row in assessment["metrics"] if row["model"] == model_name)
    interval_radius = selected_metric.get("interval_radius")
    error_sigma = selected_metric.get("forecast_error_sigma")
    if error_sigma is None:
        error_sigma = float(interval_radius) / 1.6448536269514722 if interval_radius is not None else 0.0
    interval_lower = float(forecast_frame["lower"].mean()) if "lower" in forecast_frame else None
    interval_upper = float(forecast_frame["upper"].mean()) if "upper" in forecast_frame else None
    minimum_order = float(rule.minimum_order_qty if rule and rule.is_active and rule.minimum_order_qty is not None else material.minimum_order_qty or 0)
    order_multiple = float(rule.order_multiple if rule and rule.is_active and rule.order_multiple is not None else material.order_multiple or 0)
    maximum_stock = rule.maximum_stock_qty if rule and rule.is_active and rule.maximum_stock_qty is not None else material.maximum_stock_qty
    order_pack = order_multiple if order_multiple > 0 else None
    risk = _risk_result(
        material,
        on_hand=float(operational_stock),
        demand=weekly_demand,
        error_sigma=float(error_sigma),
        lead_time_days=int(lead_time),
        service_level=body.service_level,
        as_of=today,
        interval_lower=interval_lower,
        interval_upper=interval_upper,
        incoming_qty=eligible_incoming_qty,
        minimum_order_qty=minimum_order,
        pack_size=order_pack,
    )
    recommended_quantity = float(risk["order_quantity"])
    capacity_conflict = maximum_stock is not None and float(operational_stock) + eligible_incoming_qty + recommended_quantity > float(maximum_stock)
    if capacity_conflict:
        risk["suggestion"]["reason"] += " The quantity exceeds configured maximum stock; review the capacity rule before ordering."
    estimated_cost = (
        recommended_quantity * float(material.benchmark_unit_price_inr)
        if material.benchmark_unit_price_inr is not None
        else None
    )
    recommendation = {
        "status": risk["risk_level"].title(),
        "unit": material.unit,
        "current_stock": float(operational_stock),
        "current_stock_basis": "operational ledger",
        "lead_time_days": int(lead_time),
        "lead_time_demand": risk["lead_time_demand"],
        "forecast_values": forecast_values,
        "forecast_step_days": 7,
        "demand_basis": "weekly model forecast",
        "historical_daily_rate": float(daily_rate),
        "safety_stock_days": int(safety_days),
        "safety_stock_qty": risk["safety_stock"],
        "eligible_incoming_qty": eligible_incoming_qty,
        "excluded_late_incoming_qty": 0.0,
        "eligible_incoming_lines": incoming,
        "reorder_point_qty": risk["reorder_point"],
        "net_requirement_before_constraints": max(0.0, float(risk["target_stock_level"] or 0.0) - float(operational_stock) - eligible_incoming_qty),
        "recommended_order_qty": recommended_quantity,
        "minimum_order_qty": minimum_order,
        "order_multiple": float(order_pack or 0),
        "maximum_stock_qty": maximum_stock,
        "capacity_conflict": capacity_conflict,
        "expected_arrival_date": risk["suggestion"]["expected_arrival_date"],
        "unit_price": material.benchmark_unit_price_inr,
        "price_basis": material.price_basis,
        "estimated_order_cost_inr": round(estimated_cost, 2) if estimated_cost is not None else None,
        "provisional": False,
        "warnings": [],
        "explanation": "Shared risk calculation: lead-time demand + service-level safety stock; order-up-to/EOQ candidate rounded to the configured pack.",
        "risk": risk,
    }
    return _result(
        status=risk["risk_level"].title(),
        site=site.identifier,
        material=material.name,
        unit=material.unit,
        source_label=source_label,
        source_kind=source_kind,
        source_details=source_details,
        source_recency=recency,
        current_stock=operational_stock,
        reorder_status=reorder,
        lead_time_days=int(lead_time),
        safety_stock_days=int(safety_days),
        recommendation=recommendation,
        risk=risk,
        warnings=assessment["warnings"] + rate_warnings,
        model_name=model_name,
        daily_rate=daily_rate,
        daily_rate_warnings=rate_warnings,
    )
