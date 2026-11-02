"""Recorded-cost FIFO helpers for inventory valuation and sales margin.

No catalogue benchmark or historical CSV price is used as operational cost. Stock
without a recorded opening/receipt/positive-adjustment unit cost remains unvalued.
"""
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


def _take_fifo(layers: list[list[Decimal | None]], quantity: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Consume a quantity from mutable [remaining quantity, unit cost] FIFO layers."""
    remaining = quantity
    known_cost = Decimal("0")
    unknown_quantity = Decimal("0")
    index = 0
    while remaining > 0 and index < len(layers):
        layer_qty, unit_cost = layers[index]
        assert layer_qty is not None
        take = min(layer_qty, remaining)
        if unit_cost is None:
            unknown_quantity += take
        else:
            known_cost += take * unit_cost
        layers[index][0] = layer_qty - take
        remaining -= take
        if layers[index][0] == 0:
            index += 1
        else:
            break
    layers[:] = [layer for layer in layers if layer[0] and layer[0] > 0]
    return known_cost, unknown_quantity, remaining


def _layers_after(entries: list[InventoryTransaction]) -> list[list[Decimal | None]]:
    layers: list[list[Decimal | None]] = []
    for entry in entries:
        quantity = Decimal(entry.quantity)
        if entry.transaction_type in {"opening_balance", "receipt"}:
            layers.append([quantity, Decimal(entry.unit_cost_inr) if entry.unit_cost_inr is not None else None])
        elif entry.transaction_type == "adjustment":
            if quantity > 0:
                layers.append([quantity, Decimal(entry.unit_cost_inr) if entry.unit_cost_inr is not None else None])
            elif quantity < 0:
                _take_fifo(layers, -quantity)
        elif entry.transaction_type == "consumption":
            _take_fifo(layers, quantity)
    return [layer for layer in layers if layer[0] and layer[0] > 0]


def fifo_issue_cost(
    session: Session,
    *,
    site_id: int,
    material_id: int,
    quantity: Decimal,
    sale_date: date,
) -> tuple[Decimal | None, Decimal | None]:
    """Return (COGS, blended unit cost) only when every sold unit has recorded cost."""
    if quantity <= 0:
        raise CostBasisError("Sale quantity must be positive for cost allocation.")
    entries = _entries(session, site_id, material_id, as_of=sale_date)
    layers = _layers_after(entries)
    known_cost, unknown_qty, unfilled = _take_fifo(layers, quantity)
    if unfilled > 0:
        raise CostBasisError("Sale quantity exceeds the cost-layer stock available on the sale date.")
    if unknown_qty > 0:
        return None, None
    cogs = known_cost.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    unit_cost = (known_cost / quantity).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    return cogs, unit_cost


def inventory_cost_summary(
    session: Session,
    *,
    site_id: int,
    material_id: int,
    as_of: date,
) -> dict[str, Decimal | str | None]:
    """Return ledger quantity and recorded-cost coverage without estimating unknown stock."""
    balance = get_current_balance(session, site_id, material_id, as_of=as_of)
    if balance is None:
        return {
            "current_stock": None,
            "stock_value_inr": None,
            "known_cost_value_inr": None,
            "costed_quantity": None,
            "uncosted_quantity": None,
            "cost_basis_status": "Not initialized",
        }
    layers = _layers_after(_entries(session, site_id, material_id, as_of=as_of))
    costed_qty = sum((layer[0] for layer in layers if layer[1] is not None and layer[0] is not None), Decimal("0"))
    uncosted_qty = sum((layer[0] for layer in layers if layer[1] is None and layer[0] is not None), Decimal("0"))
    known_value = sum((layer[0] * layer[1] for layer in layers if layer[0] is not None and layer[1] is not None), Decimal("0"))
    if uncosted_qty == 0:
        status = "Fully costed"
        total_value: Decimal | None = known_value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    elif costed_qty == 0:
        status = "No recorded cost basis"
        total_value = None
    else:
        status = "Partially costed"
        total_value = None
    return {
        "current_stock": balance,
        "stock_value_inr": total_value,
        "known_cost_value_inr": known_value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "costed_quantity": costed_qty,
        "uncosted_quantity": uncosted_qty,
        "cost_basis_status": status,
    }
