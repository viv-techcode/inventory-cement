# Execution Plan

- Preserve the original 14-column CSV byte-for-byte; generate a separate deterministic weekly extension through the current Monday.
- Tag bundled observations `historical_csv`, extension rows `sample_extension`, and every seeded operational record `sample_ledger` through additive columns.
- Keep generated quantities continuous and nonnegative, prices within ±15% of the last-13-row anchor, and generation/idempotent imports deterministic.
- Seed one extension-aligned opening count per site/material, receipts and sales; verify every weekly close reconciles to the extension.
- Use 30 generic Indian business customers with blank contact details and active reorder rules for all 60 pairs; cost opening and receipt layers deterministically for FIFO valuation.
- Exclude `sample_ledger` sales from operational-sales forecast eligibility and keep model sources separate.
- Use only the exact README disclosure line and one `Data source` line on Data & Reports; no sample banners/badges/warnings elsewhere.
- Apply seven-day freshness logic in Asia/Kolkata; retain stock, lead-time, horizon and negative-stock guards.
- Retrain each weekly series with chronological holdout and past-only features; verify migrations, tests, exports, six-page browser behavior and preview server.
