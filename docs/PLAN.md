# Project Plan

## Audit

- The repository is an existing FastAPI, SQLAlchemy, SQLite, and static frontend application. Existing modules cover catalog, sales, stock, forecasting, replenishment, purchasing, and reports.
- The active CSV is `data/construction_materials_ledger.csv`: 8,940 rows, 60 site/material series, ten materials, weekly dates from 2024-01-01 through 2026-11-02, and 16 columns. This differs from the required ledger schema, count, and dates.
- Legacy inputs and dated repository copies have been moved under `_private_archive/`. The active dataset is the single fixed ledger at `data/construction_materials_ledger.csv`.
- The repository includes scripts for database initialization, operations loading, dataset repricing, and model training. `api/main.py` imports the configured CSV on startup and optionally seeds operations. Inventory and purchasing routes exist; the requested company-wide ledger architecture is not present.
- Forecasting includes pooled and per-series implementations, saved artifacts, and chronological evaluation. A full leakage and holdout audit remains pending.
- The frontend has the seven requested navigation sections and working API calls, but page-by-page reconciliation remains pending.
- Requirements are pinned, but the deployment documentation currently requires a persistent disk and uses a seed environment flag. No `render.yaml` is present.
- The supplied original proposal was not found in tracked project files; use the feature scope in the project request.
- Git is on `master`, aligned with `origin/master` at audit time. Five pre-existing modified files are `api/routes_dashboard.py`, `docs/RENDER_DEPLOYMENT.md`, `frontend/app.js`, `frontend/index.html`, and `scripts/load_operations.py`. Preserve and review these changes; do not overwrite them blindly.
- The project instructions name five files as unpushed, consistent with the five modified files. Git history and source inspection are the available local evidence; remote state requires a later GitHub check.
- No `TODO.md`, `docs/DECISIONS.md`, or `docs/VERIFICATION_LOG.md` existed at audit time. `docs/PLAN.md` existed but was ignored by `.gitignore`.
- The current dataset card and deployment guide contain content that conflicts with the required neutral wording. The code, tests, and docs contain several prohibited disclosure terms; the content audit remains open.
- No Render live URL or credentials were found in the checked project configuration. The API has `/api/health`, but current health checks report the old CSV row count.

## Architecture

Keep the existing FastAPI and static frontend. Make `data/construction_materials_ledger.csv` the single committed source of baseline operational events. Derive weekly demand, balances, margins, reports, and forecast inputs from it. Keep app-entered records in SQLite and clearly separate them from the loaded baseline. Startup must rebuild an empty database idempotently from the ledger and deterministic operations setup. Render serves one Python web service.

## Data design

The target ledger has 8,490 dated events, 11 required columns, continuous event identifiers, six named Dehradun sites, and the 2024-04-01 to 2026-07-02 coverage. Use INR ex-GST prices consistently and include units on every quantity. For cement, apply 28% through 2025-09-21 and the revised 18% rate from 2025-09-22; verify every other SKU classification before generation. CPWD May 2025 cement and TMT references are ex-GST and regionally limited to Delhi/NCR, while Dehradun item rates consulted for material units are indicative published data with the page dated August 2026, after the target data cutoff. Do not treat those later market rates as historical transaction prices. Operations tables and reference records are derived in code from the ledger; no additional active data file is allowed. Archive prior CSV inputs without deleting them and ensure runtime code never reads the archive.

## Demand story

Use the working identity Doon Ridge Materials. Target annual sales turnover is INR 6 crore, with ex-GST gross revenue aligned to the ledger. Monthly sales should show the requested construction cycle: pre-monsoon strength, monsoon softness, festive recovery with a short Diwali dip, winter slowdown, a March year-end push, a 2025 monsoon decline, and recovery through the 2026 pre-monsoon period. Stock movements must reconcile at event level and stay nonnegative. Company turnover and material/category margins must be calculated from the ledger and documented after generation.

## Forecasting design

Forecast weekly quantity. Forecast at material level and allocate predictions to sites by trailing observed sales share; reconcile site predictions back to material totals. Use a chronological 13-16 week holdout and expanding-window validation. Compare naive or seasonal-naive, Ridge regression, and a tree model using past-only features. Select by validation scores; report MAE, RMSE, WAPE, and MASE, residual checks, aligned holdout values, future intervals from validation residuals, and tree feature importance. Save metrics and predictions as committed text data, and pin any model library used for persisted artifacts.

## Deployment design

Add a Render Blueprint with one Python service, a fully pinned Python version, pinned dependencies, `$PORT` binding, `/api/health`, and relative database defaults. Use the free plan by default. Document persistent-disk configuration separately, and ensure an empty database is rebuilt quickly and safely at startup. Do not commit a SQLite database. Provide a URL-driven smoke script and deployment steps if the hosted service cannot be reached.

## Risks

- The old event-level operational model and new single-ledger model may require route and schema redesign.
- The current frontend and working-tree modifications may contain useful work; inspect before replacing.
- Current local price sources include indicative published prices and are not a complete historical dealer series. Keep ex-GST units explicit and record consulted dates.
- Converting date range, materials, and units can break existing forecasts, tests, and report contracts.
- Repository-wide wording cleanup must avoid `_private_archive/` while ensuring runtime has no archive dependency.
- A GitHub push and Render dashboard verification depend on remote availability and account access.

## Roadmap

1. Audit repository, git state, routes, models, frontend, scripts, tests, configuration, docs, and proposal availability. Done when this baseline is recorded.
2. Research price, tax, seasonality, forecasting, inventory policy, and Render deployment sources. Depends on task 1.
3. Define the new ledger and deterministic master/operations design; record decisions and final acceptance checks. Depends on task 2.
4. Build the reproducible ledger and archive other active CSV inputs. Depends on task 3.
5. Reconcile/load the database and update APIs, forecasting, and frontend to the ledger. Depends on task 4.
6. Add reports, reset, training, smoke, Render files, and short supporting documents. Depends on task 5.
7. Run the final audit, inspect every page, fix issues, and repeat. Depends on task 6.
8. Commit completed milestones and push to `master`; verify remote state and Render where accessible. Depends on task 7.

## Acceptance Checklist

- [x] Ledger built at `data/construction_materials_ledger.csv` with 8,490 events, required dates/sites/columns, unique ordered IDs, valid units, and nonnegative running stock.
- [ ] All other CSV data is preserved in `_private_archive/legacy_inputs/` and disconnected; startup works without the archive.
- [ ] Database rebuild is idempotent; entry count, operations, sales, purchase receipts, and balances reconcile to the ledger.
- [ ] Dashboard, Inventory, Sales & Margin, Forecasting, Replenishment, Purchasing, and Data & Reports are populated and their totals agree.
- [ ] Sales, purchase-order lifecycle, and planner actions update the expected records; reset restores the baseline.
- [ ] Seasonal revenue phases, annual turnover, and category gross margins meet the specified ranges.
- [ ] Forecast split, validation, metrics, residuals, future intervals, and actual-sales alignment are verified.
- [ ] Content audit finds none of the prohibited terms in active files, database content, or API JSON; no authorship claim is present.
- [ ] App runs without archive access and supports Windows and Render Linux.
- [ ] Render Blueprint and deployment guide agree; smoke check, test suite, and frontend checks pass.
- [ ] Every TODO has evidence; required project documents are present; remote and Render checks are recorded or their access limitations are documented.

