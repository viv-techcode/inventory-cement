"""Minimal purchasing API over the existing atomic procurement service."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.errors import APIProblem
from api.schemas import (PurchaseOrderFromRecommendation, PurchaseOrderStatusUpdate,
                         ReceiptCreate, SupplierCreate)
from inventory_app.models import PurchaseOrder, Supplier
from inventory_app.inventory import InventoryError, local_today
from inventory_app.procurement import (ProcurementError, create_purchase_order,
                                       create_supplier, order_summary, post_receipt,
                                       purchase_order_lines, transition_purchase_order)

router = APIRouter(prefix="/api", tags=["purchasing"])


def _problem(exc: Exception):
    return APIProblem(422, "procurement_error", str(exc))


@router.get("/suppliers")
def suppliers(session: Session = Depends(get_session)):
    rows = session.scalars(select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.name)).all()
    return {"items": [{"id": x.id, "name": x.name, "contact_name": x.contact_name,
                       "email": x.email, "phone": x.phone, "city": x.city} for x in rows]}


@router.post("/suppliers", status_code=201)
def add_supplier(body: SupplierCreate, session: Session = Depends(get_session)):
    try:
        item = create_supplier(session, **body.model_dump())
        session.commit()
        return {"id": item.id, "name": item.name, "is_active": item.is_active}
    except ProcurementError as exc:
        session.rollback()
        raise _problem(exc) from exc


@router.get("/purchase-orders")
def purchase_orders(session: Session = Depends(get_session)):
    output = []
    for row in order_summary(session):
        order = session.get(PurchaseOrder, row["ID"])
        lines = purchase_order_lines(session, order.id)
        output.append({"id": order.id, "po_number": order.po_number, "supplier": row["Supplier"],
                       "site": row["Site"], "status": order.status,
                       "order_date": order.order_date, "expected_delivery_date": order.expected_delivery_date,
                       "lines": [{"id": x["line"].id, "material": x["material"].name,
                                  "quantity_ordered": x["line"].quantity_ordered,
                                  "quantity_received": x["line"].quantity_received,
                                  "outstanding": x["outstanding"], "unit": x["line"].unit}
                                 for x in lines]})
    return {"items": output}


@router.post("/purchase-orders/from-recommendation", status_code=201)
def create_from_recommendation(body: PurchaseOrderFromRecommendation, session: Session = Depends(get_session)):
    try:
        order = create_purchase_order(session, idempotency_key=body.idempotency_key,
            supplier_id=body.supplier_id, site_id=body.site_id, order_date=local_today(),
            expected_delivery_date=body.expected_delivery_date,
            lines=[{"material_id": body.material_id, "quantity": body.quantity,
                    "unit": body.unit, "unit_price_inr": body.unit_price_inr}], notes=body.notes)
        session.commit()
        return {"id": order.id, "po_number": order.po_number, "status": order.status,
                "lines": [{"id": x["line"].id, "material": x["material"].name,
                           "quantity_ordered": x["line"].quantity_ordered,
                           "unit": x["line"].unit} for x in purchase_order_lines(session, order.id)]}
    except (ProcurementError, InventoryError, ValueError) as exc:
        session.rollback()
        raise _problem(exc) from exc


@router.patch("/purchase-orders/{order_id}/status")
def update_status(order_id: int, body: PurchaseOrderStatusUpdate, session: Session = Depends(get_session)):
    try:
        order = transition_purchase_order(session, order_id, body.status)
        session.commit()
        return {"id": order.id, "po_number": order.po_number, "status": order.status}
    except ProcurementError as exc:
        session.rollback()
        raise _problem(exc) from exc


@router.post("/receipts", status_code=201)
def receive_goods(body: ReceiptCreate, session: Session = Depends(get_session)):
    try:
        receipt = post_receipt(session, **body.model_dump())
        session.commit()
        return {"id": receipt.id, "receipt_reference": receipt.receipt_reference,
                "quantity": receipt.quantity, "unit": receipt.unit,
                "inventory_transaction_id": receipt.inventory_transaction_id}
    except (ProcurementError, InventoryError, ValueError) as exc:
        session.rollback()
        raise _problem(exc) from exc
