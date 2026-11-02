"""Per-site/material reorder rules and current-stock alert helpers."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.inventory import decimal_value, get_current_balance, local_today
from inventory_app.models import Material, ProjectSite, ReorderRule


class ReorderRuleError(ValueError):
    pass


def get_reorder_rule(session: Session, site_id: int, material_id: int) -> ReorderRule | None:
    return session.scalar(
        select(ReorderRule).where(
            ReorderRule.site_id == site_id,
            ReorderRule.material_id == material_id,
        )
    )


def save_reorder_rule(
    session: Session,
    *,
    site_id: int,
    material_id: int,
    unit: str,
    reorder_point_qty: Decimal | int | float | str,
    lead_time_days: int | None = None,
    safety_stock_days: int | None = None,
    minimum_order_qty: Decimal | int | float | str | None = None,
    order_multiple: Decimal | int | float | str | None = None,
    maximum_stock_qty: Decimal | int | float | str | None = None,
    is_active: bool = True,
    notes: str | None = None,
    source_tag: str = "operator",
) -> ReorderRule:
    clean_source_tag = str(source_tag or "").strip()
    if not clean_source_tag or len(clean_source_tag) > 40:
        raise ReorderRuleError("source_tag must contain 1–40 characters.")
    site = session.get(ProjectSite, site_id)
    material = session.get(Material, material_id)
    if site is None or material is None or not site.is_active or not material.is_active:
        raise ReorderRuleError("Select an active site and material to configure a reorder rule.")
    if unit != material.unit:
        raise ReorderRuleError(f"Unit mismatch: {material.name} is configured in '{material.unit}'.")
    if lead_time_days is not None and not 1 <= int(lead_time_days) <= 365:
        raise ReorderRuleError("Lead time must be between 1 and 365 days, or left unset.")
    if safety_stock_days is not None and not 0 <= int(safety_stock_days) <= 90:
        raise ReorderRuleError("Safety-stock days must be between 0 and 90, or left unset.")

    point = decimal_value(reorder_point_qty, field="reorder point")
    if point < 0:
        raise ReorderRuleError("Reorder point cannot be negative.")
    optional_values: dict[str, Decimal | None] = {}
    for field, value in (
        ("minimum_order_qty", minimum_order_qty),
        ("order_multiple", order_multiple),
        ("maximum_stock_qty", maximum_stock_qty),
    ):
        amount = decimal_value(value, field=field.replace("_", " ")) if value is not None else None
        if amount is not None and amount < 0:
            raise ReorderRuleError(f"{field.replace('_', ' ').title()} cannot be negative.")
        optional_values[field] = amount

    rule = get_reorder_rule(session, site_id, material_id)
    if rule is None:
        rule = ReorderRule(site_id=site_id, material_id=material_id)
        session.add(rule)
    rule.reorder_point_qty = point
    rule.lead_time_days = int(lead_time_days) if lead_time_days is not None else None
    rule.safety_stock_days = int(safety_stock_days) if safety_stock_days is not None else None
    rule.minimum_order_qty = optional_values["minimum_order_qty"]
    rule.order_multiple = optional_values["order_multiple"]
    rule.maximum_stock_qty = optional_values["maximum_stock_qty"]
    rule.is_active = bool(is_active)
    rule.notes = str(notes).strip() if notes else None
    rule.source_tag = clean_source_tag
    session.flush()
    return rule


def stock_reorder_status(session: Session, site_id: int, material_id: int, *, as_of=None) -> dict[str, object]:
    day = as_of or local_today()
    stock = get_current_balance(session, site_id, material_id, as_of=day)
    rule = get_reorder_rule(session, site_id, material_id)
    if stock is None:
        status = "Not initialized"
        alert = False
    elif rule is None or not rule.is_active:
        status = "Rule not configured"
        alert = False
    elif stock <= Decimal(rule.reorder_point_qty):
        status = "Below reorder point"
        alert = True
    else:
        status = "At/above reorder point"
        alert = False
    return {
        "current_stock": stock,
        "reorder_point_qty": Decimal(rule.reorder_point_qty) if rule and rule.is_active else None,
        "rule_configured": bool(rule and rule.is_active),
        "status": status,
        "alert": alert,
    }
