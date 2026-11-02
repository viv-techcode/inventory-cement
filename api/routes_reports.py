"""CSV/XLSX exports for operations and the strictly separate historical source."""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.errors import APIProblem
from inventory_app.data_quality import build_data_quality_report, history_to_frame
from inventory_app.models import Customer, Material, ProjectSite, SalesRecord
from inventory_app.reports import (
    current_inventory_report,
    dataframe_csv_bytes,
    excel_workbook_bytes,
    forecast_metadata_report,
    import_quality_report,
    inventory_report,
)
from api.serializers import sale_payload

router = APIRouter(prefix="/api", tags=["reports"])


def _catalog_names(session: Session, site_id: int | None, material_id: int | None):
    site_name = None
    material_name = None
    if site_id is not None:
        site = session.get(ProjectSite, site_id)
        if site is None:
            raise APIProblem(404, "site_not_found", "Project site not found.")
        site_name = site.identifier
    if material_id is not None:
        material = session.get(Material, material_id)
        if material is None:
            raise APIProblem(404, "material_not_found", "Material not found.")
        material_name = material.name
    return site_name, material_name


def _filtered_transactions(session: Session, site_id, material_id, start_date, end_date, search):
    frame = inventory_report(session)
    site_name, material_name = _catalog_names(session, site_id, material_id)
    if site_name is not None:
        frame = frame.loc[frame["site"] == site_name]
    if material_name is not None:
        frame = frame.loc[frame["material"] == material_name]
    if start_date is not None and not frame.empty:
        frame = frame.loc[pd.to_datetime(frame["date"]).dt.date >= start_date]
    if end_date is not None and not frame.empty:
        frame = frame.loc[pd.to_datetime(frame["date"]).dt.date <= end_date]
    if search and not frame.empty:
        columns = [column for column in ("site", "material", "transaction_type", "reference", "source", "notes") if column in frame]
        mask = frame[columns].astype(str).apply(lambda series: series.str.contains(search, case=False, na=False)).any(axis=1)
        frame = frame.loc[mask]
    return frame.reset_index(drop=True)


def _filtered_sales(session: Session, site_id, material_id, customer_id, start_date, end_date, search):
    query = select(SalesRecord, ProjectSite, Material, Customer).join(
        ProjectSite, SalesRecord.site_id == ProjectSite.id
    ).join(Material, SalesRecord.material_id == Material.id).outerjoin(Customer, SalesRecord.customer_id == Customer.id)
    if site_id is not None:
        query = query.where(SalesRecord.site_id == site_id)
    if material_id is not None:
        query = query.where(SalesRecord.material_id == material_id)
    if customer_id is not None:
        query = query.where(SalesRecord.customer_id == customer_id)
    if start_date is not None:
        query = query.where(SalesRecord.sale_date >= start_date)
    if end_date is not None:
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
    rows = session.execute(query.order_by(SalesRecord.sale_date.desc(), SalesRecord.id.desc())).all()
    return pd.DataFrame.from_records([
        sale_payload(sale, site=site, material=material, customer=customer)
        for sale, site, material, customer in rows
    ])


def _historical_frame(session: Session, site_id, material_id, start_date, end_date):
    history = history_to_frame(session)
    site_name, material_name = _catalog_names(session, site_id, material_id)
    if site_name is not None:
        history = history.loc[history["project_site_id"] == site_name]
    if material_name is not None:
        history = history.loc[history["material"] == material_name]
    if start_date is not None and not history.empty:
        history = history.loc[pd.to_datetime(history["date"]).dt.date >= start_date]
    if end_date is not None and not history.empty:
        history = history.loc[pd.to_datetime(history["date"]).dt.date <= end_date]
    return history.reset_index(drop=True)


def _csv_response(frame: pd.DataFrame, filename: str) -> Response:
    return Response(
        content=dataframe_csv_bytes(frame),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _check_date_range(start_date: date | None, end_date: date | None):
    if start_date and end_date and start_date > end_date:
        raise APIProblem(422, "invalid_date_range", "Start date must not be after end date.")


@router.get("/reports/ledger.csv")
def export_ledger(
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = Query(default=None, max_length=160),
    session: Session = Depends(get_session),
):
    _check_date_range(start_date, end_date)
    return _csv_response(_filtered_transactions(session, site_id, material_id, start_date, end_date, search), "inventory_ledger.csv")


@router.get("/reports/sales.csv")
def export_sales(
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = Query(default=None, max_length=160),
    session: Session = Depends(get_session),
):
    _check_date_range(start_date, end_date)
    return _csv_response(_filtered_sales(session, site_id, material_id, customer_id, start_date, end_date, search), "operational_sales.csv")


@router.get("/reports/current-inventory.csv")
def export_current_inventory(
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    session: Session = Depends(get_session),
):
    frame = current_inventory_report(session)
    site_name, material_name = _catalog_names(session, site_id, material_id)
    if site_name is not None:
        frame = frame.loc[frame["site"] == site_name]
    if material_name is not None:
        frame = frame.loc[frame["material"] == material_name]
    return _csv_response(frame.reset_index(drop=True), "current_inventory_balances.csv")


@router.get("/reports/historical.csv")
def export_historical(
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_session),
):
    _check_date_range(start_date, end_date)
    return _csv_response(_historical_frame(session, site_id, material_id, start_date, end_date), "historical_csv_observations.csv")


@router.get("/reports/forecast-metadata.csv")
def export_forecast_metadata(session: Session = Depends(get_session)):
    return _csv_response(forecast_metadata_report(session), "forecast_evaluation_metadata.csv")


@router.get("/reports/quality.csv")
def export_quality(session: Session = Depends(get_session)):
    report = build_data_quality_report(history_to_frame(session))
    rows = [
        {"check": "Historical rows", "result": report.get("row_count"), "note": "Imported Historical CSV observations only."},
        {"check": "Columns", "result": report.get("column_count"), "note": "Verified source fields."},
        {"check": "Sites", "result": report.get("site_count"), "note": "Historical source identifiers."},
        {"check": "Materials", "result": report.get("material_count"), "note": "Historical source material names."},
        {"check": "Date minimum", "result": report.get("date_min"), "note": "Observed source date."},
        {"check": "Date maximum", "result": report.get("date_max"), "note": "Observed source date; not a current stock date."},
        {"check": "Exact duplicate rows", "result": report.get("duplicate_exact_rows"), "note": "Source-quality check."},
        {"check": "WPI reference month mismatches", "result": report.get("wpi_reference_month_mismatches"), "note": "Month key only; no WPI index values supplied."},
    ]
    for warning in report.get("warnings", []):
        rows.append({"check": "Interpretation warning", "result": "Review", "note": warning})
    return _csv_response(pd.DataFrame.from_records(rows), "historical_data_quality.csv")


@router.get("/reports/workbook.xlsx")
def export_workbook(session: Session = Depends(get_session)):
    quality = build_data_quality_report(history_to_frame(session))
    quality_frame = pd.DataFrame.from_records([
        {"check": key, "result": value}
        for key, value in quality.items()
        if not isinstance(value, (dict, list))
    ])
    imports, rejected = import_quality_report(session)
    frames = {
        "Current inventory": current_inventory_report(session),
        "Operational ledger": inventory_report(session),
        "Operational sales": _filtered_sales(session, None, None, None, None, None, None),
        "Historical CSV": history_to_frame(session),
        "Forecast metadata": forecast_metadata_report(session),
        "Import history": imports,
        "Rejected rows": rejected,
        "Data quality": quality_frame,
    }
    content = excel_workbook_bytes(frames)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="construction_inventory_reports.xlsx"'},
    )
