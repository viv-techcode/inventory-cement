"""Recorded moving weighted-average cost for inventory valuation and sales margin."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.inventory import get_current_balance
from inventory_app.models import InventoryTransaction

FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")


class CostBasisError(ValueError):
    """Raised when a sale quantity cannot be reconciled to the stock ledger."""


def _entries(session: Session, site_id: int, material_id: int, *, as_of: date | None = None) -> list[InventoryTransaction]:
    query = select(InventoryTransaction).where(
        InventoryTransaction.site_id == site_id,
        InventoryTransaction.material_id == material_id,
    )
    if as_of is not None:
        query = query.where(InventoryTransaction.transaction_date <= as_of)
    return list(session.scalars(query.order_by(InventoryTransaction.transaction_date, InventoryTransaction.id)).all())


def _weighted_state(entries: list[InventoryTransaction]) -> tuple[Decimal, Decimal, Decimal]:
    """Return (quantity, known cost value, quantity with no recorded cost)."""
    quantity = Decimal("0")
    known_value = Decimal("0")
    unknown = Decimal("0")
    for entry in entries:
        qty = Decimal(entry.quantity)
        if entry.transaction_type in {"opening_balance", "receipt"}:
            quantity += qty
            if entry.unit_cost_inr is None:
                unknown += qty
            else:
                known_value += qty * Decimal(entry.unit_cost_inr)
        elif entry.transaction_type == "adjustment":
            if qty > 0:
                quantity += qty
                if entry.unit_cost_inr is None:
                    unknown += qty
                else:
                    known_value += qty * Decimal(entry.unit_cost_inr)
            elif qty < 0:
                remove = -qty
                if remove > quantity:
                    raise CostBasisError("Adjustment exceeds available stock on its transaction date.")
                if quantity:
                    average_value = known_value / quantity
                    known_value -= average_value * remove
                    unknown = max(Decimal("0"), unknown - remove)
                quantity -= remove
        elif entry.transaction_type == "consumption":
            if qty > quantity:
                raise CostBasisError("Sale quantity exceeds available stock on its transaction date.")
            if quantity:
                known_value -= (known_value / quantity) * qty
                # Unknown-cost stock makes the blended issue cost unavailable until cleared.
                unknown = max(Decimal("0"), unknown - min(unknown, qty))
            quantity -= qty
    return quantity, max(Decimal("0"), known_value), unknown


def weighted_average_issue_cost(
    session: Session, *, site_id: int, material_id: int, quantity: Decimal, sale_date: date,
) -> tuple[Decimal | None, Decimal | None]:
    """Return COGS and unit cost when all on-hand stock has recorded cost basis."""
    if quantity <= 0:
        raise CostBasisError("Sale quantity must be positive for cost allocation.")
    entries = _entries(session, site_id, material_id, as_of=sale_date)
    on_hand, known_value, unknown = _weighted_state(entries)
    if quantity > on_hand:
        raise CostBasisError("Sale quantity exceeds the stock available on the sale date.")
    if unknown > 0:
        return None, None
    average = known_value / on_hand if on_hand else Decimal("0")
    cogs = (average * quantity).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return cogs, average.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def inventory_cost_summary(session: Session, *, site_id: int, material_id: int, as_of: date) -> dict[str, Decimal | str | None]:
    """Return ledger stock and moving-average valuation without imputing missing costs."""
    balance = get_current_balance(session, site_id, material_id, as_of=as_of)
    if balance is None:
        return {"current_stock": None, "stock_value_inr": None, "known_cost_value_inr": None,
                "costed_quantity": None, "uncosted_quantity": None, "cost_basis_status": "Not initialized"}
    quantity, value, unknown = _weighted_state(_entries(session, site_id, material_id, as_of=as_of))
    costed_qty = max(Decimal("0"), quantity - unknown)
    if unknown == 0:
        status, total_value = "Fully costed", value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    elif costed_qty == 0:
        status, total_value = "No recorded cost basis", None
    else:
        status, total_value = "Partially costed", None
    return {"current_stock": balance, "stock_value_inr": total_value,
            "known_cost_value_inr": value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            "costed_quantity": costed_qty, "uncosted_quantity": unknown, "cost_basis_status": status}
