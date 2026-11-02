# Isolated Browser QA

Date: 2026-11-02 (Asia/Kolkata). Chromium/Playwright ran against Uvicorn on port 8001 with a temporary SQLite backup at `/tmp/sitestock-browser-check.db`. The retained database received no browser QA writes.

## Current sample-loaded application check

- All six pages rendered: Field overview, Inventory ledger, Sales & margin, Forecast workspace, Replenishment planner, and Data & reports.
- The requested `Data source` disclosure appeared exactly once on Data & Reports and did not appear on the other five pages.
- The quality endpoint reported latest observation 2026-11-02 (age 0); no stale-freshness warning was returned. The Replenishment calculation returned **Covered** with current source freshness, no stale-source banner, and no numeric guard failure.
- Sample sales were excluded from real operational forecast eligibility: `observed_operational_sales_periods=0`; Auto resolved to the observation-table source (`Historical CSV` / UI label `Dataset`).
- Operational ledger, sales, historical-observation CSVs downloaded and contained `source_tag` values (`sample_ledger` or `sample_extension` as appropriate). The XLSX opened successfully with eight sheets: Current inventory, Operational ledger, Operational sales, Historical CSV, Forecast metadata, Import history, Rejected rows, and Data quality.
- Browser console errors: 0; uncaught page errors: 0; HTTP responses ≥400: 0.

The Forecasting page reused a saved assessment, and the isolated browser check issued one Replenishment calculation. No inventory, sale, customer, reorder-rule, or import form was submitted. All browser-side requests used only the temporary DB copy; the copy and downloaded files were removed after QA.

## Current real-form check

On 2026-11-02, a SQLite backup of the retained database was served locally on port 8000. Through the browser UI, a receipt (5 AAC Blocks at ₹55), a sale (1 AAC Block at ₹80 to Rawat Constructions), and a signed −1 piece adjustment were each submitted and confirmed by the app's success toast. The Dashboard selection was Clement Town / AAC Blocks for 2026-11-01–2026-11-02: before the sale it showed 1 sale, ₹34,753 revenue and ₹5,068.62 gross margin; after it showed 2 sales, ₹34,833 revenue and ₹5,080.67 gross margin. QA writes remained in `data/browser_qa_copy.db`; the retained database was not changed by browser forms. The local preview server remains running against that copy.

The reorder snapshot on the retained database is 52 at/above reorder, 8 below reorder, and 0 at/under zero stock. The two lowest weeks-of-cover are about 2.17 and 2.26, so they are low-cover alerts rather than physical near-stock-outs.

## Earlier isolated form-flow verification

The saved screenshots `screenshots/isolated-{dashboard,inventory,sales,forecasting,replenishment,reports}.png` document the earlier full interaction pass on a separate temporary DB. It exercised inventory receipts/adjustments, site/material controls, a QA-only customer and cost-backed sale, forecast model overlay, reorder-rule save, stale-source blocking, duplicate historical import, CSV/XLSX downloads, and error handling. QA-only records remained isolated and were removed. Those older screenshots are not a representation of the current retained ledger.
