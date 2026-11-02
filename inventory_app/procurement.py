"""Supplier and purchase-order lifecycle with atomic, idempotent receipt posting."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from inventory_app.inventory import (
    DuplicateTransactionError,
    InventoryError,
    decimal_value,
    get_current_balance,
    local_today,
    record_inventory_transaction,
)
from inventory_app.models import (
    InventoryTransaction,
    Material,
    ProjectSite,
    PurchaseOrder,
    PurchaseOrderLine,
    ReceiptRecord,
    Supplier,
)

PO_STATUSES = ("Draft", "Pending approval", "Approved", "Partially received", "Received", "Cancelled")


class ProcurementError(ValueError):
    pass


def create_supplier(
    session: Session,
    *,
    name: str,
    contact_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    city: str | None = None,
    notes: str | None = None,
) -> Supplier:
    clean_name = name.strip()
    if not clean_name:
        raise ProcurementError("Supplier name is required.")
    if session.scalar(select(Supplier.id).where(func.lower(Supplier.name) == clean_name.lower())):
        raise ProcurementError("A supplier with that name already exists.")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
        raise ProcurementError("Enter a valid email address or leave it blank.")
    supplier = Supplier(
        name=clean_name,
        contact_name=contact_name.strip() if contact_name else None,
        email=email.strip() if email else None,
        phone=phone.strip() if phone else None,
        city=city.strip() if city else None,
        notes=notes.strip() if notes else None,
        is_active=True,
    )
    session.add(supplier)
    session.flush()
    return supplier


def update_supplier(session: Session, supplier_id: int, **changes: Any) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise ProcurementError("Supplier not found.")
    allowed = {"name", "contact_name", "email", "phone", "city", "notes", "is_active"}
    for key, value in changes.items():
        if key not in allowed:
            continue
        if key == "name":
            clean = str(value).strip()
            if not clean:
                raise ProcurementError("Supplier name is required.")
            duplicate = session.scalar(select(Supplier.id).where(func.lower(Supplier.name) == clean.lower(), Supplier.id != supplier_id))
            if duplicate:
                raise ProcurementError("A supplier with that name already exists.")
            value = clean
        if key == "email" and value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(value).strip()):
            raise ProcurementError("Enter a valid email address or leave it blank.")
        setattr(supplier, key, value.strip() if isinstance(value, str) and value.strip() else (None if value == "" else value))
    session.flush()
    return supplier


def _new_po_number(session: Session, order_date: date) -> str:
    prefix = f"PO-{order_date:%Y%m%d}-"
    existing = session.scalars(select(PurchaseOrder.po_number).where(PurchaseOrder.po_number.like(f"{prefix}%"))).all()
    sequence = len(existing) + 1
    candidate = f"{prefix}{sequence:03d}"
    while session.scalar(select(PurchaseOrder.id).where(PurchaseOrder.po_number == candidate)):
        sequence += 1
        candidate = f"{prefix}{sequence:03d}"
    return candidate


def create_purchase_order(
    session: Session,
    *,
    idempotency_key: str,
    supplier_id: int,
    site_id: int,
    order_date: date,
    expected_delivery_date: date | None,
    lines: list[dict[str, Any]],
    notes: str | None = None,
) -> PurchaseOrder:
    if not idempotency_key.strip():
        raise ProcurementError("An idempotency key is required.")
    if session.scalar(select(PurchaseOrder.id).where(PurchaseOrder.idempotency_key == idempotency_key)):
        raise ProcurementError("This purchase-order request has already been submitted.")
    supplier = session.get(Supplier, supplier_id)
    site = session.get(ProjectSite, site_id)
    if supplier is None or not supplier.is_active:
        raise ProcurementError("Select an active, configured supplier.")
    if site is None or not site.is_active:
        raise ProcurementError("Select an active project site.")
    if not isinstance(order_date, date) or order_date > local_today():
        raise ProcurementError("Order date must be valid and cannot be in the future.")
    if expected_delivery_date is not None and expected_delivery_date < order_date:
        raise ProcurementError("Expected delivery cannot be earlier than the order date.")
    if not lines:
        raise ProcurementError("Add at least one material line to the purchase order.")

    normalized: list[tuple[Material, Decimal, Decimal]] = []
    for line in lines:
        material = session.get(Material, int(line["material_id"]))
        if material is None or not material.is_active:
            raise ProcurementError("Every PO line must use an active material.")
        unit = str(line.get("unit", ""))
        if unit != material.unit:
            raise ProcurementError(f"Unit mismatch for {material.name}: expected '{material.unit}'.")
        qty = decimal_value(line.get("quantity"), field="ordered quantity")
        price = decimal_value(line.get("unit_price_inr"), field="unit price")
        if qty <= 0:
            raise ProcurementError("Ordered quantity must be greater than zero.")
        if price < 0:
            raise ProcurementError("Unit price cannot be negative.")
        normalized.append((material, qty, price))

    order = PurchaseOrder(
        po_number=_new_po_number(session, order_date),
        idempotency_key=idempotency_key,
        supplier_id=supplier_id,
        site_id=site_id,
        status="Draft",
        order_date=order_date,
        expected_delivery_date=expected_delivery_date,
        notes=notes.strip() if notes else None,
    )
    session.add(order)
    session.flush()
    for material, qty, price in normalized:
        session.add(
            PurchaseOrderLine(
                purchase_order_id=order.id,
                material_id=material.id,
                quantity_ordered=qty,
                unit=material.unit,
                unit_price_inr=price,
                quantity_received=Decimal("0"),
            )
        )
    session.flush()
    return order


def transition_purchase_order(session: Session, order_id: int, new_status: str) -> PurchaseOrder:
    order = session.get(PurchaseOrder, order_id)
    if order is None:
        raise ProcurementError("Purchase order not found.")
    if new_status not in PO_STATUSES:
        raise ProcurementError("Unsupported purchase-order status.")
    current = order.status
    allowed = {
        "Draft": {"Pending approval", "Cancelled"},
        "Pending approval": {"Draft", "Approved", "Cancelled"},
        "Approved": {"Cancelled"},
        "Partially received": set(),
        "Received": set(),
        "Cancelled": set(),
    }
    if new_status == current:
        return order
    if new_status not in allowed.get(current, set()):
        raise ProcurementError(f"Status transition {current!r} → {new_status!r} is not allowed.")
    if new_status == "Cancelled":
        lines = session.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)).all()
        if any(Decimal(line.quantity_received) > 0 for line in lines):
            raise ProcurementError("An order with posted receipts cannot be cancelled; reconcile the outstanding quantity instead.")
    order.status = new_status
    session.flush()
    return order


def purchase_order_lines(session: Session, order_id: int) -> list[dict[str, Any]]:
    rows = session.execute(
        select(PurchaseOrderLine, Material)
        .join(Material, PurchaseOrderLine.material_id == Material.id)
        .where(PurchaseOrderLine.purchase_order_id == order_id)
        .order_by(PurchaseOrderLine.id)
    ).all()
    return [
        {
            "line": line,
            "material": material,
            "outstanding": Decimal(line.quantity_ordered) - Decimal(line.quantity_received),
        }
        for line, material in rows
    ]


def post_receipt(
    session: Session,
    *,
    idempotency_key: str,
    receipt_reference: str,
    purchase_order_line_id: int,
    quantity: Decimal | int | float | str,
    unit: str,
    receipt_date: date,
    notes: str | None = None,
) -> ReceiptRecord:
    """Post receipt + inventory transaction atomically and exactly once."""
    key = idempotency_key.strip()
    reference = receipt_reference.strip()
    if not key or not reference:
        raise ProcurementError("Receipt reference and idempotency key are required.")
    existing = session.scalar(
        select(ReceiptRecord.id).where(
            (ReceiptRecord.idempotency_key == key) | (ReceiptRecord.receipt_reference == reference)
        )
    )
    if existing:
        raise DuplicateTransactionError("This receipt reference/request has already been posted.")
    line = session.get(PurchaseOrderLine, purchase_order_line_id)
    if line is None:
        raise ProcurementError("Purchase-order line not found.")
    order = session.get(PurchaseOrder, line.purchase_order_id)
    if order is None or order.status not in {"Approved", "Partially received"}:
        raise ProcurementError("Only approved or partially received purchase orders can accept receipts.")
    qty = decimal_value(quantity, field="receipt quantity")
    if qty <= 0:
        raise ProcurementError("Receipt quantity must be greater than zero.")
    outstanding = Decimal(line.quantity_ordered) - Decimal(line.quantity_received)
    if qty > outstanding:
        raise ProcurementError(f"Receipt exceeds outstanding quantity ({outstanding} {line.unit}).")
    if unit != line.unit:
        raise ProcurementError(f"Receipt unit mismatch: expected '{line.unit}'.")
    if not isinstance(receipt_date, date) or receipt_date > local_today():
        raise ProcurementError("Receipt date must be valid and cannot be in the future.")

    transaction = record_inventory_transaction(
        session,
        idempotency_key=f"receipt:{key}",
        site_id=order.site_id,
        material_id=line.material_id,
        transaction_type="receipt",
        quantity=qty,
        unit=unit,
        transaction_date=receipt_date,
        reference=reference,
        source="purchase_order",
        notes=notes or f"Confirmed receipt against {order.po_number}",
    )
    receipt = ReceiptRecord(
        idempotency_key=key,
        receipt_reference=reference,
        purchase_order_line_id=line.id,
        quantity=qty,
        unit=unit,
        receipt_date=receipt_date,
        notes=notes.strip() if notes else None,
        inventory_transaction_id=transaction.id,
    )
    session.add(receipt)
    line.quantity_received = Decimal(line.quantity_received) + qty
    if line.quantity_received >= line.quantity_ordered:
        all_lines = session.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)).all()
        # Flush the current line value before checking every line's state.
        session.flush()
        order.status = "Received" if all(
            Decimal(item.quantity_received) >= Decimal(item.quantity_ordered) for item in all_lines
        ) else "Partially received"
    else:
        order.status = "Partially received"
    session.flush()
    return receipt


def order_summary(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(PurchaseOrder, Supplier, ProjectSite)
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .join(ProjectSite, PurchaseOrder.site_id == ProjectSite.id)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
    ).all()
    output = []
    for order, supplier, site in rows:
        lines = session.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)).all()
        total = sum((Decimal(line.quantity_ordered) * Decimal(line.unit_price_inr) for line in lines), Decimal("0"))
        outstanding_lines = sum(
            (Decimal(line.quantity_ordered) - Decimal(line.quantity_received) for line in lines), Decimal("0")
        )
        output.append({
            "ID": order.id,
            "PO number": order.po_number,
            "Supplier": supplier.name,
            "Site": site.identifier,
            "Status": order.status,
            "Order date": order.order_date,
            "Expected delivery": order.expected_delivery_date,
            "Lines": len(lines),
            "Order value (INR, estimate)": float(total),
            "Outstanding quantity (mixed units)": float(outstanding_lines),
        })
    return output


def eligible_incoming_for_material(session: Session, site_id: int, material_id: int) -> list[dict[str, Any]]:
    """Approved pipeline lines only; actual receipts are already in the ledger."""
    rows = session.execute(
        select(PurchaseOrderLine, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.site_id == site_id,
            PurchaseOrderLine.material_id == material_id,
            PurchaseOrder.status.in_(["Approved", "Partially received"]),
        )
    ).all()
    result = []
    for line, order in rows:
        outstanding = Decimal(line.quantity_ordered) - Decimal(line.quantity_received)
        if outstanding > 0:
            result.append({
                "quantity": outstanding,
                "unit": line.unit,
                "expected_date": order.expected_delivery_date,
                "status": order.status,
                "reference": order.po_number,
            })
    return result
