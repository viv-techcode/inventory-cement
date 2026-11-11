# Feature Checklist

## Application and stack

- [x] FastAPI/uvicorn API, Pydantic request validation, structured JSON errors and static asset serving.
- [x] Six static pages: Dashboard, Inventory, Sales, Forecasting, Replenishment, and Data & Reports.
- [x] HTML/CSS/vanilla JavaScript; no React, npm build, CDN, remote font or runtime external dependency.
- [x] Local Plotly.js bundle; same-origin relative API requests.
- [x] Existing database, original CSV, services, and previously saved forecast artifacts preserved.

## Source provenance and sample data

- [x] Original 14-column CSV remains byte-identical; SHA-256 and row integrity verified.
- [x] Deterministic separate extension through 2026-11-02: 2,640 rows, 44 weekly rows for each of 60 pairs.
- [x] Extension observations tagged `sample_extension`; original observations tagged `historical_csv`.
- [x] Idempotent `scripts.extend_dataset.py` CSV writer/import flow and `scripts.load_operations.py` sample ledger loader.
- [x] 60 opening counts, 630 receipts, 2,640 sales and linked consumption transactions, 30 generic customers, and 60 reorder rules; all operational additions tagged `sample_ledger`.
- [x] Weekly ledger balances reconcile to the extension; nonnegative stock is enforced and no acquisition cost is invented.
- [x] Sample-ledger sales excluded from real operational-sales forecast eligibility.
- [x] Exact requested README disclosure line and one Data & Reports `Data source` line; no sample banner/badge/warning elsewhere.

## Inventory, sales, and finance

- [x] Opening physical counts, receipts, consumption, and signed adjustments; a second opening count is rejected.
- [x] Unit mismatch, future date, negative stock, duplicate movement, and adjustment without reason are rejected.
- [x] FIFO valuation uses recorded costs only; sample COGS and margin stay unknown.
- [x] Sales, customer directory, revenue, COGS/margin reporting, filters and idempotency.
- [x] Per-site/material reorder rules, alerts, and transparent replenishment math based on live ledger stock.
- [x] Missing physical stock, source freshness, lead time, weekly horizon, and negative-stock guards retained.
- [x] CSV and XLSX exports keep observations and operations separate and include row-level source tags.

## Forecasting, migration, and QA

- [x] Naive, eligible Seasonal Naive, linear regression, random forest, optional XGBoost; chronological fixed-origin holdout and past-only features.
- [x] Five models retrained for all 60 extended weekly pairs: 300 new artifacts, 0 issues; previous 300 artifacts retained.
- [x] Operational-sales eligibility threshold is 26 observed weekly or 18 monthly periods; `sample_ledger` rows are excluded.
- [x] Schema v3 additive/idempotent source-tag columns; nullable costs remain unbackfilled.
- [x] Automated suite: 43 passed, one non-failing deprecation warning.
- [x] Isolated Chromium loaded all six pages and verified disclosure, freshness, eligibility, and tagged CSV/XLSX exports with zero console/page/HTTP errors.
