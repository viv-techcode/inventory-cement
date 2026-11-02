"""Operational stock ledger, balance, and per-pair reorder-rule endpoints."""
from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.errors import APIProblem
from api.schemas import InventoryTransactionCreate, ReorderRuleInput
from api.serializers import as_iso, material_payload, reorder_rule_payload, site_payload
from inventory_app.inventory import (
    DuplicateTransactionError,
    InventoryError,
    get_current_balance,
    local_today,
    record_inventory_transaction,
)
from inventory_app.models import InventoryTransaction, Material, ProjectSite, ReorderRule
from inventory_app.reorder import ReorderRuleError, save_reorder_rule
from inventory_app.reports import current_inventory_report

router = APIRouter(prefix="/api", tags=["inventory"])


def _json_scalar(value):
    """Normalize pandas/NumPy scalars and represent missing values as JSON null."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _transaction_payload(txn: InventoryTransaction, site: ProjectSite, material: Material) -> dict:
    display_type = "Sale" if txn.source == "sale" else txn.transaction_type.replace("_", " ").title()
    return {
        "id": txn.id,
        "date": as_iso(txn.transaction_date),
        "site_id": site.id,
        "site": site.identifier,
        "material_id": material.id,
        "material": material.name,
        "type": display_type,
        "transaction_type": txn.transaction_type,
        "quantity": float(txn.quantity),
        "unit": txn.unit,
        "unit_cost_inr": float(txn.unit_cost_inr) if txn.unit_cost_inr is not None else None,
        "reference": txn.reference,
        "source": txn.source,
        "source_tag": txn.source_tag,
        "notes": txn.notes,
        "created_at": as_iso(txn.created_at),
    }


def _transaction_query(
    session: Session,
    *,
    search: str | None,
    site_id: int | None,
    material_id: int | None,
    transaction_type: str | None,
    start_date: date | None,
    end_date: date | None,
):
    query = select(InventoryTransaction, ProjectSite, Material).join(
        ProjectSite, InventoryTransaction.site_id == ProjectSite.id
    ).join(Material, InventoryTransaction.material_id == Material.id)
    if site_id is not None:
        query = query.where(InventoryTransaction.site_id == site_id)
    if material_id is not None:
        query = query.where(InventoryTransaction.material_id == material_id)
    if transaction_type:
        if transaction_type.lower() == "sale":
            query = query.where(InventoryTransaction.source == "sale")
        else:
            query = query.where(InventoryTransaction.transaction_type == transaction_type.lower().replace(" ", "_"))
    if start_date:
        query = query.where(InventoryTransaction.transaction_date >= start_date)
    if end_date:
        query = query.where(InventoryTransaction.transaction_date <= end_date)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(
            ProjectSite.identifier.ilike(pattern),
            Material.name.ilike(pattern),
            InventoryTransaction.reference.ilike(pattern),
            InventoryTransaction.notes.ilike(pattern),
            InventoryTransaction.source.ilike(pattern),
        ))
    return query


@router.get("/inventory/balances")
def list_balances(
    site_id: int | None = None,
    material_id: int | None = None,
    alert_only: bool = False,
    search: str | None = Query(default=None, max_length=160),
    session: Session = Depends(get_session),
):
    frame = current_inventory_report(session)
    if site_id is not None:
        site = session.get(ProjectSite, site_id)
        if site is None:
            raise APIProblem(404, "site_not_found", "Project site not found.")
        frame = frame.loc[frame["site"] == site.identifier]
    if material_id is not None:
        material = session.get(Material, material_id)
        if material is None:
            raise APIProblem(404, "material_not_found", "Material not found.")
        frame = frame.loc[frame["material"] == material.name]
    if alert_only:
        frame = frame.loc[frame["reorder_alert"]]
    if search:
        mask = frame["site"].str.contains(search, case=False, na=False) | frame["material"].str.contains(search, case=False, na=False)
        frame = frame.loc[mask]
    items = [
        {key: _json_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    return {"items": items, "total": len(items), "as_of": local_today().isoformat()}


@router.get("/inventory/transactions")
def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=160),
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    transaction_type: str | None = Query(default=None, max_length=30),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_session),
):
    if start_date and end_date and start_date > end_date:
        raise APIProblem(422, "invalid_date_range", "Start date must not be after end date.")
    query = _transaction_query(
        session,
        search=search,
        site_id=site_id,
        material_id=material_id,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
    )
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = int(session.scalar(count_query) or 0)
    rows = session.execute(
        query.order_by(InventoryTransaction.transaction_date.desc(), InventoryTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_transaction_payload(txn, site, material) for txn, site, material in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.post("/inventory/transactions", status_code=201)
def post_transaction(body: InventoryTransactionCreate, session: Session = Depends(get_session)):
    try:
        txn = record_inventory_transaction(
            session,
            idempotency_key=body.idempotency_key,
            site_id=body.site_id,
            material_id=body.material_id,
            transaction_type=body.transaction_type,
            quantity=body.quantity,
            unit=body.unit,
            transaction_date=body.transaction_date,
            reference=body.reference,
            source="manual",
            notes=body.reason if body.transaction_type == "adjustment" else body.notes,
            unit_cost_inr=body.unit_cost_inr,
        )
        session.commit()
        site = session.get(ProjectSite, txn.site_id)
        material = session.get(Material, txn.material_id)
        return {
            "item": _transaction_payload(txn, site, material),
            "current_balance": float(get_current_balance(session, txn.site_id, txn.material_id)),
        }
    except DuplicateTransactionError as exc:
        raise APIProblem(409, "duplicate_submission", str(exc)) from exc
    except InventoryError as exc:
        status = 409 if "negative balance" in str(exc).lower() or "already exists" in str(exc).lower() or "already been posted" in str(exc).lower() else 422
        raise APIProblem(status, "inventory_conflict" if status == 409 else "inventory_validation", str(exc)) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "inventory_conflict", "This ledger transaction conflicts with an existing entry.") from exc


@router.get("/reorder-rules")
def list_reorder_rules(
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    include_inactive: bool = False,
    session: Session = Depends(get_session),
):
    query = select(ReorderRule, ProjectSite, Material).join(
        ProjectSite, ReorderRule.site_id == ProjectSite.id
    ).join(Material, ReorderRule.material_id == Material.id)
    if site_id is not None:
        query = query.where(ReorderRule.site_id == site_id)
    if material_id is not None:
        query = query.where(ReorderRule.material_id == material_id)
    if not include_inactive:
        query = query.where(ReorderRule.is_active.is_(True))
    rows = session.execute(query.order_by(ProjectSite.identifier, Material.name)).all()
    return {"items": [reorder_rule_payload(rule, site=site, material=material) for rule, site, material in rows]}


@router.put("/reorder-rules/{site_id}/{material_id}")
def upsert_reorder_rule(
    site_id: int,
    material_id: int,
    body: ReorderRuleInput,
    session: Session = Depends(get_session),
):
    if body.site_id != site_id or body.material_id != material_id:
        raise APIProblem(422, "path_body_mismatch", "Path site/material IDs must match the request body.")
    try:
        rule = save_reorder_rule(session, **body.model_dump())
        session.commit()
        site = session.get(ProjectSite, site_id)
        material = session.get(Material, material_id)
        return {"item": reorder_rule_payload(rule, site=site, material=material)}
    except ReorderRuleError as exc:
        raise APIProblem(422, "reorder_rule_validation", str(exc)) from exc
    except IntegrityError as exc:
        raise APIProblem(409, "reorder_rule_conflict", "A reorder rule already exists for this pair and could not be updated.") from exc
