"""Acceptance checks for the ledger-backed system."""
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from itertools import product
from pathlib import Path

from sqlalchemy import func, select

from inventory_app.database import Database, initialize_database
from api.routes_dashboard import dashboard as dashboard_page
from api.routes_data import data_quality
from api.routes_inventory import list_balances
from api.routes_procurement import purchase_orders
from api.routes_replenishment import planner_history
from api.routes_forecasting import forecast_leaderboard
from inventory_app.forecast_sources import operational_sales_history
from inventory_app.costing import weighted_average_issue_cost
from inventory_app.data_quality import history_to_frame
from inventory_app.forecasting import load_or_naive_assessment
from inventory_app.inventory import get_current_balance
from inventory_app.models import (
    HistoricalObservation, InventoryTransaction, Material, PlannerRun, ProjectSite, PurchaseOrderLine,
    SalesRecord, Supplier,
)
from inventory_app.procurement import (
    create_purchase_order, post_receipt, transition_purchase_order,
)
from inventory_app.sales import create_sale
from scripts.load_operations import ensure_baseline_planner_history, ensure_ledger_baseline

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "construction_materials_ledger.csv"
AS_OF = date(2026, 7, 2)


def fresh_database(path: Path) -> Database:
    db = Database(f"sqlite:///{path.as_posix()}")
    initialize_database(db)
    ensure_ledger_baseline(db, LEDGER)
    ensure_baseline_planner_history(db, LEDGER)
    return db


def test_ledger_contract_and_running_stock():
    with LEDGER.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8490
    assert rows[0]["date"] == "2024-04-01"
    assert rows[-1]["date"] == "2026-07-02"
    assert [row["event_id"] for row in rows] == [f"L{i:06d}" for i in range(1, 8491)]
    assert len({row["site"] for row in rows}) == 6
    assert len({row["material"] for row in rows}) == 15
    stock = defaultdict(Decimal)
    for row in rows:
        key = (row["site"], row["material"])
        qty = Decimal(row["quantity"])
        if row["event_type"] in {"opening_balance", "purchase_receipt", "adjustment"}:
            stock[key] += qty
        elif row["event_type"] == "sale":
            stock[key] -= qty
        assert stock[key] >= 0


def test_clean_load_reconciles_and_is_idempotent(tmp_path):
    db = fresh_database(tmp_path / "ledger.sqlite")
    try:
        with db.session() as session:
            assert session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source_tag == "baseline_ledger")) == 8490
            assert session.scalar(select(func.count(SalesRecord.id))) == 7932
            assert session.scalar(select(func.count(PurchaseOrderLine.id))) > 0
            assert session.scalar(select(func.count(Supplier.id))) > 0
            assert session.scalar(select(func.count(PlannerRun.id))) == 90
            latest_observation = session.scalar(select(func.max(HistoricalObservation.observation_datetime)))
            assert latest_observation.date() == AS_OF
            assert session.scalar(select(func.sum(SalesRecord.revenue_inr))).quantize(Decimal("1")) == Decimal("134998970")
            forecast_rows = operational_sales_history(session)
            assert len(forecast_rows) == 7932
        assert ensure_ledger_baseline(db, LEDGER) is None
    finally:
        db.dispose()


def test_post_load_sale_and_receipt_update_stock_without_retraining(tmp_path):
    db = fresh_database(tmp_path / "operations.sqlite")
    try:
        with db.session() as session, session.begin():
            pairs = product(session.scalars(select(ProjectSite).order_by(ProjectSite.id)).all(), session.scalars(select(Material).order_by(Material.id)).all())
            site, material, opening = next((site, material, balance) for site, material in pairs
                if (balance := get_current_balance(session, site.id, material.id, as_of=AS_OF)) is not None and balance > 2)
            training_count = len(operational_sales_history(session))
            _, expected_weighted_average = weighted_average_issue_cost(
                session, site_id=site.id, material_id=material.id,
                quantity=Decimal("1"), sale_date=AS_OF,
            )
            sale, _ = create_sale(session, idempotency_key="LIVE-SALE-1", site_id=site.id,
                material_id=material.id, customer_id=None, quantity=Decimal("1"),
                unit=material.unit, unit_sale_price_inr=Decimal("1000"), sale_date=AS_OF,
                reference="INV-LIVE-1", source_tag="operator")
            assert sale.source_tag == "operator"
            assert sale.unit_cost_basis_inr == expected_weighted_average
            assert get_current_balance(session, site.id, material.id, as_of=AS_OF) == opening - Decimal("1")
            assert len(operational_sales_history(session)) == training_count

            supplier = session.scalar(select(Supplier).order_by(Supplier.id))
            po = create_purchase_order(session, idempotency_key="LIVE-PO-1", supplier_id=supplier.id,
                site_id=site.id, order_date=AS_OF, expected_delivery_date=AS_OF,
                lines=[{"material_id":material.id,"quantity":Decimal("2"),"unit":material.unit,"unit_price_inr":Decimal("100")}])
            transition_purchase_order(session, po.id, "Pending approval")
            transition_purchase_order(session, po.id, "Approved")
            line = session.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id))
            before_receipt = get_current_balance(session, site.id, material.id, as_of=AS_OF)
            post_receipt(session, idempotency_key="LIVE-GRN-1", receipt_reference="GRN-LIVE-1",
                purchase_order_line_id=line.id, quantity=Decimal("2"), unit=material.unit,
                receipt_date=AS_OF)
            assert get_current_balance(session, site.id, material.id, as_of=AS_OF) == before_receipt + Decimal("2")
    finally:
        db.dispose()


def test_operational_pages_reconcile_to_baseline(tmp_path):
    db = fresh_database(tmp_path / "pages.sqlite")
    try:
        with db.session() as session:
            dash = dashboard_page(None, None, date(2024, 4, 1), AS_OF, session)
            inventory = list_balances(None, None, False, None, session)
            orders = purchase_orders(session)
            quality = data_quality(session)
            assert dash["as_of_date"] == "2026-07-02"
            selected = dash["selection"]
            expected_count = session.scalar(select(func.count(SalesRecord.id)).where(
                SalesRecord.site_id == selected["site_id"], SalesRecord.material_id == selected["material_id"],
                SalesRecord.sale_date >= date(2024, 4, 1), SalesRecord.sale_date <= AS_OF))
            expected_revenue = session.scalar(select(func.sum(SalesRecord.revenue_inr)).where(
                SalesRecord.site_id == selected["site_id"], SalesRecord.material_id == selected["material_id"],
                SalesRecord.sale_date >= date(2024, 4, 1), SalesRecord.sale_date <= AS_OF))
            assert dash["summary"]["sales_count"] == expected_count
            assert Decimal(str(dash["summary"]["sales_revenue_inr"])).quantize(Decimal("0.01")) == Decimal(expected_revenue).quantize(Decimal("0.01"))
            assert inventory["total"] == 90
            assert len(orders["items"]) == 28
            assert quality["report"]["row_count"] == 8490
            assert quality["report"]["stock_reconciles_pass"] is True
            assert quality["report"]["unit_consistency_pass"] is True
            history = planner_history(session)
            assert len(history["items"]) == 50
            assert all(item["created_at"].startswith("2026-07-02") for item in history["items"])
    finally:
        db.dispose()


def test_committed_forecasts_load_without_local_model_artifacts(tmp_path):
    db = fresh_database(tmp_path / "committed-forecasts.sqlite")
    try:
        with db.session() as session:
            history = history_to_frame(session)
            site = str(history.project_site_id.iloc[0])
            material = str(history.material.iloc[0])
            assessment = load_or_naive_assessment(db, history, site=site, material=material,
                frequency="weekly", horizon_days=30)
            leaderboard = forecast_leaderboard(session)
            assert assessment["cache_hit"] is True
            assert assessment["best_model"] in {row["model"] for row in assessment["metrics"]}
            assert len(assessment["holdout_predictions"][assessment["best_model"]]) == 16
            assert len(assessment["forecasts"][assessment["best_model"]]) == 5
            assert leaderboard["pair_count"] == 90
    finally:
        db.dispose()


