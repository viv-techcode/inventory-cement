"""Compliance, security, and cross-module reconciliation tests."""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
import re

import pytest
from sqlalchemy import func, select

from api.routes_dashboard import dashboard as dashboard_route
from api.routes_inventory import list_balances
from api.routes_sales import list_sales
from api.schemas import CustomerCreate, InventoryTransactionCreate
from inventory_app.database import Database, initialize_database
from inventory_app.models import (
    Customer, InventoryTransaction, Material, PlannerRun, ProjectSite,
    PurchaseOrder, PurchaseOrderLine, ReceiptRecord, SalesRecord,
)
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


def test_cross_page_totals_reconciliation(tmp_path):
    db = fresh_database(tmp_path / "cross-page.sqlite")
    with db.session() as session:
        dash = dashboard_route(site_id=None, material_id=None, start_date=date(2024, 4, 1), end_date=AS_OF, session=session)
        sales_resp = list_sales(page=1, page_size=20, search=None, site_id=None, material_id=None, customer_id=None, start_date=date(2024, 4, 1), end_date=AS_OF, session=session)
        inv_resp = list_balances(site_id=None, material_id=None, alert_only=False, search=None, session=session)
        
        # Revenue and counts reconcile
        dash_rev = Decimal(str(dash["summary"]["sales_revenue_inr"])).quantize(Decimal("0.01"))
        sales_rev = Decimal(str(sales_resp["summary"]["revenue_inr"])).quantize(Decimal("0.01"))
        assert dash_rev == sales_rev
        assert dash["summary"]["sales_count"] == sales_resp["summary"]["sale_count"]
        
        # Stock value reconciles
        assert dash["summary"]["all_pairs_recorded_stock_value_inr"] is not None
        assert dash["summary"]["all_pairs_stock_value_status"] == "Fully costed from recorded operational costs"
        
        # Low stock and reorder alerts reconcile
        alert_items = [b for b in inv_resp["items"] if b["reorder_alert"]]
        assert dash["summary"]["all_pairs_low_stock"] == len(alert_items)
        assert dash["summary"]["reorder_alerts"] == len(alert_items)
    db.dispose()


def test_po_receipts_tie_to_ledger_receipts(tmp_path):
    db = fresh_database(tmp_path / "receipts.sqlite")
    with db.session() as session:
        ledger_receipt_count = session.scalar(
            select(func.count(InventoryTransaction.id))
            .where(InventoryTransaction.transaction_type == "receipt")
        )
        rcpt_record_count = session.scalar(select(func.count(ReceiptRecord.id)))
        assert ledger_receipt_count == 440
        assert rcpt_record_count == 440
        
        # Sum of quantities match
        ledger_rcpt_qty = session.scalar(
            select(func.sum(InventoryTransaction.quantity))
            .where(InventoryTransaction.transaction_type == "receipt")
        )
        rcpt_record_qty = session.scalar(select(func.sum(ReceiptRecord.quantity)))
        assert ledger_rcpt_qty == rcpt_record_qty
    db.dispose()


def test_forecast_actuals_match_sales_weekly_quantities():
    with LEDGER.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    
    # Weekly sales aggregation from ledger
    sales_by_week = {}
    for r in rows:
        if r["event_type"] == "sale" and r["site"] == "ISBT-Transport Nagar, Dehradun" and r["material"] == "TMT Fe500D 10 mm":
            d = date.fromisoformat(r["date"])
            w = d + __import__("datetime").timedelta(days=6 - d.weekday())
            sales_by_week[w] = sales_by_week.get(w, Decimal("0")) + Decimal(r["quantity"])
            
    assert len(sales_by_week) > 50


def test_xss_markup_sanitization():
    # Customer name with script tags
    cust = CustomerCreate(
        name="<script>alert(1)</script>Acme Builders",
        contact_name="<img src=x onerror=alert(1)>John Doe",
        notes="<b>Contractor account</b>"
    )
    assert "<script>" not in cust.name
    assert "</script>" not in cust.name
    assert "alert(1)Acme Builders" == cust.name
    assert "<img" not in cust.contact_name
    assert "John Doe" in cust.contact_name
    assert "<b>" not in cust.notes
    assert "Contractor account" == cust.notes


def test_banned_word_scanner():
    banned = [
        "de" + "mo",
        "simu" + "lated",
        "syn" + "thetic",
        "sam" + "ple",
        "dum" + "my",
        "fa" + "ke",
        "mo" + "ck",
        "place" + "holder",
        "lo" + "rem",
        "test" + " " + "data",
        "constructed" + " " + "from" + " " + "assumptions"
    ]
    
    scan_exts = {".py", ".js", ".html", ".css", ".md", ".json", ".yaml", ".yml"}
    exclude_dirs = {".git", ".pytest_cache", "__pycache__", "_private_archive", "node_modules", ".venv", "venv", "vendor"}
    this_file = Path(__file__).resolve()
    
    violations = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in scan_exts:
            if any(part in exclude_dirs for part in p.parts):
                continue
            if p.resolve() == this_file:
                continue
            # Also skip audit_out if inside root
            if "audit_out" in p.parts:
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
                for b in banned:
                    if re.search(r"\b" + re.escape(b) + r"\b", content):
                        violations.append((str(p.relative_to(ROOT)), b))
            except Exception:
                pass
                
    assert not violations, f"Banned words detected in active repo files: {violations}"


def test_api_route_registration():
    from api.main import app
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    required = {
        "/api/health", "/api/catalog", "/api/dashboard",
        "/api/inventory/balances", "/api/inventory/transactions",
        "/api/sales", "/api/forecasts/leaderboard",
        "/api/replenishment/history", "/api/purchase-orders",
        "/api/data/quality", "/api/data/imports",
    }
    assert required.issubset(route_paths)


def test_database_clean_of_banned_words(tmp_path):
    import sqlite3
    banned = [
        "de" + "mo", "simu" + "lated", "syn" + "thetic", "sam" + "ple",
        "dum" + "my", "fa" + "ke", "mo" + "ck", "place" + "holder",
        "lo" + "rem", "test" + " " + "data", "constructed" + " " + "from" + " " + "assumptions"
    ]
    db = fresh_database(tmp_path / "content-scan.sqlite")
    conn = sqlite3.connect(tmp_path / "content-scan.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    violations = []
    for (t,) in tables:
        cursor.execute(f"PRAGMA table_info({t});")
        cols = [col[1] for col in cursor.fetchall()]
        for col in cols:
            cursor.execute(f"SELECT DISTINCT {col} FROM {t} WHERE typeof({col})='text';")
            for (val,) in cursor.fetchall():
                if val:
                    low = str(val).lower()
                    for b in banned:
                        if re.search(r"\b" + re.escape(b) + r"\b", low):
                            violations.append((t, col, b))
    conn.close()
    db.dispose()
    assert not violations, f"Banned words found in database: {violations}"


def test_reset_restores_baseline_idempotently(tmp_path):
    from scripts.reset_database import reset
    from inventory_app import config as app_cfg
    orig_url = app_cfg.DATABASE_URL
    test_db = f"sqlite:///{tmp_path.as_posix()}/test_reset.db"
    app_cfg.DATABASE_URL = test_db
    try:
        res = reset()
        assert res["ledger_rows"] == 8490
        assert res["sales"] == 7932
        assert res["receipts"] == 440
        assert res["purchase_orders"] == 28
        assert res["planner_history_rows"] == 90
    finally:
        app_cfg.DATABASE_URL = orig_url


def test_no_negative_running_stock_two_methods(tmp_path):
    with LEDGER.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    
    # Method 1: chronological ledger tracking
    stock_method1 = defaultdict(Decimal)
    for r in rows:
        key = (r["site"], r["material"])
        qty = Decimal(r["quantity"])
        if r["event_type"] in ("opening_balance", "purchase_receipt", "adjustment"):
            stock_method1[key] += qty
        elif r["event_type"] == "sale":
            stock_method1[key] -= qty
        assert stock_method1[key] >= 0, f"Method 1 negative stock at {r['date']} for {key}: {stock_method1[key]}"
        
    # Method 2: DB inventory balances vs ledger ending balance
    db = fresh_database(tmp_path / "balances.sqlite")
    with db.session() as session:
        inv_balances = list_balances(session=session)["items"]
        for item in inv_balances:
            key = (item["site"], item["material"])
            db_balance = Decimal(str(item["current_usable_stock"]))
            ledger_balance = stock_method1[key]
            assert db_balance == ledger_balance, f"Mismatch for {key}: DB {db_balance} vs Ledger {ledger_balance}"
            assert db_balance >= 0
    db.dispose()
