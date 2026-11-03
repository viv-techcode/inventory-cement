"""CSV and Excel export helpers with predictable headings and empty-state support."""
from __future__ import annotations

from io import BytesIO
import re
from typing import Mapping

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.costing import inventory_cost_summary
from inventory_app.inventory import get_current_balance, local_today
from inventory_app.reorder import stock_reorder_status
from inventory_app.models import (
    ForecastArtifact,
    ImportRun,
    InventoryTransaction,
    Material,
    ProjectSite,
    PurchaseOrder,
    PurchaseOrderLine,
    ReceiptRecord,
    RejectedRow,
    Supplier,
)


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")


def excel_workbook_bytes(sheets: Mapping[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        used: set[str] = set()
        for sheet_name, frame in sheets.items():
            clean = re.sub(r"[\\/*?:\[\]]", " ", str(sheet_name)).strip()[:31] or "Report"
            candidate = clean
            suffix = 2
            while candidate.lower() in used:
                tail = f" {suffix}"
                candidate = f"{clean[:31-len(tail)]}{tail}"
                suffix += 1
            used.add(candidate.lower())
            frame.to_excel(writer, sheet_name=candidate, index=False)
            worksheet = writer.sheets[candidate]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                letter = column_cells[0].column_letter
                max_len = max((len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells[:200]), default=10)
                worksheet.column_dimensions[letter].width = min(max(max_len + 2, 12), 42)
    return output.getvalue()


def inventory_report(session: Session) -> pd.DataFrame:
    txns = session.execute(
        select(InventoryTransaction, ProjectSite, Material)
        .join(ProjectSite, InventoryTransaction.site_id == ProjectSite.id)
        .join(Material, InventoryTransaction.material_id == Material.id)
        .order_by(InventoryTransaction.transaction_date.desc(), InventoryTransaction.id.desc())
    ).all()
    records = []
    for txn, site, material in txns:
        records.append({
            "transaction_id": txn.id,
            "date": txn.transaction_date,
            "site": site.identifier,
            "material": material.name,
            "transaction_type": txn.transaction_type,
            "quantity": float(txn.quantity),
            "unit": txn.unit,
            "recorded_unit_cost_inr": float(txn.unit_cost_inr) if txn.unit_cost_inr is not None else None,
            "reference": txn.reference,
            "source": txn.source,
            "notes": txn.notes,
        })
    columns = ["transaction_id", "date", "site", "material", "transaction_type", "quantity", "unit", "recorded_unit_cost_inr", "reference", "source", "notes"]
    return pd.DataFrame.from_records(records, columns=columns)


def current_inventory_report(session: Session) -> pd.DataFrame:
    """Current ledger balances and recorded-cost valuation; unknown values stay blank."""
    sites = session.scalars(select(ProjectSite).order_by(ProjectSite.identifier)).all()
    materials = session.scalars(select(Material).order_by(Material.name)).all()
    records = []
    as_of = local_today()
    for site in sites:
        for material in materials:
            cost = inventory_cost_summary(session, site_id=site.id, material_id=material.id, as_of=as_of)
            balance = cost["current_stock"]
            if balance is None:
                status = "Not initialized"
            elif balance < 0:
                status = "Ledger review"
            else:
                status = "Known operational balance"
            reorder = stock_reorder_status(session, site.id, material.id, as_of=as_of)
            records.append({
                "as_of_date": as_of,
                "site": site.identifier,
                "material": material.name,
                "unit": material.unit,
                "stock_status": status,
                "current_usable_stock": float(balance) if balance is not None else None,
                "reorder_status": reorder["status"],
                "reorder_point_qty": float(reorder["reorder_point_qty"]) if reorder["reorder_point_qty"] is not None else None,
                "reorder_alert": bool(reorder["alert"]),
                "recorded_stock_value_inr": float(cost["stock_value_inr"]) if cost["stock_value_inr"] is not None else None,
                "known_cost_value_inr": float(cost["known_cost_value_inr"]) if cost["known_cost_value_inr"] is not None else None,
                "costed_quantity": float(cost["costed_quantity"]) if cost["costed_quantity"] is not None else None,
                "uncosted_quantity": float(cost["uncosted_quantity"]) if cost["uncosted_quantity"] is not None else None,
                "cost_basis_status": cost["cost_basis_status"],
                "reference_unit_price_inr": float(material.benchmark_unit_price_inr) if material.benchmark_unit_price_inr is not None else None,
                "reference_price_basis": material.price_basis,
            })
    columns = [
        "as_of_date", "site", "material", "unit", "stock_status", "current_usable_stock",
        "reorder_status", "reorder_point_qty", "reorder_alert", "recorded_stock_value_inr",
        "known_cost_value_inr", "costed_quantity", "uncosted_quantity", "cost_basis_status",
        "reference_unit_price_inr", "reference_price_basis",
    ]
    return pd.DataFrame.from_records(records, columns=columns)


def purchase_order_report(session: Session) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = session.execute(
        select(PurchaseOrder, Supplier, ProjectSite)
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .join(ProjectSite, PurchaseOrder.site_id == ProjectSite.id)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
    ).all()
    header_rows = []
    line_rows = []
    receipt_rows = []
    for order, supplier, site in orders:
        lines = session.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)).all()
        total = 0.0
        for line in lines:
            material = session.get(Material, line.material_id)
            outstanding = float(line.quantity_ordered - line.quantity_received)
            line_total = float(line.quantity_ordered * line.unit_price_inr)
            total += line_total
            line_rows.append({
                "po_number": order.po_number,
                "site": site.identifier,
                "supplier": supplier.name,
                "status": order.status,
                "material": material.name if material else "",
                "quantity_ordered": float(line.quantity_ordered),
                "quantity_received": float(line.quantity_received),
                "outstanding_quantity": outstanding,
                "unit": line.unit,
                "unit_price_inr": float(line.unit_price_inr),
                "estimated_line_value_inr": line_total,
                "expected_delivery_date": order.expected_delivery_date,
            })
            receipts = session.scalars(select(ReceiptRecord).where(ReceiptRecord.purchase_order_line_id == line.id)).all()
            for receipt in receipts:
                receipt_rows.append({
                    "receipt_reference": receipt.receipt_reference,
                    "po_number": order.po_number,
                    "material": material.name if material else "",
                    "quantity": float(receipt.quantity),
                    "unit": receipt.unit,
                    "receipt_date": receipt.receipt_date,
                    "posted_to_inventory_transaction_id": receipt.inventory_transaction_id,
                })
        header_rows.append({
            "po_number": order.po_number,
            "supplier": supplier.name,
            "site": site.identifier,
            "status": order.status,
            "order_date": order.order_date,
            "expected_delivery_date": order.expected_delivery_date,
            "estimated_order_value_inr": total,
            "notes": order.notes,
        })
    return (
        pd.DataFrame.from_records(header_rows, columns=["po_number", "supplier", "site", "status", "order_date", "expected_delivery_date", "estimated_order_value_inr", "notes"]),
        pd.DataFrame.from_records(line_rows, columns=["po_number", "site", "supplier", "status", "material", "quantity_ordered", "quantity_received", "outstanding_quantity", "unit", "unit_price_inr", "estimated_line_value_inr", "expected_delivery_date"]),
        pd.DataFrame.from_records(receipt_rows, columns=["receipt_reference", "po_number", "material", "quantity", "unit", "receipt_date", "posted_to_inventory_transaction_id"]),
    )


def import_quality_report(session: Session) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs = session.scalars(select(ImportRun).order_by(ImportRun.imported_at.desc())).all()
    rejected = session.execute(
        select(RejectedRow, ImportRun)
        .join(ImportRun, RejectedRow.import_id == ImportRun.id)
        .order_by(ImportRun.imported_at.desc(), RejectedRow.source_row_number)
    ).all()
    run_df = pd.DataFrame.from_records([
        {
            "import_id": run.id,
            "file_name": run.file_name,
            "file_sha256": run.file_hash,
            "source_kind": run.source_kind,
            "status": run.status,
            "total_rows": run.total_rows,
            "accepted_rows": run.accepted_rows,
            "rejected_rows": run.rejected_rows,
            "duplicate_rows": run.duplicate_rows,
            "imported_at": run.imported_at,
        }
        for run in runs
    ], columns=["import_id", "file_name", "file_sha256", "source_kind", "status", "total_rows", "accepted_rows", "rejected_rows", "duplicate_rows", "imported_at"])
    rejected_df = pd.DataFrame.from_records([
        {
            "import_id": run.id,
            "file_name": run.file_name,
            "source_row_number": item.source_row_number,
            "reason": item.reason,
            "raw_row_json": item.raw_json,
        }
        for item, run in rejected
    ], columns=["import_id", "file_name", "source_row_number", "reason", "raw_row_json"])
    return run_df, rejected_df


def forecast_metadata_report(session: Session) -> pd.DataFrame:
    rows = session.scalars(select(ForecastArtifact).order_by(ForecastArtifact.trained_at.desc())).all()
    data = []
    for item in rows:
        import json
        metrics = json.loads(item.metrics_json or "{}")
        data.append({
            "site": item.site_identifier,
            "material": item.material_name,
            "frequency": item.frequency,
            "model": item.model_name,
            "status": metrics.get("status"),
            "model_version": item.model_version,
            "training_start": item.training_start,
            "training_end": item.training_end,
            "training_observations": item.training_observations,
            "evaluation_start": item.evaluation_start,
            "evaluation_end": item.evaluation_end,
            "evaluation_observations": item.evaluation_observations,
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "r2": metrics.get("r2"),
            "wape_pct": metrics.get("wape_pct"),
            "data_hash": item.data_hash,
            "trained_at": item.trained_at,
            "notes": item.notes,
        })
    columns = ["site", "material", "frequency", "model", "status", "model_version", "training_start", "training_end", "training_observations", "evaluation_start", "evaluation_end", "evaluation_observations", "mae", "rmse", "r2", "wape_pct", "data_hash", "trained_at", "notes"]
    return pd.DataFrame.from_records(data, columns=columns)
