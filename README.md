# SiteStock — Construction Materials Operations

SiteStock is an offline-first construction-material operations workspace. FastAPI/uvicorn serves a static HTML/CSS/vanilla-JavaScript interface with six pages: Dashboard, Inventory, Sales, Forecasting, Replenishment, and Data & Reports. The existing `inventory_app/` services, SQLite database, original CSV, and forecasting implementation are retained.

rows after 2025-12-29 and all operational records are sample data

Historical observations remain separate from the live operational ledger. CSV stock fields never initialize current inventory; source prices are not operational acquisition costs. FIFO costing uses recorded transaction costs only, and unknown costs/margins remain unavailable.

## Start

From the repository root, with Python 3.11 or newer:

```bash
python -m pip install -r requirements.txt -r requirements-optional-ml.txt
python -m scripts.extend_dataset
python -m scripts.load_operations
python -m scripts.train_all_models
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Open **http://127.0.0.1:8000/** locally. The server initializes the retained database additively and imports the bundled CSV only if its file hash is not already present. The extension and operations commands are deterministic and idempotent. Use `python -m scripts.extend_dataset --as-of-date YYYY-MM-DD` for a reproducible weekly cutoff, or `--skip-database` to generate only the separate CSV. `scripts.load_operations` verifies that the extension is imported before posting its reconciled ledger.

There is no npm install, frontend build, CDN, remote font, or runtime network dependency. Plotly.js is bundled locally; the browser uses same-origin relative API paths.

## Data and provenance

The original file `data/Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv` remains byte-identical and keeps its 14-column schema. It contains 6,300 observations for six sites, ten materials, and 60 site/material series from 2024-01-01 through 2025-12-29. Its SHA-256 is `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`.

`data/Dehradun_Inventory_Dataset_Sample_Extension.csv` is a distinct file with 2,640 deterministic weekly observations, 44 per series, from 2026-01-05 through 2026-11-02. Its rows are tagged `sample_extension`; original rows are tagged `historical_csv`. The resulting observation table has 8,940 rows, 149 weekly observations per pair. The extension generator validates continuity and nonnegative stock flows, bounds price movement to ±15% of the recent pair-level anchor, and never edits the original CSV.

The operations loader adds 60 opening counts, 630 receipts, 2,640 sales with linked consumption movements, 30 generic Indian contractor/builder/retailer customer names (without contact details), and 60 active reorder rules. Each weekly close is reconciled to the extension. These operational rows are tagged `sample_ledger`. Opening and receipt costs are deterministic synthetic values 82–93% of the corresponding week's unit price, making FIFO stock value, COGS and margin available. Sample sales remain reportable but are excluded from operational-sales forecast eligibility.

Schema version 3 stores row-level `source_tag` values on observations, inventory transactions, customers, sales, and reorder rules. Migrations are additive and idempotent. The retained database preserves its prior records and artifacts.

## Six pages

- **Dashboard** — date/site/material scope; operational ledger balances, recorded-cost stock valuation, sales/revenue and reorder alerts, with historical demand kept separate.
- **Inventory** — opening counts, receipts, consumption and signed reason-required adjustments; current balances, FIFO valuation, filters and site/material administration.
- **Sales** — optional customer directory, quantity/date/unit sale price, stock deduction, revenue, and margin only when the complete sold quantity has a recorded FIFO cost basis.
- **Forecasting** — Naive, eligible Seasonal Naive, Multiple Linear Regression, Random Forest and optional XGBoost, with chronological holdout metrics, charts and saved assessments.
- **Replenishment** — live ledger balance, per-pair reorder rules and alerts, source freshness, 90-day weekly horizon guard, and transparent lead-time/safety-stock math. User-confirmed incoming quantity is a scenario only.
- **Data & Reports** — source quality, CSV validation/explicit historical import, rejected-row audit, and distinct CSV/XLSX operational and observation exports.

Purchase-order, supplier, approval, and delivery workflows are not exposed in the new API/frontend. Compatible legacy schema and services are retained.

## Inventory and financial rules

```text
Closing stock = opening physical count + receipts − consumption ± signed adjustments
```

- Receipts, consumption, and adjustments require an existing physical opening count; a second opening balance is rejected.
- Units must match the catalogue. Negative balances, future-dated movements, duplicate idempotency keys, and adjustments without a signed quantity and reason are rejected.
- Opening counts and receipts may have an operator-recorded unit cost. FIFO valuation uses recorded costs only; no historical or catalogue price is used as acquisition cost. The deterministic sample ledger records each opening/receipt layer at 82–93% of that week's sample unit price; these are explicitly synthetic costs.
- If any remaining stock lacks recorded cost, total stock value is unavailable. Sale margin is unavailable when any part of that sale cannot be costed from recorded inventory.
- Revenue remains reportable even when COGS/margin is unknown. Sample sales are tagged and are not treated as genuine operational-sales forecast history.
- Reorder rules are scoped to one site/material pair. Replenishment uses the live ledger balance by default; uninitialized stock remains unknown.

## Forecast sources and methodology

The API supports `auto`, `historical_csv`, and `operational_sales`. Forecast inputs never mix sources. Auto may select operator-originated operational sales only after at least 26 observed weekly or 18 observed monthly periods for that site/material; `sample_ledger` sales are excluded from those counts. The current 44-week sample ledger therefore does not qualify as an actual operational-sales source. Otherwise Auto uses the observation table (`Historical CSV` source label), including its distinct row tags.

- Weekly/monthly aggregation does not zero-fill missing periods or invent daily demand.
- Chronological fixed-origin holdout; future test values are not fed back into subsequent predictions.
- Past-only lag 1–4 and trailing-four-period features; MAE, RMSE, R² when defined, and zero-safe WAPE.
- The Asia/Kolkata seven-day freshness gate and 90-day weekly horizon guard remain active for current replenishment. Missing physical stock, unsupported lead time, and unavailable daily rate still withhold numeric recommendations.

## Extended-series model run

Five models were trained for all 60 extended weekly series: 300 new artifacts, no series-level issues, completed in 129.63 seconds. The original 300 artifacts remain; the database now contains 600 in total across the original and extended data hashes. The 119-observation training window and 30-observation chronological holdout end on 2026-11-02. The holdout includes generated extension rows, so these are diagnostics of the generated series and not measured accuracy on actual future demand. Forecasting puts WAPE first as the headline error and explains R² against the holdout-average baseline.

| Model | Best-model wins / 60 | Median WAPE | Median R² |
|---|---:|---:|---:|
| Naive | 21 | 29.83% | −2.014 |
| Random Forest | 20 | 25.90% | −1.566 |
| XGBoost | 17 | 29.11% | −1.944 |
| Seasonal Naive | 1 | 49.20% | −11.793 |
| Multiple Linear Regression | 1 | 76.00% | −19.586 |

Negative median R² across every model reinforces that these retrospective per-pair metrics are not a global accuracy claim. See [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md).

## API and project layout

All API errors use a consistent JSON envelope. Main routes include catalog/sites/materials/customers, inventory transactions/balances, reorder rules, sales, forecast sources/evaluations/metadata, replenishment, data quality/imports/validation, and CSV/XLSX reports. The full route list is available in `api/`.

```text
api/                         FastAPI app, request schemas, routers and error envelope
frontend/                    Static interface, CSS, vanilla JS and local Plotly.js
inventory_app/               Retained services, DB models/migrations, forecasting and reports
scripts/                      Dataset extension, operations loader and model training
data/                         Original CSV, separate extension CSV and retained SQLite DB
tests/                         Core, API, migration, import, forecast and sample-pipeline tests
docs/                          Data profile, plan, model results, progress and QA notes
```

## Verification

Run from the project root:

```bash
python -m compileall -q inventory_app api tests scripts
node --check frontend/app.js
python -m pytest -q
```

The current focused checks pass the sample data pipeline and inventory tests. The sample-pipeline test covers deterministic generation, source tags, ledger reconciliation, deterministic unit costs and repeat-load idempotency. The full suite was stopped before completion during this fast pass. Isolated browser checks covered real receipt, sale and adjustment submissions on a database copy, with dashboard totals verified after the sale. See [`TEST_RESULTS.md`](TEST_RESULTS.md) and [`docs/BROWSER_QA.md`](docs/BROWSER_QA.md).
