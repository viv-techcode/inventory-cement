# Examiner Review Plan — November 2026

## Objective
Deliver a working and reproducible SiteStock project with a verified price-rebased dataset, one shared inventory risk model, honest model evaluation, policy sensitivity results, and a clean submission bundle. No Git commands will be used. Decisions and evidence go in `docs/REVIEW_LOG.md`.

## Work order and dependencies

| Order | Phase | Work | Depends on | Parallel work | Status |
|---|---|---|---|---|---|
| 0 | Plan | Set scope, order, and verification gates | None; first | None | Complete |
| 1 | App and tests | Reproduce 500s; traceback logging, diagnostics/startup checks; locate slow path; offline training/artifact loading; fast timed test suite; verify on port 8001 if needed | Existing schema and current code | Price research and risk-design research can proceed independently | In progress |
| 2 | Dataset and pricing | Inspect materials/sites/columns; source current price anchors; implement config-driven Nov 2026 rebasing in builder; preserve quantities/stock chain; demand levels | Backup before any data edits | Price source research can run alongside Phase 1 diagnosis | Pending |
| 3 | Risk logic | One risk module, formulas/precedence/suggestions; API, DB view and UI use same output; boundary/scenario tests; 10-series manual/API check | Phase 2 finalized price/demand fields; API stability from Phase 1 | Risk design and test design can proceed in parallel | Pending |
| 4 | ML | Offline all-series training; rolling-origin metrics incl. MASE; leakage checks; interval coverage; plots; save/load/API checks | Phase 2 dataset; Phase 1 artifact path | Metrics analysis can proceed alongside risk module | Pending |
| 5 | Policy simulation | Compare validated model, Naive, fixed reorder; cost sensitivity assumptions/table | Phases 3–4 outputs and fixed test window | None once inputs fixed | Pending |
| 6 | Product and DB | Fresh install, migrations/idempotency/backup restore; API edges; dashboard, risk, chart, packaging, paths, requirements and README | Phases 1–5 fixes | UI and documentation drafts may overlap; final claims depend on verification | Pending |
| 7 | Submission pack | Update report/demo/viva/slides/scorecard; submission zip script | Phases 2–6 results | Drafting can overlap implementation; finalization serial | Pending |
| 8 | Final check | Timeout-bounded full tests, build/compile, server/page/endpoint/browser/log checks, formula audit, DB integrity, terminology scan | All prior phases | None; final state only | Pending |

## Verification gates
- Dataset: 8,940 rows, 60 series, expected columns, no missing/natural-key duplicates/negative stock, stock chain within 1e-6, price levels plausible, consistent units, recorded SHA-256.
- App: clean startup self-check, structured health/diagnostics, traceback in `logs/app.log`, no silent request-time model fitting; live or second-port smoke tests.
- Risk: formula agreement across manual calculation, API, persisted view, and UI; boundary tests and high/medium/low/overstock cases.
- ML: identical chronological splits for all models, train-only preprocessing, per-series and aggregate MAE/RMSE/WAPE/MASE, interval empirical coverage, persisted load and endpoint checks.
- Policy: same held-out weeks across policies; service level, stock-out weeks, average stock value, orders, total cost under documented sensitivity assumptions.
- Submission: all claims trace to outputs; archive/backups/logs/caches excluded from ZIP.

## Decision rules
- Take fresh file and SQLite online backups before dataset, migration, or schema edits.
- Reprice only price/value fields; do not change any demand, receipt, stock, or quantity measurement.
- Price references are indicative dealer-to-retail levels. Explicitly identify dated sources and adjustments; do not call indicative prices official.
- Every command expected to take over 10 seconds gets a timeout. If blocked or timed out, record its exact command, duration, success signal, and unverified scope for the final response.
- If requested pricing references cannot be independently sourced, disclose the supplied anchor as an assumption and preserve its provenance in `docs/PRICE_SOURCES.md`.
