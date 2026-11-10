# Render Demo Deployment

SiteStock is a single FastAPI application that serves both the API and the HTML/CSS/JavaScript interface. Deploy it as one Render **Web Service**. Vercel would turn this server application into function-based routes and would not solve the database persistence problem.

## Render service settings

- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/health`
- Environment: `INVENTORY_DB_URL=sqlite:////var/data/inventory.db`
- Environment: `INVENTORY_SEED_SAMPLE_OPERATIONS=true`
- Persistent disk mount path: `/var/data`

Attach the persistent disk to the web service and keep one service instance. The database file must live under the disk mount. A SQLite file in the repository directory or `/tmp` can disappear when Render replaces the instance. A persistent disk is a Render paid feature; if the service must stay on a free ephemeral filesystem, treat it as a read-only demonstration because visitor changes can be lost at restart or redeploy.

The seed setting is optional and off by default. When enabled, app startup imports the canonical historical dataset and creates the sample operational ledger only if the database has no sample transactions. This produces opening stock, receipts, sales, 30 customers, and reorder rules for all 60 site/material pairs. Five generic demo suppliers are added if the supplier list is empty. The loader checks stock reconciliation and is safe to run again; existing sample operations are not rewritten. Forecast evaluation uses its lightweight Naive fallback if no compatible trained model artifacts are present, so first requests do not trigger long model training.

## After deployment

1. Open `/api/health` and confirm `status` is `ok`, `schema_current` and `required_tables_present` are true, and `dataset_row_count_matches` is true.
2. Open `/` and try Dashboard, Inventory, Sales, Forecasting, Replenishment, Purchasing, and Data & Reports.
3. For a demo workflow, post an inventory receipt, record a sale, inspect replenishment, and confirm the new balance appears afterward.
4. Check the Render deploy logs if the service starts with no records or an API page reports an error. Recheck the service's Start command and that the disk is mounted at `/var/data`.

The sample customer names, ledger, prices, and demand series are synthetic teaching/demo records. Do not present them as real supplier transactions or physical stock counts. Use the sample-tag/source fields and disclose the synthetic data in a submitted demo.

## Database upgrade path

For this single-instance prototype, SQLite on a persistent disk is the smallest change because the app already uses SQLAlchemy and SQLite migrations. Use managed PostgreSQL when multiple app instances, concurrent users, or a real multi-user dataset become requirements. Before switching, validate the migration path against PostgreSQL; the existing production workflow is currently documented and verified for SQLite. Back up the database before each schema or deployment change.
