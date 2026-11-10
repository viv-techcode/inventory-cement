from fastapi.testclient import TestClient

from api.main import create_app
from inventory_app.inventory import local_today


def test_supplier_recommendation_po_approval_and_receipt_api(seeded_db):
    db, _ = seeded_db
    with TestClient(create_app(database_url=db.engine.url.render_as_string(hide_password=False), auto_import_source=False)) as client:
        catalog = client.get("/api/catalog").json()
        site = next(x for x in catalog["sites"] if x["identifier"] == "Jakhan, Dehradun")
        material = next(x for x in catalog["materials"] if x["name"] == "Cement")
        supplier = client.post("/api/suppliers", json={"name": "API Test Vendor"})
        assert supplier.status_code == 201
        assert client.get("/api/suppliers").json()["items"][0]["name"] == "API Test Vendor"
        opening = client.post("/api/inventory/transactions", json={
            "idempotency_key": "api-po-opening", "site_id": site["id"], "material_id": material["id"],
            "transaction_type": "opening_balance", "quantity": 10, "unit": material["unit"],
            "transaction_date": local_today().isoformat(),
        })
        assert opening.status_code == 201
        po = client.post("/api/purchase-orders/from-recommendation", json={
            "idempotency_key": "api-po-create", "supplier_id": supplier.json()["id"],
            "site_id": site["id"], "material_id": material["id"], "quantity": 5.00001,
            "unit": material["unit"], "unit_price_inr": 400,
        })
        assert po.status_code == 201
        assert float(po.json()["lines"][0]["quantity_ordered"]) == 5.0001
        line_id = po.json()["lines"][0]["id"]
        oid = po.json()["id"]
        assert client.patch(f"/api/purchase-orders/{oid}/status", json={"status": "Pending approval"}).status_code == 200
        assert client.patch(f"/api/purchase-orders/{oid}/status", json={"status": "Approved"}).json()["status"] == "Approved"
        receipt = client.post("/api/receipts", json={
            "idempotency_key": "api-grn-1", "receipt_reference": "API-GRN-1",
            "purchase_order_line_id": line_id, "quantity": 5.0001, "unit": material["unit"],
            "receipt_date": local_today().isoformat(),
        })
        assert receipt.status_code == 201
        assert client.get("/api/purchase-orders").json()["items"][0]["status"] == "Received"
        balances = client.get("/api/inventory/balances", params={"site_id": site["id"], "material_id": material["id"]}).json()
        assert float(balances["items"][0]["current_usable_stock"]) == 15.0001
