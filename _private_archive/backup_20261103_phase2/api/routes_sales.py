"""Customer sales endpoints and margin-safe reporting."""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.errors import APIProblem
from api.schemas import SaleCreate
from api.serializers import sale_payload
from inventory_app.inventory import get_current_balance
from inventory_app.models import Customer, Material, ProjectSite, SalesRecord
from inventory_app.sales import DuplicateSaleError, SalesError, create_sale

router = APIRouter(prefix="/api", tags=["sales"])


def _sales_query(
    *,
    search: str | None,
    site_id: int | None,
    material_id: int | None,
    customer_id: int | None,
    start_date: date | None,
    end_date: date | None,
):
    query = select(SalesRecord, ProjectSite, Material, Customer).join(
        ProjectSite, SalesRecord.site_id == ProjectSite.id
    ).join(Material, SalesRecord.material_id == Material.id).outerjoin(
        Customer, SalesRecord.customer_id == Customer.id
    )
    if site_id is not None:
        query = query.where(SalesRecord.site_id == site_id)
    if material_id is not None:
        query = query.where(SalesRecord.material_id == material_id)
    if customer_id is not None:
        query = query.where(SalesRecord.customer_id == customer_id)
    if start_date:
        query = query.where(SalesRecord.sale_date >= start_date)
    if end_date:
        query = query.where(SalesRecord.sale_date <= end_date)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(
            ProjectSite.identifier.ilike(pattern),
            Material.name.ilike(pattern),
            Customer.name.ilike(pattern),
            SalesRecord.reference.ilike(pattern),
            SalesRecord.notes.ilike(pattern),
        ))
    return query


@router.get("/sales")
def list_sales(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=160),
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_session),
):
    if start_date and end_date and start_date > end_date:
        raise APIProblem(422, "invalid_date_range", "Start date must not be after end date.")
    query = _sales_query(
        search=search,
        site_id=site_id,
        material_id=material_id,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )
    rows = session.execute(query.order_by(SalesRecord.sale_date.desc(), SalesRecord.id.desc())).all()
    total = len(rows)
    page_rows = rows[(page - 1) * page_size: page * page_size]
    revenue = sum((Decimal(sale.revenue_inr) for sale, *_ in rows), Decimal("0"))
    costed = [sale for sale, *_ in rows if sale.cost_of_goods_sold_inr is not None]
    unavailable = total - len(costed)
    complete = total > 0 and unavailable == 0
    margin = sum((Decimal(sale.gross_margin_inr) for sale in costed if sale.gross_margin_inr is not None), Decimal("0")) if complete else None
    cogs = sum((Decimal(sale.cost_of_goods_sold_inr) for sale in costed), Decimal("0")) if complete else None
    summary = {
        "sale_count": total,
        "revenue_inr": float(revenue.quantize(Decimal("0.01"))),
        "cost_of_goods_sold_inr": float(cogs.quantize(Decimal("0.01"))) if cogs is not None else None,
        "gross_margin_inr": float(margin.quantize(Decimal("0.01"))) if margin is not None else None,
        "margin_status": "Available" if complete else ("No sales in filter" if total == 0 else "Unavailable — one or more sales lack a fully recorded FIFO cost basis"),
        "costed_sales_count": len(costed),
        "margin_unavailable_sales_count": unavailable,
        "cost_basis_complete": complete,
    }
    return {
        "items": [sale_payload(sale, site=site, material=material, customer=customer) for sale, site, material, customer in page_rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
        "summary": summary,
    }


@router.post("/sales", status_code=201)
def post_sale(body: SaleCreate, session: Session = Depends(get_session)):
    try:
        sale, created = create_sale(session, **body.model_dump())
        session.commit()
        site = session.get(ProjectSite, sale.site_id)
        material = session.get(Material, sale.material_id)
        customer = session.get(Customer, sale.customer_id) if sale.customer_id is not None else None
        balance = get_current_balance(session, sale.site_id, sale.material_id)
        return {
            "item": sale_payload(sale, site=site, material=material, customer=customer),
            "created": created,
            "current_balance": float(balance) if balance is not None else None,
        }
    except DuplicateSaleError as exc:
        raise APIProblem(409, "duplicate_submission", str(exc)) from exc
    except SalesError as exc:
        message = str(exc)
        conflict = any(term in message.lower() for term in ("negative balance", "initialize the operational opening", "exceeds the cost-layer stock", "already been posted"))
        raise APIProblem(409 if conflict else 422, "sales_conflict" if conflict else "sales_validation", message) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "sales_conflict", "This sale conflicts with an existing ledger or idempotency entry.") from exc
