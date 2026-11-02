"""Operational stock ledger calculations and validated inventory transactions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.models import InventoryTransaction, Material, ProjectSite

TransactionType = Literal["opening_balance", "receipt", "consumption", "adjustment"]
VALID_TRANSACTION_TYPES = {"opening_balance", "receipt", "consumption", "adjustment"}


class InventoryError(ValueError):
    """Raised when a ledger transaction would violate inventory policy."""


class DuplicateTransactionError(InventoryError):
    pass


def decimal_value(value: Decimal | int | float | str, *, field: str = "quantity") -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise InventoryError(f"{field} must be a valid number.") from None
    if not result.is_finite():
        raise InventoryError(f"{field} must be finite.")
    return result


def local_today() -> date:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def get_current_balance(
    session: Session,
    site_id: int,
    material_id: int,
    *,
    as_of: date | None = None,
) -> Decimal | None:
    """Return a known operational balance, or None until a physical opening count exists."""
    cutoff = as_of or local_today()
    entries = session.scalars(
        select(InventoryTransaction)
        .where(
            InventoryTransaction.site_id == site_id,
            InventoryTransaction.material_id == material_id,
            InventoryTransaction.transaction_date <= cutoff,
        )
        .order_by(InventoryTransaction.transaction_date, InventoryTransaction.id)
    ).all()
    openings = [row for row in entries if row.transaction_type == "opening_balance"]
    if not openings:
        return None
    if len(openings) > 1:
        raise InventoryError("Multiple opening balances exist for this site/material ledger; reconcile before using it.")

    balance = Decimal("0")
    for entry in entries:
        amount = Decimal(entry.quantity)
        if entry.transaction_type in {"opening_balance", "receipt"}:
            balance += amount
        elif entry.transaction_type == "consumption":
            balance -= amount
        elif entry.transaction_type == "adjustment":
            balance += amount
    return balance


def has_opening_balance(session: Session, site_id: int, material_id: int) -> bool:
    return session.scalar(
        select(InventoryTransaction.id).where(
            InventoryTransaction.site_id == site_id,
            InventoryTransaction.material_id == material_id,
            InventoryTransaction.transaction_type == "opening_balance",
        ).limit(1)
    ) is not None


def record_inventory_transaction(
    session: Session,
    *,
    idempotency_key: str,
    site_id: int,
    material_id: int,
    transaction_type: TransactionType,
    quantity: Decimal | int | float | str,
    unit: str,
    transaction_date: date,
    reference: str | None = None,
    source: str = "manual",
    source_tag: str = "operator",
    notes: str | None = None,
    unit_cost_inr: Decimal | int | float | str | None = None,
) -> InventoryTransaction:
    """Validate and stage one ledger event. Caller commits within its transaction."""
    if transaction_type not in VALID_TRANSACTION_TYPES:
        raise InventoryError(f"Unsupported transaction type: {transaction_type}.")
    if not idempotency_key.strip():
        raise InventoryError("An idempotency key is required to protect against duplicate posting.")
    clean_source_tag = str(source_tag or "").strip()
    if not clean_source_tag or len(clean_source_tag) > 40:
        raise InventoryError("source_tag must contain 1–40 characters.")
    if session.scalar(select(InventoryTransaction.id).where(InventoryTransaction.idempotency_key == idempotency_key)): 
        raise DuplicateTransactionError("This transaction request has already been posted.")
    material = session.get(Material, material_id)
    site = session.get(ProjectSite, site_id)
    if material is None or site is None or not site.is_active or not material.is_active:
        raise InventoryError("Select an active project site and material.")
    if not unit or unit != material.unit:
        raise InventoryError(f"Unit mismatch: {material.name} is configured in '{material.unit}'.")
    if not isinstance(transaction_date, date):
        raise InventoryError("A valid transaction date is required.")
    if transaction_date > local_today():
        raise InventoryError("Posted inventory transactions cannot be dated in the future.")

    qty = decimal_value(quantity)
    cost = decimal_value(unit_cost_inr, field="unit cost") if unit_cost_inr is not None else None
    if cost is not None and cost < 0:
        raise InventoryError("Recorded unit cost cannot be negative.")
    if cost is not None and transaction_type == "consumption" and source != "sale":
        raise InventoryError("A cost on an outgoing sale may only be set by the sales service.")
    if cost is not None and transaction_type == "adjustment" and qty < 0:
        raise InventoryError("A negative adjustment removes stock; it cannot add a cost layer.")
    clean_notes = notes.strip() if notes else None
    if transaction_type == "adjustment" and not clean_notes:
        raise InventoryError("A reason is required for every stock adjustment.")
    if transaction_type == "opening_balance":
        if qty < 0:
            raise InventoryError("An opening balance cannot be negative.")
        existing = session.scalar(
            select(InventoryTransaction.id).where(
                InventoryTransaction.site_id == site_id,
                InventoryTransaction.material_id == material_id,
                InventoryTransaction.transaction_type == "opening_balance",
            ).limit(1)
        )
        any_txn = session.scalar(
            select(InventoryTransaction.id).where(
                InventoryTransaction.site_id == site_id,
                InventoryTransaction.material_id == material_id,
            ).limit(1)
        )
        if existing or any_txn:
            raise InventoryError("A ledger already exists for this material/site. Use a stock adjustment instead of adding another opening balance.")
    else:
        if transaction_type == "adjustment" and qty == 0:
            raise InventoryError("An adjustment must be non-zero; use a note to document a count with no change.")
        if transaction_type != "adjustment" and qty <= 0:
            raise InventoryError(f"{transaction_type.replace('_', ' ').title()} quantity must be greater than zero.")
        current = get_current_balance(session, site_id, material_id, as_of=transaction_date)
        if current is None:
            raise InventoryError("Initialize the operational opening balance from a physical count before posting receipts, consumption or adjustments.")
        delta = qty if transaction_type in {"receipt", "adjustment"} else -qty
        if current + delta < 0:
            raise InventoryError(f"Transaction would create a negative balance ({current + delta} {unit}).")

    txn = InventoryTransaction(
        idempotency_key=idempotency_key,
        site_id=site_id,
        material_id=material_id,
        transaction_type=transaction_type,
        quantity=qty,
        unit=unit,
        unit_cost_inr=cost,
        transaction_date=transaction_date,
        reference=reference.strip() if reference else None,
        source=source,
        source_tag=clean_source_tag,
        notes=clean_notes,
    )
    session.add(txn)
    session.flush()
    return txn


def ledger_rows(session: Session, site_id: int | None = None, material_id: int | None = None) -> list[dict[str, object]]:
    query = select(InventoryTransaction, ProjectSite, Material).join(
        ProjectSite, InventoryTransaction.site_id == ProjectSite.id
    ).join(Material, InventoryTransaction.material_id == Material.id)
    if site_id is not None:
        query = query.where(InventoryTransaction.site_id == site_id)
    if material_id is not None:
        query = query.where(InventoryTransaction.material_id == material_id)
    rows = session.execute(query.order_by(InventoryTransaction.transaction_date.desc(), InventoryTransaction.id.desc())).all()
    return [
        {
            "Date": tx.transaction_date,
            "Site": site.identifier,
            "Material": material.name,
            "Type": tx.transaction_type.replace("_", " ").title(),
            "Quantity": float(tx.quantity),
            "Unit": tx.unit,
            "Recorded unit cost (INR)": float(tx.unit_cost_inr) if tx.unit_cost_inr is not None else None,
            "Reference": tx.reference or "—",
            "Source": tx.source,
            "Source tag": tx.source_tag,
            "Notes": tx.notes or "",
        }
        for tx, site, material in rows
    ]
