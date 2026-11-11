# Verification Log

- 2026-11-11 — Phase 0 audit: `git status --short --branch`; output showed `master...origin/master` with five modified paths (`api/routes_dashboard.py`, `docs/RENDER_DEPLOYMENT.md`, `frontend/app.js`, `frontend/index.html`, `scripts/load_operations.py`).
- 2026-11-11 — Phase 0 data inspection: Python CSV read; output `rows 8940`, date range `2024-01-01` through `2026-11-02`, `149` unique weekly dates, six sites, ten materials, and 16 columns.
- 2026-11-11 — Phase 0 file inspection: repository listing confirmed no `render.yaml`, `TODO.md`, `docs/DECISIONS.md`, or `docs/VERIFICATION_LOG.md`; existing `docs/PLAN.md` was excluded by `.gitignore`.
- 2026-11-11 — Phase 0 route inspection: `rg -n "include_router|@router\\.(get|post|put|delete)" api` found existing endpoints for dashboard, catalog, inventory, sales, forecasts, replenishment, purchasing, data, and reports.
- 2026-11-11 — Phase 0 research: Render, CBIC, Dehradun rates, and intermittent-demand methods were searched. Price-history and seasonal claims need better dated sources before encoding values.
- 2026-11-11 — Phase 1 source research: official CBIC/GST Council, Render, MoEFCC, IMD, CPWD, and relevant market rate pages consulted; recorded URLs in `docs/DECISIONS.md` and prices in `docs/PRICE_REFERENCES.md`.
- 2026-11-11 — Phase 1 methods/platform: confirmed cement rate effective date in Gazette Notification No. 9/2025; recorded safety-stock, weighted-average costing, ABC, and intermittent-metric sources in `docs/DECISIONS.md`.
- 2026-11-11 — Phase 2 design recorded: reviewed `docs/PLAN.md` and `docs/DECISIONS.md` for 15 SKU units, INR 6 crore annual ex-GST turnover, six sites, event ledger and top-down material forecast allocation.
- 2026-11-11 — Ledger build: `python -m scripts.build_ledger`; output `rows=8490`, `sales=7932`, `receipts=440`, `adjustments=28`, coverage `2024-04-01` to `2026-07-02`, total sales INR `134999107.45`.
- 2026-11-11 — Ledger reproducibility: ran the builder twice; SHA-256 matched at `4E7F89F80CEDB6764FE630B2B947F9CD460086D0A7912B0A3CF9FFDAF88E516F`.
- 2026-11-11 — Ledger structure: Python CSV audit confirmed 8,490 rows, 11 columns, IDs `L000001`–`L008490`, 6 sites, 15 materials, and event counts `opening_balance=90`, `sale=7932`, `purchase_receipt=440`, `adjustment=28`.
- 2026-11-11 — Ledger financial profile: sales sum INR 134,998,970 after CSV rounding, equivalent to INR 5.99995 crore annualized over 27 months; monthly revenue ranges INR 2.4–66.4 lakh with visible monsoon and winter troughs and pre-monsoon/March peaks.
