"""Validated catalog maintenance for materials and project sites."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from inventory_app.inventory import decimal_value
from inventory_app.models import (
    HistoricalObservation,
    InventoryTransaction,
    Material,
    ProjectSite,
    PurchaseOrder,
    PurchaseOrderLine,
)


class CatalogError(ValueError):
    pass


def _clean_required(value: str, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise CatalogError(f"{label} is required.")
    return result


def create_material(
    session: Session,
    *,
    name: str,
    unit: str,
    benchmark_unit_price_inr: Decimal | int | float | str | None = None,
    default_lead_time_days: int | None = None,
    safety_stock_days: int = 7,
    minimum_order_qty: Decimal | int | float | str = 0,
    order_multiple: Decimal | int | float | str = 0,
    maximum_stock_qty: Decimal | int | float | str | None = None,
    notes: str | None = None,
) -> Material:
    clean_name = _clean_required(name, "Material name")
    clean_unit = _clean_required(unit, "Unit")
    if session.scalar(select(Material.id).where(func.lower(Material.name) == clean_name.lower())):
        raise CatalogError("A material with that name already exists.")
    if safety_stock_days < 0:
        raise CatalogError("Safety-stock days cannot be negative.")
    if default_lead_time_days is not None and default_lead_time_days <= 0:
        raise CatalogError("Supplier lead time must be greater than zero or left unset.")
    price = decimal_value(benchmark_unit_price_inr, field="unit price") if benchmark_unit_price_inr is not None else None
    if price is not None and price < 0:
        raise CatalogError("Unit price cannot be negative.")
    material = Material(
        name=clean_name,
        unit=clean_unit,
        benchmark_unit_price_inr=price,
        price_basis="user-configured reference price" if price is not None else "not configured",
        default_lead_time_days=default_lead_time_days,
        safety_stock_days=safety_stock_days,
        minimum_order_qty=decimal_value(minimum_order_qty, field="minimum order quantity"),
        order_multiple=decimal_value(order_multiple, field="order multiple"),
        maximum_stock_qty=decimal_value(maximum_stock_qty, field="maximum stock") if maximum_stock_qty is not None else None,
        notes=notes.strip() if notes else None,
    )
    if material.minimum_order_qty < 0 or material.order_multiple < 0 or (material.maximum_stock_qty is not None and material.maximum_stock_qty < 0):
        raise CatalogError("Order constraints cannot be negative.")
    session.add(material)
    session.flush()
    return material


def update_material(session: Session, material_id: int, **changes: Any) -> Material:
    material = session.get(Material, material_id)
    if material is None:
        raise CatalogError("Material not found.")
    allowed = {
        "name", "unit", "is_active", "benchmark_unit_price_inr", "default_lead_time_days",
        "safety_stock_days", "minimum_order_qty", "order_multiple", "maximum_stock_qty", "notes",
    }
    for key, raw_value in changes.items():
        if key not in allowed:
            continue
        value = raw_value
        if key == "name":
            value = _clean_required(str(value), "Material name")
            duplicate = session.scalar(select(Material.id).where(func.lower(Material.name) == value.lower(), Material.id != material_id))
            if duplicate:
                raise CatalogError("A material with that name already exists.")
            if value != material.name:
                referenced = any((
                    session.scalar(select(HistoricalObservation.id).where(HistoricalObservation.material == material.name).limit(1)),
                    session.scalar(select(InventoryTransaction.id).where(InventoryTransaction.material_id == material_id).limit(1)),
                    session.scalar(select(PurchaseOrderLine.id).where(PurchaseOrderLine.material_id == material_id).limit(1)),
                ))
                if referenced:
                    raise CatalogError("Material name is an immutable source identifier after historical data or transactions use it. Deactivate the old entry and add a new material rather than severing source traceability.")
        elif key == "unit":
            value = _clean_required(str(value), "Unit")
            if value != material.unit:
                referenced = any(
                    (
                        session.scalar(select(HistoricalObservation.id).where(HistoricalObservation.material == material.name).limit(1)),
                        session.scalar(select(InventoryTransaction.id).where(InventoryTransaction.material_id == material_id).limit(1)),
                        session.scalar(select(PurchaseOrderLine.id).where(PurchaseOrderLine.material_id == material_id).limit(1)),
                    )
                )
                if referenced:
                    raise CatalogError("Unit cannot be changed after historical data, ledger transactions or purchase orders reference this material. Add a new material with the correct unit instead.")
        elif key in {"benchmark_unit_price_inr", "minimum_order_qty", "order_multiple", "maximum_stock_qty"}:
            value = decimal_value(value, field=key.replace("_", " ")) if value is not None else None
            if value is not None and value < 0:
                raise CatalogError(f"{key.replace('_', ' ').title()} cannot be negative.")
            if key == "benchmark_unit_price_inr":
                material.price_basis = "user-configured reference price" if value is not None else "not configured"
        elif key == "default_lead_time_days" and value is not None:
            value = int(value)
            if value <= 0:
                raise CatalogError("Supplier lead time must be greater than zero or left unset.")
        elif key == "safety_stock_days":
            value = int(value)
            if value < 0:
                raise CatalogError("Safety-stock days cannot be negative.")
        elif key == "notes":
            value = str(value).strip() if value else None
        setattr(material, key, value)
    session.flush()
    return material


def create_site(
    session: Session,
    *,
    identifier: str,
    name: str,
    city: str,
    state: str,
    project_type: str | None = None,
    notes: str | None = None,
) -> ProjectSite:
    clean_identifier = _clean_required(identifier, "Site identifier")
    if session.scalar(select(ProjectSite.id).where(func.lower(ProjectSite.identifier) == clean_identifier.lower())):
        raise CatalogError("A site with that identifier already exists.")
    site = ProjectSite(
        identifier=clean_identifier,
        name=_clean_required(name, "Site name"),
        city=_clean_required(city, "City"),
        state=_clean_required(state, "State"),
        project_type=project_type.strip() if project_type else None,
        notes=notes.strip() if notes else None,
    )
    session.add(site)
    session.flush()
    return site


def update_site(session: Session, site_id: int, **changes: Any) -> ProjectSite:
    site = session.get(ProjectSite, site_id)
    if site is None:
        raise CatalogError("Project site not found.")
    allowed = {"identifier", "name", "city", "state", "project_type", "is_active", "notes"}
    for key, value in changes.items():
        if key not in allowed:
            continue
        if key in {"identifier", "name", "city", "state"}:
            value = _clean_required(str(value), key.replace("_", " ").title())
        if key == "identifier" and value != site.identifier:
            duplicate = session.scalar(select(ProjectSite.id).where(func.lower(ProjectSite.identifier) == value.lower(), ProjectSite.id != site_id))
            if duplicate:
                raise CatalogError("A site with that identifier already exists.")
            referenced = any(
                (
                    session.scalar(select(HistoricalObservation.id).where(HistoricalObservation.project_site_id == site.identifier).limit(1)),
                    session.scalar(select(InventoryTransaction.id).where(InventoryTransaction.site_id == site_id).limit(1)),
                    session.scalar(select(PurchaseOrder.id).where(PurchaseOrder.site_id == site_id).limit(1)),
                )
            )
            # Imported and operational identifiers are immutable once created, because they
            # are also the source-series keys and must remain traceable.
            if referenced:
                raise CatalogError("Site identifier cannot be changed after it is used by historical records or operations; edit the display name instead.")
        if key == "notes":
            value = value.strip() if value else None
        if key == "project_type":
            value = value.strip() if value else None
        setattr(site, key, value)
    session.flush()
    return site
