"""Historical source inspection and idempotent CSV validation/import routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_database, get_session
from api.errors import APIProblem
from inventory_app.data_quality import build_data_quality_report, history_to_frame
from inventory_app.ingestion import EXPECTED_COLUMNS, import_dataframe, read_csv_bytes, sha256_bytes, validate_frame
from inventory_app.models import ImportRun, RejectedRow

router = APIRouter(prefix="/api", tags=["data"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _read_upload(file_name: str, raw: bytes):
    if not file_name.lower().endswith(".csv"):
        raise APIProblem(415, "unsupported_file", "Upload a .csv file.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise APIProblem(413, "upload_too_large", f"CSV uploads are limited to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        frame = read_csv_bytes(raw)
    except Exception as exc:
        raise APIProblem(422, "csv_unreadable", f"CSV could not be read: {exc}") from exc
    if frame.empty and len(frame.columns) == 0:
        raise APIProblem(422, "csv_empty", "The uploaded CSV has no readable header or records.")
    return frame


@router.get("/data/quality")
def data_quality(session: Session = Depends(get_session)):
    history = history_to_frame(session)
    report = build_data_quality_report(history)
    operational = session.scalars(select(ImportRun)).all()
    rejected_count = sum(run.rejected_rows for run in operational)
    return {
        "historical_source_label": "Construction Materials Dehradun Dataset",
        "operational_transactions_excluded": True,
        "report": report,
        "import_run_count": len(operational),
        "rejected_row_count": rejected_count,
        "required_columns": list(EXPECTED_COLUMNS),
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


@router.post("/data/validate")
async def validate_csv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    raw = await file.read()
    frame = _read_upload(file.filename or "upload.csv", raw)
    file_hash = sha256_bytes(raw)
    valid, rejected, summary = validate_frame(frame)
    prior = session.scalar(select(ImportRun).where(ImportRun.file_hash == file_hash))
    valid_preview = [
        {key: row.get(key) for key in EXPECTED_COLUMNS}
        for row in valid[:20]
    ]
    rejected_preview = [
        {
            "row_number": row["row_number"],
            "reason": row["reason"],
            "raw": row.get("raw", {}),
        }
        for row in rejected[:50]
    ]
    return {
        "file_name": file.filename,
        "file_hash": file_hash,
        "total_rows": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": [str(item) for item in frame.columns],
        "schema_errors": summary.get("schema_errors", []),
        "accepted_rows": len(valid),
        "rejected_rows": len(rejected),
        "validation_summary": summary,
        "valid_preview": valid_preview,
        "rejected_preview": rejected_preview,
        "already_imported": prior is not None,
        "prior_import_id": prior.id if prior is not None else None,
        "historical_only": True,
        "creates_operational_transactions": False,
    }


@router.post("/data/import", status_code=201)
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    confirm: bool = Form(default=False),
):
    if not confirm:
        raise APIProblem(422, "confirmation_required", "Confirm the validated preview before importing.")
    raw = await file.read()
    frame = _read_upload(file.filename or "upload.csv", raw)
    valid, rejected, summary = validate_frame(frame)
    if summary.get("schema_errors"):
        raise APIProblem(422, "schema_validation_failed", "The CSV schema does not match the required fields.", summary["schema_errors"])
    database = get_database(request)
    try:
        result = import_dataframe(
            database,
            frame,
            file_name=file.filename or "upload.csv",
            file_bytes=raw,
            source_kind="uploaded_csv",
        )
    except Exception as exc:
        raise APIProblem(409, "import_conflict", f"Import failed without reporting a partial success: {exc}") from exc
    return {
        "run_id": result.run_id,
        "file_hash": result.file_hash,
        "total_rows": result.total_rows,
        "accepted_rows": result.accepted_rows,
        "rejected_rows": result.rejected_rows,
        "duplicate_rows": result.duplicate_rows,
        "duplicate_file": result.duplicate_file,
        "message": result.message,
        "creates_operational_transactions": False,
    }
