from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


def test_static_six_page_application_and_primary_http_views(fresh_db):
    app = create_app(database_url=fresh_db.url, auto_import_source=False)
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        for page in ("dashboard", "inventory", "sales", "forecasting", "replenishment", "reports"):
            assert f'data-page="{page}"' in root.text
        assert "/vendor/plotly.min.js" in root.text
        assert "https://" not in root.text
        for asset in ("/styles.css", "/app.js", "/vendor/plotly.min.js"):
            assert client.get(asset).status_code == 200

        created_site = client.post("/api/sites", json={
            "identifier": "Smoke Site", "name": "Smoke Site", "city": "Moradabad", "state": "Uttar Pradesh",
        }).json()["item"]
        created_material = client.post("/api/materials", json={"name": "Smoke Material", "unit": "pieces"}).json()["item"]
        ids = f"site_id={created_site['id']}&material_id={created_material['id']}"
        uninitialized = client.get(f"/api/inventory/balances?{ids}")
        assert uninitialized.status_code == 200, uninitialized.text
        assert uninitialized.json()["items"][0]["current_usable_stock"] is None
        assert uninitialized.json()["items"][0]["recorded_stock_value_inr"] is None
        checks = [
            "/api/health",
            "/api/catalog",
            f"/api/dashboard?{ids}",
            "/api/inventory/balances",
            "/api/inventory/transactions",
            "/api/sales",
            f"/api/forecast-sources?{ids}&frequency=weekly",
            "/api/reorder-rules",
            "/api/data/quality",
            "/api/data/imports",
            "/api/forecasts/metadata",
            "/api/forecasts/leaderboard",
            "/api/reports/current-inventory.csv",
            "/api/reports/ledger.csv",
            "/api/reports/sales.csv",
            "/api/reports/historical.csv",
            "/api/reports/quality.csv",
            "/api/reports/workbook.xlsx",
        ]
        for path in checks:
            response = client.get(path)
            assert response.status_code == 200, f"{path}: {response.text[:500]}"
