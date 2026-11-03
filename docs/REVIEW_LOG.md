# Review Log

## Decision record

### 2026-11-03 — Establish review workflow
- Options considered: (1) inspect everything before planning; (2) write the required dependency plan first, then inspect; (3) immediately start cleanup.
- Selected: option 2. Reason: the user requires the plan to be the first artifact, and the dataset affects the database, ML, API, and submission claims.
- Constraints adopted: no Git commands; no asking questions; preserve measurement values; back up before destructive changes; disclose only verified claims and list blocked commands for the user.

### 2026-11-03 — Initial scope scan
- Options considered: (1) enumerate every artifact including model caches; (2) enumerate source/docs/tests and separately inspect data/database/artifact locations; (3) start by running the app.
- Selected: option 2. Reason: it identifies code and data dependencies without noisy cache listings or changing the running environment.
- Initial evidence: project contains FastAPI modules, static frontend, tests, one 8,940-row target CSV, a pre-existing archive directory, migration docs, and many model artifacts. The current archive is inside the active tree and will need relocation after a backup and dependency scan.

## Findings and decisions

(To be updated in execution order. `SUBMISSION_EXCLUDE`: `_private_archive/`.)

### 2026-11-03 — Backup and dataset presentation cleanup
- Options considered for rebuilding: (1) regenerate values from archived inputs; (2) remove only the presentation field from the active canonical rows; (3) synthesize a new dataset from assumptions.
- Selected: option 2. Reason: it preserves every existing measurement value and matches the user's requirement that measurements never change. A generation pipeline is not appropriate here; the one retained builder will validate and reproducibly rewrite the canonical CSV.
- Options considered for legacy archive: (1) delete it; (2) keep it under data; (3) move all legacy inputs to _private_archive.
- Selected: option 3. Reason: preserves the requested materials while keeping them outside the submission data folder. SUBMISSION_EXCLUDE: _private_archive/.
- Created _private_archive/backup_20261103/ with a source snapshot and SQLite online backup before changes. The active CSV is now 8,940 rows and 14 documented columns; serialization removed only the final data_origin field, preserving every other cell string.
- Moved the prior source CSVs, generator, and manifest to _private_archive/legacy_inputs/. Removed the prior dataset-combination script; added scripts/build_dataset.py, which validates and normalizes the canonical file without altering row measurements.
- Database migration decision: drop only the historical-observation source_tag field; retain operational source tags because they distinguish operator-created ledger examples. Schema version advanced to 5. Existing DB migration is still pending.

### 2026-11-03 — Documentation and test updates
- Options considered: (1) patch stale claims line by line; (2) replace obsolete dataset/status summaries with concise current descriptions; (3) keep multiple competing historical summaries.
- Selected: option 2. Reason: stale metrics and provenance language conflicted across several files; concise replacements reduce contradictions, while the detailed audit and report retain useful evidence.
- Rewrote the data card and quality audit for the canonical 14-column file. The required simulated-data statement appears once in the data card. Replaced stale dataset summary/status files and removed the obsolete pooled-results JSON.
- Updated CSV integrity/import tests for the 14-column schema and removed tests tied to the retired rebuild implementation.
- Further source/UI and database verification remains in progress.

### 2026-11-03 — Schema migration, API boundary, and ML interval
- Options considered for the database label: (1) keep it in historical records; (2) retain it only as JSON metadata; (3) remove the historical table column and scrub stored row/import JSON.
- Selected: option 3. Reason: it removes the label from both the schema and historical row payloads while preserving measurement fields. Schema version 5 now uses an index and unique natural-key constraint for historical rows.
- API output decision: remove internal source_tag values from customer, sale, reorder, transaction, and report payloads; keep the internal operational fields used by idempotency and sample-data filters.
- Forecast interval options: (1) use final holdout RMSE; (2) use residual quantiles from pre-holdout rolling origins; (3) show no interval.
- Selected: option 2. Reason: it avoids using the final holdout to set interval width. Implemented a 90th-percentile absolute-error band with lower bound clipped at zero; coverage is not guaranteed.
- Model evaluation completed for 60 pairs across Naive, Seasonal Naive, MLR, Random Forest, and XGBoost; no pair evaluation failed. Results and 300 per-model records are in docs/MODEL_RESULTS.md and docs/model_metrics.json. Naive fallback was selected for 39 pairs.
- Database evidence: 8,940 observations, 60 series, no duplicate natural keys, no foreign-key violations, SQLite integrity_check=ok, and no historical label column. A SQLite online backup exists at _private_archive/backup_20261103/inventory.pre_review.db.
- Live UI inspection found Dashboard, Forecasting, and Data & Reports return HTTP 500 at the supplied URL; Inventory, Sales, Replenishment, and Purchasing rendered. The current-code quality service works directly on the migrated database, suggesting the app URL is served by a stale in-memory process. Attempts to start/restart the HTTP server from the terminal did not produce an accessible running process.
- Inventory policy cost simulation remains unreported because carrying-cost and shortage-penalty rates are absent. Live formula/API checks across ten series remain blocked by the server mismatch and source freshness policy.

### 2026-11-03 — Forecast persistence fix and residue check
- Options considered for saved intervals: (1) retrain whenever a cached artifact lacks a band; (2) reconstruct its interval radius from the persisted metrics; (3) silently omit interval output.
- Selected: option 2. The training path already persisted the pre-holdout rolling-error radius in each artifact metric, but the reload path omitted it while reconstructing metrics and therefore rejected valid saved suites. The loader now restores that value and applies the same interval. Focused save/reload/invalidation test passed in 63.66s.
- Updated the forecast API test to assert the current source-selection explanation rather than stale source-origin wording. Its focused rerun later stalled without a result; full pytest remains unverified.
- Retired dataset terminology scan across README, docs, API, application, frontend (excluding vendored Plotly), tests, and scripts returned no matches for the requested deprecated terms.
- Final checks after the edits: `python -m compileall -q api inventory_app scripts tests` passed; `node --check frontend/app.js` passed; `python -m scripts.build_dataset` passed with 8,940 rows, 60 series and SHA-256 `3e80743a161fc72aeca8b462974897a8468f1687f5d6374554df9df74b9de516`; selected dataset/migration/sample pipeline checks passed (4 passed in 37.00s); forecast artifact save/reload/invalidation passed (1 passed in 63.66s).
- The focused forecast API test was stopped after more than two minutes without a result. The full `pytest -q` attempt also yielded no result after several minutes and was stopped. An attempt to inspect process details with `Get-CimInstance Win32_Process ...` was denied by the environment. These checks should be rerun from a normal project shell.

### 2026-11-03 — Expanded completion plan and price research
- Options considered for the new scope: (1) patch isolated symptoms as they arise; (2) re-plan by hard dependencies from app recovery through pricing/risk/ML/policy to release; (3) restart the review from scratch.
- Selected: option 2. The first review already completed dataset cleanup and schema migration; the new plan preserves that work and orders newly requested changes by dependency.
- Price-source options: (1) use the supplied InfraLens August 12 category anchors plus dated market adjustments; (2) replace them with a generic September Dehradun list; (3) mix multiple incompatible online price estimates.
- Selected: option 1 pending product mapping. InfraLens provides per-material Dehradun dealer-to-retail anchors matching the brief; BusinessToday (2026-09-29) supports an October cement increase range, and SMM (2026-10-23) documents a regional steel rally that lost momentum in October. A generic Dehradun list had materially conflicting cement/brick/steel units and levels, so it will not replace like-for-like anchors. Current browser research found no itemized November dealer quotes for all project materials; adjustments remain explicit assumptions, not claimed market observations.
- Updated `docs/REVIEW_PLAN.md` as the first artifact for this scope. Before changing the dataset, code, or database, create a new snapshot and online SQLite backup for the expanded review.
- Snapshot completed at `_private_archive/backup_20261103_phase2/` before repricing or schema changes; includes source/docs/tests/frontend snapshot, canonical CSV, and SQLite online backup.

### 2026-11-03 — App root cause and request-time training
- Options for model work on requests: (1) keep fitting all models when cached artifacts are absent; (2) always return a cheap Naive-only result when no compatible offline suite is present; (3) introduce a background worker and job queue.
- Selected: option 2 with candidate training moved to `scripts/train_all.py`. It avoids blocking requests and extra worker infrastructure, and every fallback remains a real baseline evaluation.
- Live evidence: port 8000 `/api/health` returns the old two-field response and `/api/diagnostics` is 404, proving the visible process does not contain the current application routes. The current DB is schema 5 and has no historical `source_tag` column; the saved pre-review schema-4 model maps that column. Executing that legacy `SELECT source_tag` against the current DB reproduces `sqlite3.OperationalError: no such column: source_tag`, explaining the data-dependent 500 when the old process queries history. The exact server traceback remains unavailable because that old process writes no current file log.
- App fix: current code now logs startup and full request tracebacks to `logs/app.log`, reports schema/tables/dataset parity from `/api/health` and `/api/diagnostics`, and loads offline forecasts or returns a Naive fallback without fitting tree/regression candidates inside the request.
- Test stall evidence: even a trivial `FastAPI()` + `TestClient` GET did not return in this runtime; the timeout wrapper stopped it after 25 seconds. The previous forecast endpoint additionally executed the full candidate training suite on cache misses. The new `scripts/run_with_timeout.py` provides a hard wall-clock command timeout and output capture. TestClient integration is not yet verified in this environment.

### 2026-11-03 — Repricing, risk integration, and current verification
- Rebased only historical `unit_price_inr` values to the dated, documented Dehradun reference assumptions; reproduced source hash `4b60db1190bce14bbe057c7772fcb00a7024365f18e623e2d406018fd90faee4`. The builder reports 8,940 rows, 60 series, and zero stock-chain mismatches. The 13 original non-price columns match the phase-2 backup; two past-only derived level columns were added.
- Added schema v6 fields and migrated the active DB; all 8,940 canonical records have rebased prices and levels, SQLite integrity check is OK, and foreign-key check is empty. Historical observations did not create operational stock ledger rows.
- Implemented `inventory_app.risk.calculate_inventory_risk` and wired it to replenishment and the dashboard. The dashboard baseline uses the last four observed weekly quantities and recent one-step changes; service level defaults to 95%. Missing physical counts are High and do not receive a numeric order recommendation. The replenishment UI exposes 90/95/98% service choices and displays the implemented formulas.
- Added fresh-install initializer `scripts.init_database.py`, updated dataset audit/README, and implemented offline policy replay against stored chronological holdout predictions with 15/20/30% holding rates and 1.5/2/3× unit-value shortage costs. The retrospective simulation never writes ledger rows.
- Current checks: compileall, Node syntax, and dataset rebuild passed. Fifteen focused dataset/risk/ingestion tests passed (11.74 seconds); the broader database/calculation set produced 43 passes and one stale 14-column/date assertion, which passed after correction. Full `pytest -q` timed out after 180 seconds without output. Offline training completed in 221.86 seconds (60/60 pairs, 300 current-version artifacts, zero issues); `scripts.train_all --metrics-only` refreshed interval metadata. Policy replay completed 1,620 scenarios across 60 series. Final submission ZIP contains 122 files and no excluded state/artifact paths. Port 8001 bind was rejected by socket permissions, while port 8000 remains the old server.
- Fresh-install smoke check: `scripts.init_database` created a temporary database, imported 8,940 observations, and created no ledger movements.

### 2026-11-03 — Beginner project guide and viva preparation
- Options considered: (1) provide a short summary; (2) create the requested full guide from the project evidence; (3) claim live readiness and treat historical rows as current stock.
- Selected: option 2. The guide must teach the student while keeping simulated history, saved model results, and operational stock clearly distinct.
- Documented the dataset as self-created and simulated, the 2026 price anchors as indicative, the selected-model holdout versus Naive honestly, and the policy replay as an assumed-cost scenario where lower total cost did not produce the highest service level.
- Checked the unusual MASE scale in `inventory_app/forecasting.py`: weekly MASE divides MAE by the training mean absolute difference at a 52-observation lag. Explained it as dimensionless, not as a percentage or demand-normalized score.
- The three inventory examples use the latest 2026-11-02 canonical CSV observations, reconstructed closing stock, last-four-observation demand, and selected-model error sigma from `docs/model_metrics.json`. They are explicitly labeled simulated teaching calculations, not operational physical counts or live dashboard totals.
- Checked the actual feature builder before writing: it uses four consumption lags, the four-observation mean, and population standard deviation. Week-of-year, monsoon/peak-season flags, price, and price change are not inputs to the current per-series model; the guide says so rather than repeating those unimplemented feature ideas.
- Recorded the existing test and live-server limits from `docs/COMPLETION_REPORT.md`, `docs/BROWSER_QA.md`, and `docs/PROJECT_STATUS.md`; no new test run or code change was needed to write the guide.
- Created `docs/PROJECT_EXPLAINED.md` and its Word companion `docs/PROJECT_EXPLAINED.docx`; document rendering and page-by-page visual review remain required before delivery.
