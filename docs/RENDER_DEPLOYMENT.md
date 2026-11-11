# Render Deployment

## Blueprint settings

`render.yaml` defines one Python web service on the free plan:

- Python version: 3.11.11 through `PYTHON_VERSION`.
- Build: `pip install -r requirements.txt`.
- Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.
- Health check: `/api/health`.
- `AS_OF_DATE=2026-07-02`.
- `INVENTORY_DB_URL=sqlite:///data/inventory.db`.

At startup, an empty database is created from the committed ledger and deterministic loading code. Existing populated databases are left intact. The SQLite database file is excluded from Git. Forecast requests use source-hash-checked metrics and aligned predictions in `docs/model_metrics.json`; startup does not train models or require fitted model binaries.

## Free plan behavior

Render free web services sleep after 15 minutes without inbound traffic and typically take about a minute to start again. Their filesystem is ephemeral: local changes, including SQLite writes, are lost on spin-down, restart, or deployment. Free web services cannot attach persistent disks. The committed ledger remains available to rebuild baseline records at startup; records entered through the interface reset with the ephemeral database.

## Optional persistent storage

Persistent disks require an eligible paid service plan. In `render.yaml`, change `plan: free` to `plan: starter` or another disk-eligible plan, uncomment the `disk` block, and set `INVENTORY_DB_URL` to `sqlite:////var/data/inventory.db`. Create/sync the Blueprint, confirm the mount path is `/var/data` in the Render dashboard, and verify `/api/health` before accepting writes.

## Dashboard setup

1. Create a new Blueprint from the repository.
2. Confirm the service name, linked repository, and `master` branch.
3. Review the plan and environment variables from `render.yaml`.
4. Deploy and wait for `/api/health` to pass.
5. Open the service URL and visit Dashboard, Inventory, Sales, Forecasting, Replenishment, Purchasing, and Data & Reports.
6. If network access to the deployed service is unavailable, run `python scripts/smoke_test.py https://YOUR-SERVICE.onrender.com` from a reachable machine and retain the output.

`/api/health` returns database connectivity, ledger-file presence, ledger row count, and the number of loaded baseline events. `scripts/smoke_test.py` checks this endpoint and each page API using the supplied base URL.
