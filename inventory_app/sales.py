"""Operational customer sales linked to the stock ledger and recorded-cost FIFO."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from inventory_app.costing import CostBasisError, fifo_issue_cost
from inventory_app.inventory import DuplicateTransactionError, InventoryError, decimal_value, get_current_balance, local_today, record_inventory_transaction
from inventory_app.models import Customer, Material, ProjectSite, SalesRecord

MONEY = Decimal("0.01")


class SalesError(ValueError):
    """Raised when a sale or customer fails operational validation."""


class DuplicateSaleError(SalesError):
    pass


def create_customer(
    session: Session,
    *,
    name: str,
    contact_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
    source_tag: str = "operator",
) -> Customer:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise SalesError("Customer name is required.")
    clean_source_tag = str(source_tag or "").strip()
    if not clean_source_tag or len(clean_source_tag) > 40:
        raise SalesError("source_tag must contain 1–40 characters.")
    if session.scalar(select(Customer.id).where(func.lower(Customer.name) == clean_name.lower())):
        raise SalesError("A customer with that name already exists.")
    customer = Customer(
        name=clean_name,
        contact_name=str(contact_name).strip() if contact_name else None,
        email=str(email).strip() if email else None,
        phone=str(phone).strip() if phone else None,
        notes=str(notes).strip() if notes else None,
        source_tag=clean_source_tag,
    )
    session.add(customer)
    session.flush()
    return customer


def create_sale(
    session: Session,
    *,
    idempotency_key: str,
    site_id: int,
    material_id: int,
    customer_id: int | None,
    quantity: Decimal | int | float | str,
    unit: str,
    unit_sale_price_inr: Decimal | int | float | str,
    sale_date: date,
    reference: str | None = None,
    notes: str | None = None,
    source_tag: str = "operator",
) -> tuple[SalesRecord, bool]:
    """Record a sale and its linked stock-consuming transaction atomically.

    A repeated key with the same payload returns the existing record; reusing a key
    for changed content is rejected. Unknown FIFO cost remains unavailable rather
    than being filled from historical CSV or material reference prices.
    """
    key = str(idempotency_key or "").strip()
    if not key or len(key) > 110:
        raise SalesError("An idempotency key between 1 and 110 characters is required.")
    clean_source_tag = str(source_tag or "").strip()
    if not clean_source_tag or len(clean_source_tag) > 40:
        raise SalesError("source_tag must contain 1–40 characters.")

    qty = decimal_value(quantity, field="sale quantity")
    price = decimal_value(unit_sale_price_inr, field="sale price")
    if qty <= 0:
        raise SalesError("Sale quantity must be greater than zero.")
    if price < 0:
        raise SalesError("Sale price cannot be negative.")
    if not isinstance(sale_date, date):
        raise SalesError("A valid sale date is required.")
    if sale_date > local_today():
        raise SalesError("Sales cannot be dated in the future.")

    clean_reference = str(reference).strip() if reference else None
    clean_notes = str(notes).strip() if notes else None
    prior = session.scalar(select(SalesRecord).where(SalesRecord.idempotency_key == key))
    if prior is not None:
        same_payload = (
            prior.site_id == site_id
            and prior.material_id == material_id
            and prior.customer_id == customer_id
            and Decimal(prior.quantity) == qty
            and prior.unit == unit
            and Decimal(prior.unit_sale_price_inr) == price
            and prior.sale_date == sale_date
            and prior.reference == clean_reference
            and prior.notes == clean_notes
            and prior.source_tag == clean_source_tag
        )
        if same_payload:
            return prior, False
        raise DuplicateSaleError("This idempotency key was already used for a different sale.")

    material = session.get(Material, material_id)
    site = session.get(ProjectSite, site_id)
    if material is None or site is None or not material.is_active or not site.is_active:
        raise SalesError("Select an active project site and material.")
    if unit != material.unit:
        raise SalesError(f"Unit mismatch: {material.name} is configured in '{material.unit}'.")
    current_balance = get_current_balance(session, site_id, material_id, as_of=sale_date)
    if current_balance is None:
        raise SalesError("Initialize the operational opening balance from a physical count before posting a sale.")
    if current_balance < qty:
        raise SalesError(f"Sale would create a negative balance ({current_balance - qty} {unit}).")
    customer = session.get(Customer, customer_id) if customer_id is not None else None
    if customer_id is not None and (customer is None or not customer.is_active):
        raise SalesError("Select an active customer or leave the customer blank.")

    try:
        cogs, unit_cost = fifo_issue_cost(
            session,
            site_id=site_id,
            material_id=material_id,
            quantity=qty,
            sale_date=sale_date,
        )
        txn = record_inventory_transaction(
            session,
            idempotency_key=f"sale:{key}",
            site_id=site_id,
            material_id=material_id,
            transaction_type="consumption",
            quantity=qty,
            unit=unit,
            transaction_date=sale_date,
            reference=clean_reference,
            source="sale",
            source_tag=clean_source_tag,
            notes=clean_notes,
            unit_cost_inr=unit_cost,
        )
    except DuplicateTransactionError as exc:
        raise DuplicateSaleError("This sale request has already been posted.") from exc
    except (InventoryError, CostBasisError) as exc:
        raise SalesError(str(exc)) from exc

    revenue = (qty * price).quantize(MONEY, rounding=ROUND_HALF_UP)
    margin = (revenue - cogs).quantize(MONEY, rounding=ROUND_HALF_UP) if cogs is not None else None
    record = SalesRecord(
        idempotency_key=key,
        site_id=site_id,
        material_id=material_id,
        customer_id=customer_id,
        inventory_transaction_id=txn.id,
        sale_date=sale_date,
        quantity=qty,
        unit=unit,
        unit_sale_price_inr=price,
        revenue_inr=revenue,
        unit_cost_basis_inr=unit_cost,
        cost_of_goods_sold_inr=cogs,
        gross_margin_inr=margin,
        reference=clean_reference,
        notes=clean_notes,
        source_tag=clean_source_tag,
    )
    session.add(record)
    session.flush()
    return record, True
