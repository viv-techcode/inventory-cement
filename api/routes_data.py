"""Inspection routes for the fixed baseline ledger and its load history."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies import get_database, get_session
from inventory_app.data_quality import build_data_quality_report, history_to_frame
from inventory_app.models import ImportRun, InventoryTransaction, Material, ProjectSite, RejectedRow

router = APIRouter(prefix="/api", tags=["data"])
@router.get("/data/quality")
def data_quality(session: Session = Depends(get_session)):
    baseline = session.execute(
        select(InventoryTransaction, ProjectSite, Material)
        .join(ProjectSite, InventoryTransaction.site_id == ProjectSite.id)
        .join(Material, InventoryTransaction.material_id == Material.id)
        .where(InventoryTransaction.source_tag == "baseline_ledger")
        .order_by(InventoryTransaction.transaction_date, InventoryTransaction.id)
    ).all()
    type_counts = {}
    sites, materials, units = set(), set(), {}
    running_stock = {}
    stock_reconciles = True
    dates = []
    for txn, site, material in baseline:
        label = {"opening_balance":"opening_balance", "receipt":"purchase_receipt", "consumption":"sale", "adjustment":"adjustment"}[txn.transaction_type]
        type_counts[label] = type_counts.get(label, 0) + 1
        sites.add(site.identifier)
        materials.add(material.name)
        units.setdefault(material.name, set()).add(txn.unit)
        dates.append(txn.transaction_date)
        key = (site.identifier, material.name)
        running_stock[key] = running_stock.get(key, 0.0) + (float(txn.quantity) if txn.transaction_type in {"opening_balance", "receipt", "adjustment"} else -float(txn.quantity))
        if running_stock[key] < -0.0001:
            stock_reconciles = False
    history = history_to_frame(session)
    report = build_data_quality_report(history)
    report.update({
        "row_count": len(baseline),
        "site_count": len(sites),
        "material_count": len(materials),
        "date_min": min(dates).isoformat() if dates else None,
        "date_max": max(dates).isoformat() if dates else None,
        "event_type_counts": type_counts,
        "unique_event_ids": len({txn.idempotency_key.removeprefix("baseline:") for txn, _, _ in baseline}),
        "unit_consistency_pass": all(len(value) == 1 for value in units.values()),
        "stock_reconciles_pass": stock_reconciles,
        "entries_added_since_load": session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source_tag != "baseline_ledger")) or 0,
    })
    operational = session.scalars(select(ImportRun)).all()
    return {
        "historical_source_label": "Doon Ridge Materials Ledger",
        "entries_since_load_excluded_from_training": True,
        "report": report,
        "import_run_count": len(operational),
        "rejected_row_count": sum(run.rejected_rows for run in operational),
        "required_columns": ["event_id", "date", "site", "material", "unit", "quantity", "unit_price", "unit_cost", "document_reference", "counterparty", "event_type"],
    }


@router.get("/data/imports")
def data_import_history(session: Session = Depends(get_session)):
    runs = session.scalars(select(ImportRun).order_by(ImportRun.imported_at.desc())).all()
    rejects = session.execute(
        select(RejectedRow, ImportRun)
        .join(ImportRun, RejectedRow.import_id == ImportRun.id)
        .order_by(ImportRun.imported_at.desc(), RejectedRow.source_row_number)
        .limit(500)
    ).all()
    return {
        "items": [
            {
                "id": run.id,
                "file_name": run.file_name,
                "file_hash": run.file_hash,
                "source_kind": run.source_kind,
                "status": run.status,
                "total_rows": run.total_rows,
                "accepted_rows": run.accepted_rows,
                "rejected_rows": run.rejected_rows,
                "duplicate_rows": run.duplicate_rows,
                "imported_at": run.imported_at.isoformat(),
            }
            for run in runs
        ],
        "rejected_rows": [
            {
                "import_id": run.id,
                "file_name": run.file_name,
                "row_number": item.source_row_number,
                "reason": item.reason,
                "raw_json": item.raw_json,
            }
            for item, run in rejects
        ],
    }


