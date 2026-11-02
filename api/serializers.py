"""Stable JSON shape helpers shared by API routes."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from inventory_app.models import Customer, Material, ProjectSite, ReorderRule, SalesRecord


def as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def as_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    return str(value)


def site_payload(site: ProjectSite) -> dict[str, Any]:
    return {
        "id": site.id,
        "identifier": site.identifier,
        "name": site.name,
        "city": site.city,
        "state": site.state,
        "project_type": site.project_type,
        "is_active": site.is_active,
        "notes": site.notes,
    }


def material_payload(material: Material) -> dict[str, Any]:
    return {
        "id": material.id,
        "name": material.name,
        "unit": material.unit,
        "is_active": material.is_active,
        "default_lead_time_days": material.default_lead_time_days,
        "safety_stock_days": material.safety_stock_days,
        "minimum_order_qty": as_number(material.minimum_order_qty),
        "order_multiple": as_number(material.order_multiple),
        "maximum_stock_qty": as_number(material.maximum_stock_qty),
        "benchmark_unit_price_inr": as_number(material.benchmark_unit_price_inr),
        "price_basis": material.price_basis,
        "notes": material.notes,
    }


def customer_payload(customer: Customer) -> dict[str, Any]:
    return {
        "id": customer.id,
        "name": customer.name,
        "contact_name": customer.contact_name,
        "email": customer.email,
        "phone": customer.phone,
        "is_active": customer.is_active,
        "notes": customer.notes,
        "source_tag": customer.source_tag,
    }


def reorder_rule_payload(rule: ReorderRule, *, site: ProjectSite, material: Material) -> dict[str, Any]:
    return {
        "id": rule.id,
        "site_id": rule.site_id,
        "site": site.identifier,
        "material_id": rule.material_id,
        "material": material.name,
        "unit": material.unit,
        "reorder_point_qty": as_number(rule.reorder_point_qty),
        "lead_time_days": rule.lead_time_days,
        "safety_stock_days": rule.safety_stock_days,
        "minimum_order_qty": as_number(rule.minimum_order_qty),
        "order_multiple": as_number(rule.order_multiple),
        "maximum_stock_qty": as_number(rule.maximum_stock_qty),
        "is_active": rule.is_active,
        "notes": rule.notes,
        "source_tag": rule.source_tag,
        "updated_at": as_iso(rule.updated_at),
    }


def sale_payload(
    sale: SalesRecord,
    *,
    site: ProjectSite,
    material: Material,
    customer: Customer | None,
) -> dict[str, Any]:
    return {
        "id": sale.id,
        "idempotency_key": sale.idempotency_key,
        "sale_date": as_iso(sale.sale_date),
        "site_id": site.id,
        "site": site.identifier,
        "material_id": material.id,
        "material": material.name,
        "customer_id": customer.id if customer else None,
        "customer": customer.name if customer else None,
        "quantity": as_number(sale.quantity),
        "unit": sale.unit,
        "unit_sale_price_inr": as_number(sale.unit_sale_price_inr),
        "revenue_inr": as_number(sale.revenue_inr),
        "unit_cost_basis_inr": as_number(sale.unit_cost_basis_inr),
        "cost_of_goods_sold_inr": as_number(sale.cost_of_goods_sold_inr),
        "gross_margin_inr": as_number(sale.gross_margin_inr),
        "margin_status": "Available" if sale.gross_margin_inr is not None else "Unavailable — no fully recorded FIFO cost basis",
        "reference": sale.reference,
        "notes": sale.notes,
        "source_tag": sale.source_tag,
        "inventory_transaction_id": sale.inventory_transaction_id,
        "created_at": as_iso(sale.created_at),
    }


def forecast_payload(
    assessment: dict[str, Any],
    *,
    source_kind: str,
    source_label: str,
    source_details: dict[str, Any],
    recency: dict[str, Any],
) -> dict[str, Any]:
    series = assessment["series"]
    feature_importance = []
    forest_payload = assessment.get("payloads", {}).get("Random Forest", {})
    forest = forest_payload.get("estimator") if isinstance(forest_payload, dict) else None
    if forest is not None:
        if hasattr(forest, "named_steps"):
            forest = list(forest.named_steps.values())[-1]
        importances = getattr(forest, "feature_importances_", None)
        if importances is not None and len(importances) == 6:
            names = ["lag_1", "lag_2", "lag_3", "lag_4", "rolling_mean_4", "rolling_std_4"]
            feature_importance = sorted(
                [
                    {"feature": name, "importance": as_number(value)}
                    for name, value in zip(names, importances)
                ],
                key=lambda row: row["importance"] or 0,
                reverse=True,
            )
    historical = []
    for day, value in zip(series.dates, series.values):
        historical.append({
            "date": day.date().isoformat(),
            "actual": as_number(value),
        })
    forecasts = {
        name: [
            {"date": as_iso(row["date"]), "forecast": as_number(row["forecast"])}
            for _, row in frame.iterrows()
        ]
        for name, frame in assessment["forecasts"].items()
    }
    holdouts = {
        name: [
            {
                "date": as_iso(row["date"]),
                "actual": as_number(row["actual"]),
                "predicted": as_number(row["predicted"]),
            }
            for _, row in frame.iterrows()
        ]
        for name, frame in assessment.get("holdout_predictions", {}).items()
    }
    return {
        "site": assessment["site"],
        "material": assessment["material"],
        "unit": assessment["unit"],
        "frequency": assessment["frequency"],
        "horizon_days": assessment["horizon_days"],
        "source_kind": source_kind,
        "source_label": source_label,
        "source_details": source_details,
        "source_observations": assessment["source_observations"],
        "calendar_periods": assessment["calendar_periods"],
        "training_start": assessment["training_start"],
        "training_end": assessment["training_end"],
        "evaluation_start": assessment["evaluation_start"],
        "evaluation_end": assessment["evaluation_end"],
        "best_model": assessment["best_model"],
        "cache_hit": bool(assessment.get("cache_hit")),
        "metrics": assessment["metrics"],
        "feature_importance": feature_importance,
        "warnings": assessment["warnings"],
        "freshness": {
            "latest_observation_date": as_iso(recency.get("latest_observation_date")),
            "as_of": as_iso(recency.get("as_of")),
            "age_days": recency.get("age_days"),
            "max_age_days": recency.get("max_age_days"),
            "is_current": bool(recency.get("is_current")),
        },
        "historical": historical,
        "forecasts": forecasts,
        "holdouts": holdouts,
    }
