"""Dashboard summaries kept separate by source, unit, and recorded-cost completeness."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies import get_session
from api.errors import APIProblem
from inventory_app.analytics import aggregate_consumption
from inventory_app.data_quality import history_to_frame
from inventory_app.inventory import local_today
from inventory_app.models import Customer, Material, ProjectSite, SalesRecord
from inventory_app.reports import current_inventory_report

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    site_id: int | None = Query(default=None, gt=0),
    material_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_session),
):
    today = local_today()
    if start_date is None:
        start_date = today - timedelta(days=29)
    if end_date is None:
        end_date = today
    if start_date > end_date:
        raise APIProblem(422, "invalid_date_range", "Start date must not be after end date.")

    sites = session.scalars(select(ProjectSite).where(ProjectSite.is_active.is_(True)).order_by(ProjectSite.identifier)).all()
    materials = session.scalars(select(Material).where(Material.is_active.is_(True)).order_by(Material.name)).all()
    selected_site = session.get(ProjectSite, site_id) if site_id is not None else (sites[0] if sites else None)
    selected_material = session.get(Material, material_id) if material_id is not None else (materials[0] if materials else None)
    if site_id is not None and (selected_site is None or not selected_site.is_active):
        raise APIProblem(404, "site_not_found", "Active project site not found.")
    if material_id is not None and (selected_material is None or not selected_material.is_active):
        raise APIProblem(404, "material_not_found", "Active material not found.")

    overview_balances = current_inventory_report(session)
    overview_initialized = overview_balances.loc[overview_balances["current_usable_stock"].notna()]
    overview_all_costed = not overview_initialized.empty and bool((overview_initialized["cost_basis_status"] == "Fully costed").all())
    overview_stock_value = (
        float(overview_initialized["recorded_stock_value_inr"].fillna(0).sum())
        if overview_all_costed else None
    )
    overview_low = int(overview_balances["reorder_alert"].fillna(False).astype(bool).sum())
    overview_out = int((overview_initialized["current_usable_stock"] <= 0).sum())

    balances = overview_balances.copy()
    if selected_site is not None:
        balances = balances.loc[balances["site"] == selected_site.identifier]
    if selected_material is not None:
        balances = balances.loc[balances["material"] == selected_material.name]
    initialized = balances.loc[balances["current_usable_stock"].notna()]
    all_costed = not initialized.empty and bool((initialized["cost_basis_status"] == "Fully costed").all())
    if all_costed:
        stock_value = float(initialized["recorded_stock_value_inr"].fillna(0).sum())
        stock_value_status = "Fully costed from recorded operational costs"
    elif initialized.empty:
        stock_value = None
        stock_value_status = "No initialized stock in this selection"
    else:
        stock_value = None
        stock_value_status = "Unavailable — one or more balances lack a complete recorded cost basis"
    low_stock = balances.loc[balances["reorder_alert"] == True]
    alerts = [
        {
            "site": row.site,
            "material": row.material,
            "unit": row.unit,
            "current_stock": row.current_usable_stock,
            "reorder_point_qty": row.reorder_point_qty,
            "status": row.reorder_status,
        }
        for row in low_stock.itertuples(index=False)
    ]

    sales_query = select(SalesRecord, ProjectSite, Material, Customer).join(
        ProjectSite, SalesRecord.site_id == ProjectSite.id
    ).join(Material, SalesRecord.material_id == Material.id).outerjoin(Customer, SalesRecord.customer_id == Customer.id).where(
        SalesRecord.sale_date >= start_date,
        SalesRecord.sale_date <= end_date,
    )
    if selected_site is not None:
        sales_query = sales_query.where(SalesRecord.site_id == selected_site.id)
    if selected_material is not None:
        sales_query = sales_query.where(SalesRecord.material_id == selected_material.id)
    sales_rows = session.execute(sales_query.order_by(SalesRecord.sale_date, SalesRecord.id)).all()
    top_query = select(
        Material.name,
        Material.unit,
        func.sum(SalesRecord.quantity).label("quantity"),
        func.sum(SalesRecord.revenue_inr).label("revenue_inr"),
        func.count(SalesRecord.id).label("sale_count"),
    ).join(Material, SalesRecord.material_id == Material.id).where(
        SalesRecord.sale_date >= start_date,
        SalesRecord.sale_date <= end_date,
    )
    if selected_site is not None:
        top_query = top_query.where(SalesRecord.site_id == selected_site.id)
    top_materials = [
        {
            "material": name,
            "unit": unit,
            "quantity": float(quantity or 0),
            "revenue_inr": float(total_revenue or 0),
            "sale_count": int(sale_count),
        }
        for name, unit, quantity, total_revenue, sale_count in session.execute(
            top_query.group_by(Material.name, Material.unit)
            .order_by(func.sum(SalesRecord.revenue_inr).desc(), Material.name)
            .limit(5)
        ).all()
    ]
    revenue = sum((Decimal(sale.revenue_inr) for sale, *_ in sales_rows), Decimal("0"))
    costed = [sale for sale, *_ in sales_rows if sale.cost_of_goods_sold_inr is not None]
    margin_complete = bool(sales_rows) and len(costed) == len(sales_rows)
    gross_margin = sum((Decimal(sale.gross_margin_inr) for sale in costed if sale.gross_margin_inr is not None), Decimal("0")) if margin_complete else None

    historical = history_to_frame(session)
    historical_trend = []
    historical_coverage = None
    if selected_site is not None and selected_material is not None and not historical.empty:
        selected_history = historical.loc[
            (historical["project_site_id"] == selected_site.identifier)
            & (historical["material"] == selected_material.name)
        ].copy()
        if not selected_history.empty:
            observed_dates = pd.to_datetime(selected_history["date"], errors="coerce").dropna()
            historical_coverage = {
                "from": observed_dates.min().date().isoformat(),
                "to": observed_dates.max().date().isoformat(),
                "observations": int(len(selected_history)),
            }
            aggregated = aggregate_consumption(selected_history, "Monthly")
            historical_trend = [
                {"period": pd.Timestamp(row.period).date().isoformat(), "quantity": float(row.consumption_qty), "unit": row.unit}
                for row in aggregated.itertuples(index=False)
            ]

    sales_trend = []
    for sale, _, _, _ in sales_rows:
        period = pd.Timestamp(sale.sale_date).to_period("M").start_time.date().isoformat()
        sales_trend.append({"period": period, "revenue_inr": float(sale.revenue_inr)})
    if sales_trend:
        sales_trend = (
            pd.DataFrame(sales_trend)
            .groupby("period", as_index=False)["revenue_inr"]
            .sum()
            .to_dict(orient="records")
        )

    return {
        "as_of_date": today.isoformat(),
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "selection": {
            "site_id": selected_site.id if selected_site else None,
            "site": selected_site.identifier if selected_site else None,
            "material_id": selected_material.id if selected_material else None,
            "material": selected_material.name if selected_material else None,
            "unit": selected_material.unit if selected_material else None,
        },
        "summary": {
            "active_sites": len(sites),
            "active_materials": len(materials),
            "initialized_ledgers": int(balances["current_usable_stock"].notna().sum()),
            "reorder_alerts": len(alerts),
            "recorded_stock_value_inr": stock_value,
            "stock_value_status": stock_value_status,
            "sales_count": len(sales_rows),
            "sales_revenue_inr": float(revenue.quantize(Decimal("0.01"))),
            "gross_margin_inr": float(gross_margin.quantize(Decimal("0.01"))) if gross_margin is not None else None,
            "margin_status": "Available" if margin_complete else ("No sales in period" if not sales_rows else "Unavailable — recorded cost basis is incomplete"),
            "margin_unavailable_sales_count": len(sales_rows) - len(costed),
            "all_pairs_initialized": int(len(overview_initialized)),
            "all_pairs_low_stock": overview_low,
            "all_pairs_out_of_stock": overview_out,
            "all_pairs_recorded_stock_value_inr": overview_stock_value,
            "all_pairs_stock_value_status": (
                "Fully costed from recorded operational costs" if overview_all_costed
                else "No initialized stock in the catalogue" if overview_initialized.empty
                else "Unavailable — one or more balances lack a complete recorded cost basis"
            ),
        },
        "alerts": alerts[:30],
        "top_materials": top_materials,
        "historical_consumption_source": "Historical CSV",
        "historical_coverage": historical_coverage,
        "historical_consumption_trend": historical_trend,
        "operational_sales_revenue_trend": sales_trend,
        "source_separation_note": "Historical CSV observations and operational sales are returned as separate series and are never combined.",
    }
