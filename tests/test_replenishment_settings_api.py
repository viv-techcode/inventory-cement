from fastapi.testclient import TestClient

from api.main import create_app
from inventory_app.catalog import create_material, create_site


def _pair(db):
    with db.session() as session:
        site = create_site(session, identifier="Settings Yard", name="Settings Yard", city="Dehradun", state="Uttarakhand")
        material = create_material(session, name="Settings Cement", unit="bags", default_lead_time_days=8)
        session.commit()
        return site.id, material.id


def test_reorder_settings_api_saves_and_returns_material_planning_values(fresh_db):
    site_id, material_id = _pair(fresh_db)
    app = create_app(database_url=fresh_db.url, auto_import_source=False)
    body = {
        "site_id": site_id, "material_id": material_id, "unit": "bags",
        "reorder_point_qty": 24, "lead_time_days": 8, "safety_stock_days": 11,
        "minimum_order_qty": 20, "order_multiple": 5, "maximum_stock_qty": 100,
    }
    with TestClient(app) as client:
        saved = client.put(f"/api/reorder-rules/{site_id}/{material_id}", json=body)
        assert saved.status_code == 200, saved.text
        item = saved.json()["item"]
        assert item["safety_stock_days"] == 11
        assert float(item["minimum_order_qty"]) == 20
        assert float(item["order_multiple"]) == 5
        listed = client.get(f"/api/reorder-rules?site_id={site_id}&material_id={material_id}")
        assert listed.status_code == 200, listed.text
        assert listed.json()["items"][0]["safety_stock_days"] == 11


def test_reorder_settings_api_rejects_unit_mismatch_and_out_of_range_days(fresh_db):
    site_id, material_id = _pair(fresh_db)
    app = create_app(database_url=fresh_db.url, auto_import_source=False)
    body = {
        "site_id": site_id, "material_id": material_id, "unit": "kg",
        "reorder_point_qty": 24, "safety_stock_days": 11,
        "minimum_order_qty": 20, "order_multiple": 5,
    }
    with TestClient(app) as client:
        mismatch = client.put(f"/api/reorder-rules/{site_id}/{material_id}", json=body)
        assert mismatch.status_code == 422
        assert "Unit mismatch" in mismatch.json()["error"]["message"]
        body["unit"] = "bags"
        body["safety_stock_days"] = 91
        invalid_days = client.put(f"/api/reorder-rules/{site_id}/{material_id}", json=body)
        assert invalid_days.status_code == 422
