# Academic Project Summary

## Title

**Construction Materials Inventory Operations and Demand Forecasting with an Offline-First Web Interface**

## Summary

SiteStock is a FastAPI/uvicorn application with a static HTML/CSS/vanilla-JavaScript client. Its six pages cover Dashboard, Inventory, Sales, Forecasting, Replenishment, and Data & Reports. The existing SQLite database, original CSV, core services, and forecasting implementation are retained; schema changes are additive.

The data model keeps distinct provenance for original observations, a separate generated observation extension, and operational ledger records. The extension and operational sample records are tagged and minimally disclosed in the application as requested. They are not presented as source-backed business events.

## Data profile and extension

The original `data/Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv` remains byte-identical (SHA-256 `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`). It contains 6,300 rows × 14 columns, six sites, ten materials and 60 pairs, dated 2024-01-01 through 2025-12-29.

A separate deterministic extension adds 2,640 weekly observations, 44 per pair, dated 2026-01-05 through 2026-11-02. Original observations are tagged `historical_csv`; extension observations are tagged `sample_extension`. The database contains 8,940 observation rows (149 per series). The extension generator preserves weekly continuity, validates nonnegative stock flows, caps price drift, and leaves the original file unchanged.

The idempotent operations loader adds 60 opening counts, 630 receipts, 2,640 sales linked to 2,640 consumption movements, 30 generic customers and 60 reorder rules. All operational sample records carry `sample_ledger`; every weekly ledger close reconciles to the extension. No acquisition costs are invented. FIFO remains the costing method, while sample COGS and margins remain unknown. Sample-ledger sales are excluded from operational-sales forecast eligibility.

## Forecasting method and results

The forecasting service keeps one site/material/unit per series, calendar aggregation without zero-fill, a chronological fixed-origin holdout, past-only lags 1–4 and trailing-four-period features. Models are Naive, eligible Seasonal Naive, Multiple Linear Regression, Random Forest and optional XGBoost. Metrics are MAE, RMSE, R² when defined, and zero-safe WAPE.

The extended dataset was trained for all 60 weekly series: 300 new artifacts, no issues, in 78.30 seconds. Existing artifacts were preserved; total saved artifacts are 600. Each series used 119 earlier periods for training and 30 chronological holdout periods ending 2026-11-02. Because the holdout includes generated extension rows, the metrics below describe the generated sample series, not measured accuracy on actual post-cutoff demand.

| Model | Best-model wins / 60 | Median WAPE | Median R² |
|---|---:|---:|---:|
| Random Forest | 22 | 25.90% | −1.566 |
| Naive | 19 | 29.83% | −2.014 |
| XGBoost | 15 | 28.26% | −1.914 |
| Seasonal Naive | 3 | 49.20% | −11.793 |
| Multiple Linear Regression | 1 | 76.00% | −19.586 |

Median R² is negative for every model. These per-pair metrics are diagnostics only, not a pooled accuracy claim. Full detail is in [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md).

## Operational inventory and financial controls

```text
Closing stock = opening physical count + receipts − consumption ± signed adjustments
```

An opening physical count is required before later movements. Units must match the catalogue; negative balances, future dates, duplicate keys, and adjustments without a reason are rejected. FIFO uses only recorded operational costs. Historical and catalogue prices are never used as stock cost basis or sales COGS. Unknown cost means unknown total stock value and unavailable sale margin.

Replenishment compares rules to live ledger balances and retains the seven-day Asia/Kolkata source-freshness gate, 90-day weekly horizon guard, missing-count checks, lead-time checks and negative-stock protections. The user-confirmed incoming quantity is a scenario only, not a receipt or delivery.

## Database and implementation

Schema version 3 adds `source_tag` to historical observations, inventory transactions, customers, sales, and reorder rules, using additive idempotent migration behavior. Legacy observations default to `historical_csv`; legacy operations default to `operator`; generated and seeded records receive their distinct tags. The v2 nullable transaction-cost migration remains intact. See [`MIGRATION_002.md`](MIGRATION_002.md) and [`MIGRATION_003.md`](MIGRATION_003.md).

The static UI uses a local Plotly.js bundle; there is no React, frontend build, CDN or runtime external dependency. Reports expose separate observation and operational exports with provenance tags.

## Verification

- Automated checks: **43 passed**, with one non-failing Starlette/AnyIO deprecation warning; compileall and `node --check frontend/app.js` passed.
- The tests cover source integrity, additive migration, extension determinism, sample-ledger reconciliation/idempotency, exclusion of sample sales from operational forecast eligibility, freshness at the seven-day boundary, sales/FIFO behavior, imports, APIs and exports.
- Isolated Chromium verified all six pages, the single Data & Reports source line, fresh-source behavior, sample-sales eligibility exclusion, and tagged CSV/XLSX exports. Console/page errors and failed HTTP responses were zero.
- Browser form writes and calculation requests remained on a temporary database copy. QA-only data and the temporary database were removed. See `TEST_RESULTS.md` and [`docs/BROWSER_QA.md`](docs/BROWSER_QA.md).
