# SiteStock — Construction Materials Inventory

SiteStock is a local FastAPI application with an HTML/CSS/JavaScript interface for construction-material inventory, sales, forecasts, replenishment, purchasing, and data-quality review. Dataset construction and its limitations are documented in the data card.

## Run on Windows

Requires Python 3.11 or newer.

1. Run: py -3.11 -m venv .venv
2. Activate: .venv\Scripts\Activate.ps1
3. Install: python -m pip install -r requirements.txt
4. Rebuild and validate the bundled dataset: python -m scripts.build_dataset
5. Initialize the database and import the historical source: python -m scripts.init_database
6. Train and save model comparisons offline: python -m scripts.train_all
7. Run the holdout policy comparison: python -m scripts.simulate_inventory_policies
8. Start the app: uvicorn api.main:app --host 127.0.0.1 --port 8000
9. Open http://127.0.0.1:8000/

Startup creates the configured SQLite database and imports the bundled CSV once by file hash. Set INVENTORY_DB_URL to use another database path. For an existing database, take a SQLite backup before changing environment or schema settings.

XGBoost is optional; install the pinned optional requirements in requirements-optional-ml.txt to enable it. Plotly.js is bundled locally, and the app has no CDN or remote font dependency.

Database initialization and CSV loading are idempotent. `scripts.train_all` runs model fitting offline; API requests use saved assessments or a lightweight Naive fallback, so a cold cache does not trigger the full model suite. Before repricing an existing copy, use the dated instructions in `docs/PRICE_SOURCES.md` and take a SQLite backup. The rebase tool updates historical prices only and validates stock-flow fields before writing.

## Dataset
- File: data/construction_materials_dehradun_dataset.csv
- 8,940 rows, 60 site/material series, 149 weekly observations each
- Calendar coverage: 2024-01-01 through 2026-11-02
- 16 identifier, measurement, and derived-level columns; see docs/DATASET_CARD.md and docs/DATASET_AUDIT.md.

## Main areas
- Dashboard: current operational stock, alerts, and historical summaries
- Inventory and sales: ledger transactions, customers, recorded costs, and revenue
- Forecasting: Naive and Seasonal Naive baselines, regression and tree models, with chronological evaluation
- Replenishment: shared risk logic, service-level safety stock, and pack-rounded suggestions
- Purchasing: supplier records, purchase orders, and receipts
- Data and reports: CSV validation/import, quality summaries, and exports

## Useful commands
- python -m scripts.build_dataset
- python -m scripts.init_database
- python -m scripts.train_all
- python -m scripts.train_all --metrics-only
- python -m scripts.simulate_inventory_policies
- python -m scripts.make_submission
- python -m scripts.run_with_timeout --timeout 170 -- python -m pytest -q
- node --check frontend/app.js

Application settings are read from environment variables; .env.example documents supported configuration. Database initialization and CSV loading are idempotent.
