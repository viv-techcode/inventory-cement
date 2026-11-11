from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from api.main import create_app
from inventory_app.database import Database
from inventory_app.forecast_sources import MIN_OPERATIONAL_SALES_PERIODS
from inventory_app.inventory import local_today
from inventory_app.models import HistoricalObservation, InventoryTransaction, SalesRecord
from conftest import SOURCE_CSV


@pytest.fixture
def api_client(fresh_db):
    app = create_app(database_url=fresh_db.url, auto_import_source=False)
    with TestClient(app) as client:
        yield client


def _create_pair(client, *, site="API Yard", material="API Cement", unit="bags"):
    site_response = client.post("/api/sites", json={
        "identifier": site, "name": site, "city": "Moradabad", "state": "Uttar Pradesh",
    })
    assert site_response.status_code == 201, site_response.text
    material_response = client.post("/api/materials", json={"name": material, "unit": unit})
    assert material_response.status_code == 201, material_response.text
    return site_response.json()["item"], material_response.json()["item"]


def _opening(client, site, material, *, quantity=10, unit_cost=None, key="open-api", day=None):
    body = {
        "idempotency_key": key,
        "site_id": site["id"],
        "material_id": material["id"],
        "transaction_type": "opening_balance",
        "quantity": quantity,
        "unit": material["unit"],
        "transaction_date": (day or local_today()).isoformat(),
        "notes": "Verified physical count",
        "unit_cost_inr": unit_cost,
    }
    response = client.post("/api/inventory/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_static_frontend_and_health_are_served_offline(api_client):
    root = api_client.get("/")
    assert root.status_code == 200
    assert "SITESTOCK" in root.text
    assert "https://" not in root.text
    assert api_client.get("/app.js").status_code == 200
    assert api_client.get("/styles.css").status_code == 200
    plotly = api_client.get("/vendor/plotly.min.js")
    assert plotly.status_code == 200
    assert len(plotly.content) > 1_000_000
    health = api_client.get("/api/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"


def test_inventory_routes_validation_adjustments_filters_and_export(api_client):
    site, material = _create_pair(api_client)
    _opening(api_client, site, material, quantity=10, unit_cost=4)
    receipt = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-receipt-1", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "receipt", "quantity": 5, "unit": material["unit"],
        "transaction_date": local_today().isoformat(), "unit_cost_inr": 6, "reference": "RCPT-5",
    })
    assert receipt.status_code == 201, receipt.text

    missing_reason = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-adjust-no-reason", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "adjustment", "quantity": -1, "unit": material["unit"],
        "transaction_date": local_today().isoformat(),
    })
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["code"] == "validation_error"

    adjustment = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-adjust-1", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "adjustment", "quantity": -1, "unit": material["unit"],
        "transaction_date": local_today().isoformat(), "reason": "Count correction",
    })
    assert adjustment.status_code == 201, adjustment.text

    bad_unit = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-wrong-unit", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "receipt", "quantity": 1, "unit": "m3",
        "transaction_date": local_today().isoformat(),
    })
    assert bad_unit.status_code == 422
    assert bad_unit.json()["error"]["code"] == "inventory_validation"

    future = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-future", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "receipt", "quantity": 1, "unit": material["unit"],
        "transaction_date": (local_today() + timedelta(days=1)).isoformat(),
    })
    assert future.status_code == 422

    negative = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-over-consume", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "consumption", "quantity": 99, "unit": material["unit"],
        "transaction_date": local_today().isoformat(),
    })
    assert negative.status_code == 409
    assert "negative balance" in negative.json()["error"]["message"].lower()

    duplicate = api_client.post("/api/inventory/transactions", json={
        "idempotency_key": "api-receipt-1", "site_id": site["id"], "material_id": material["id"],
        "transaction_type": "receipt", "quantity": 5, "unit": material["unit"],
        "transaction_date": local_today().isoformat(), "unit_cost_inr": 6, "reference": "RCPT-5",
    })
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_submission"

    balances = api_client.get(f"/api/inventory/balances?site_id={site['id']}&material_id={material['id']}").json()
    assert balances["total"] == 1
    assert balances["items"][0]["current_usable_stock"] == 14
    # FIFO removes one unit from the opening layer: 9 × 4 + 5 × 6 = 66.
    assert balances["items"][0]["cost_basis_status"] == "Fully costed"
    assert balances["items"][0]["recorded_stock_value_inr"] == pytest.approx(66.0)

    page = api_client.get(f"/api/inventory/transactions?site_id={site['id']}&material_id={material['id']}&page=1&page_size=1")
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["pages"] == 3
    filtered = api_client.get(f"/api/inventory/transactions?search=RCPT-5&site_id={site['id']}")
    assert filtered.json()["total"] == 1
    export = api_client.get(f"/api/reports/ledger.csv?site_id={site['id']}&material_id={material['id']}")
    assert export.status_code == 200 and "text/csv" in export.headers["content-type"]
    assert b"RCPT-5" in export.content and b"recorded_unit_cost_inr" in export.content


def test_sales_revenue_margin_customer_and_idempotency(api_client):
    site, material = _create_pair(api_client, site="Sales Yard", material="Cement Sale", unit="50-kg bags")
    _opening(api_client, site, material, quantity=10, unit_cost=5, key="sales-opening")
    customer_response = api_client.post("/api/customers", json={"name": "Acme Build", "email": "ops@example.test"})
    assert customer_response.status_code == 201
    customer = customer_response.json()["item"]
    body = {
        "idempotency_key": "sale-key-1", "site_id": site["id"], "material_id": material["id"],
        "customer_id": customer["id"], "quantity": 2, "unit": material["unit"],
        "unit_sale_price_inr": 12.5, "sale_date": local_today().isoformat(), "reference": "INV-001",
    }
    sale_response = api_client.post("/api/sales", json=body)
    assert sale_response.status_code == 201, sale_response.text
    sale = sale_response.json()
    assert sale["item"]["revenue_inr"] == 25
    assert sale["item"]["cost_of_goods_sold_inr"] == 10
    assert sale["item"]["gross_margin_inr"] == 15
    assert sale["item"]["customer"] == "Acme Build"
    assert sale["current_balance"] == 8

    retry = api_client.post("/api/sales", json=body)
    assert retry.status_code == 201
    assert retry.json()["created"] is False
    changed = api_client.post("/api/sales", json={**body, "quantity": 1})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "duplicate_submission"

    summary = api_client.get(f"/api/sales?site_id={site['id']}&material_id={material['id']}").json()
    assert summary["summary"]["sale_count"] == 1
    assert summary["summary"]["revenue_inr"] == 25
    assert summary["summary"]["gross_margin_inr"] == 15
    assert summary["summary"]["cost_basis_complete"] is True
    assert summary["items"][0]["margin_status"] == "Available"

    over_sale = api_client.post("/api/sales", json={**body, "idempotency_key": "sale-over", "quantity": 99})
    assert over_sale.status_code == 409
    wrong_unit = api_client.post("/api/sales", json={**body, "idempotency_key": "sale-unit", "unit": "kg"})
    assert wrong_unit.status_code == 422
    future_sale = api_client.post("/api/sales", json={**body, "idempotency_key": "sale-future", "sale_date": (local_today() + timedelta(days=1)).isoformat()})
    assert future_sale.status_code == 422

    sales_export = api_client.get(f"/api/reports/sales.csv?site_id={site['id']}")
    assert sales_export.status_code == 200
    assert b"Acme Build" in sales_export.content and b"gross_margin_inr" in sales_export.content


def test_reorder_rules_alerts_dashboard_and_current_value(api_client):
    site, material = _create_pair(api_client, site="Alert Yard", material="Blocks", unit="pieces")
    _opening(api_client, site, material, quantity=3, unit_cost=2, key="alert-opening")
    rule = api_client.put(f"/api/reorder-rules/{site['id']}/{material['id']}", json={
        "site_id": site["id"], "material_id": material["id"], "unit": "pieces",
        "reorder_point_qty": 5, "lead_time_days": 4, "safety_stock_days": 3,
    })
    assert rule.status_code == 200, rule.text
    balance = api_client.get(f"/api/inventory/balances?site_id={site['id']}&material_id={material['id']}").json()["items"][0]
    assert balance["reorder_status"] == "Below reorder point"
    assert balance["reorder_alert"] is True
    assert balance["recorded_stock_value_inr"] == 6
    dashboard = api_client.get(f"/api/dashboard?site_id={site['id']}&material_id={material['id']}")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["summary"]["reorder_alerts"] == 1
    assert dashboard.json()["summary"]["recorded_stock_value_inr"] == 6
    assert dashboard.json()["summary"]["all_pairs_low_stock"] == 1
    assert dashboard.json()["summary"]["all_pairs_out_of_stock"] == 0
    assert dashboard.json()["top_materials"] == []
    invalid = api_client.put(f"/api/reorder-rules/{site['id']}/{material['id']}", json={
        "site_id": site["id"], "material_id": material["id"], "unit": "kg", "reorder_point_qty": 4,
    })
    assert invalid.status_code == 422


def test_csv_validation_import_retains_rejections_and_never_creates_transactions(api_client):
    columns = ["date", "project_site_id", "city", "state", "project_type", "project_phase", "material", "unit", "consumption_qty", "opening_stock_qty", "incoming_qty", "unit_price_inr", "supplier_lead_time_days", "wpi_reference_month"]
    rows = [
        ["2025-01-01", "CSV Yard", "Moradabad", "Uttar Pradesh", "Residential", "Foundation", "CSV Cement", "bags", "5", "20", "2", "8", "4", "2025-01"],
        ["not-a-date", "CSV Yard", "Moradabad", "Uttar Pradesh", "Residential", "Foundation", "CSV Cement", "bags", "-1", "20", "0", "8", "4", "2025-01"],
    ]
    import io
    raw = io.StringIO()
    pd.DataFrame(rows, columns=columns).to_csv(raw, index=False)
    content = raw.getvalue().encode()
    validation = api_client.post("/api/data/validate", files={"file": ("sample.csv", content, "text/csv")})
    assert validation.status_code == 200, validation.text
    payload = validation.json()
    assert payload["accepted_rows"] == 1
    assert payload["rejected_rows"] == 1
    assert payload["creates_operational_transactions"] is False
    imported = api_client.post("/api/data/import", files={"file": ("sample.csv", content, "text/csv")}, data={"confirm": "true"})
    assert imported.status_code == 201, imported.text
    assert imported.json()["accepted_rows"] == 1 and imported.json()["rejected_rows"] == 1
    assert api_client.get("/api/inventory/transactions").json()["total"] == 0
    quality = api_client.get("/api/data/quality").json()
    assert quality["report"]["row_count"] == 1
    audit = api_client.get("/api/data/imports").json()
    assert len(audit["rejected_rows"]) == 1
    assert "not-a-date" in audit["rejected_rows"][0]["raw_json"]
    repeated = api_client.post("/api/data/import", files={"file": ("sample.csv", content, "text/csv")}, data={"confirm": "true"})
    assert repeated.status_code == 201
    assert repeated.json()["duplicate_file"] is True
    assert repeated.json()["accepted_rows"] == 1
    assert api_client.get("/api/inventory/transactions").json()["total"] == 0


def test_forecast_source_minimum_is_explicit_and_sources_never_mix(api_client, fresh_db):
    site, material = _create_pair(api_client, site="Forecast Yard", material="Forecast Cement", unit="bags")
    status = api_client.get(f"/api/forecast-sources?site_id={site['id']}&material_id={material['id']}&frequency=weekly")
    assert status.status_code == 200
    assert status.json()["source_label_if_auto"] == "Construction Materials Dehradun Dataset"
    assert status.json()["minimum_operational_sales_periods"] == MIN_OPERATIONAL_SALES_PERIODS["weekly"] == 26

    first_day = local_today() - timedelta(days=25 * 7)
    _opening(api_client, site, material, quantity=100, unit_cost=None, key="forecast-opening", day=first_day)
    for index in range(26):
        sale_day = first_day + timedelta(days=7 * index)
        result = api_client.post("/api/sales", json={
            "idempotency_key": f"weekly-sale-{index:02d}",
            "site_id": site["id"], "material_id": material["id"], "quantity": 1,
            "unit": material["unit"], "unit_sale_price_inr": 10,
            "sale_date": sale_day.isoformat(),
        })
        assert result.status_code == 201, result.text

    ready = api_client.get(f"/api/forecast-sources?site_id={site['id']}&material_id={material['id']}&frequency=weekly")
    assert ready.json()["observed_operational_sales_periods"] >= 26
    assert ready.json()["operational_sales_eligible"] is True
    assert ready.json()["source_label_if_auto"] == "Operational sales"
    monthly = api_client.get(f"/api/forecast-sources?site_id={site['id']}&material_id={material['id']}&frequency=monthly")
    assert monthly.json()["source_label_if_auto"] == "Construction Materials Dehradun Dataset"

    # Clearly labelled sample-ledger sales remain reportable but are not promoted
    # into the operational-sales training source.
    with fresh_db.session() as session:
        session.execute(update(SalesRecord).values(source_tag="sample_ledger"))
        session.commit()
    excluded = api_client.get(f"/api/forecast-sources?site_id={site['id']}&material_id={material['id']}&frequency=weekly")
    assert excluded.status_code == 200
    assert excluded.json()["observed_operational_sales_periods"] == 0
    assert excluded.json()["operational_sales_eligible"] is False
    assert excluded.json()["source_label_if_auto"] == "Construction Materials Dehradun Dataset"
