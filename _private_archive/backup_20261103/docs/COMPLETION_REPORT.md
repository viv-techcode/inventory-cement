# SiteStock completion report

Date: 2026-11-02

This report records an earlier implementation and walkthrough snapshot. Its test and runtime statements are historical; the final documentation consistency pass did not complete another full-suite or end-to-end run. Current verification attempts are recorded in [`TEST_RESULTS.md`](../TEST_RESULTS.md).

## Summary

Inventory and purchasing now work through the API and interface, replenishment includes approved PO pipeline stock, and per-series forecasting selects by rolling-origin MAE before an untouched holdout. The pooled/global forecasting model and log1p comparison remain incomplete, so the overall request is **Partial**. Forecast results are weak: Naive was selected for 39 of 60 series, and median holdout R² is negative for every candidate.

The Construction Materials Dehradun Dataset is one merged file with 6,300 self-created rows plus 2,640 deterministic generated rows. It is not real observed demand. All 1,800 rows in the final 30-week holdout are generated; metrics are diagnostics only.

## Changes by file

- `inventory_app/forecasting.py` — added three pre-holdout expanding-window origins, selection by one metric (MAE), ML-to-Naive fallback, and persisted rolling selection scores; incremented model version to 1.3.
- `inventory_app/replenishment.py` — returns the forecast period inputs and rounds recommended quantities upward to the four-decimal inventory precision.
- `inventory_app/procurement.py` — rounds PO quantities upward to four decimals so a recommendation cannot create a PO that is microscopically short.
- `api/routes_procurement.py` — new supplier, PO, PO status, and receipt endpoints backed by the existing procurement service.
- `api/main.py`, `api/schemas.py` — registered procurement routes and request validation schemas.
- `api/routes_replenishment.py` — includes eligible approved and partially received PO lines in incoming stock.
- `frontend/index.html`, `frontend/app.js` — added Purchasing view, one-click PO from a positive recommendation, approval/status actions, receipt action, forecast comparison/holdout text, and explicit calculation inputs.
- `scripts/train_all_models.py` — trains/persists model version 1.3 and reconciles stale artifact references and orphan files.
- `tests/test_procurement_api.py` — added supplier → PO → approval → receipt API coverage, including four-decimal quantity precision.
- `tests/test_replenishment.py` — added a recommendation precision regression test.
- `pytest.ini` — configured `pythonpath = .` and `testpaths = tests` for plain pytest imports.
- `.streamlit/config.toml` — removed after confirming no Streamlit app or dependency is used.
- `README.md`, `docs/MODEL_RESULTS.md`, `docs/DATA_PROFILE.md` — updated dataset provenance and current model method/results.
- `docs/DATA_CHECK.md` — added actual SQLite counts, import/rejection details, CSV reconciliation, and QA-copy code-reference check.
- `docs/PROJECT_STATUS.md` — updated Streamlit cleanup status.
- `data/inventory.db` — retained the operational ledger as-is; removed 300 stale forecast metadata rows whose `/home/user/...` artifacts were absent. Its transaction/sales/procurement counts stayed unchanged. The pre-change copy is `data/inventory.backup.db`.
- `artifacts/models/` — trained 300 version 1.3 artifacts and retired 305 unreferenced `.joblib` files. Final audit: 600 DB artifact references, 600 existing files, zero orphans (300 retained version 1.2 and 300 version 1.3).

## Before and after forecast metrics

MAE/RMSE averages below are macro-averages of per-series values in their own units; quantities are not pooled across materials. The untouched holdout scores are numerically unchanged because the fitted series models and final split remain the same. The selection method and winner distribution changed. Full aggregate and median details are in `docs/MODEL_RESULTS.md`.

| Model | Before wins | After wins | Mean holdout MAE | Median MAE | Mean RMSE | Median RMSE | Mean R² | Median R² | Mean WAPE | Median WAPE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Naive | 21 | 39 | 65.219 | 27.050 | 73.825 | 34.080 | −2.221 | −2.014 | 30.282% | 29.835% |
| Seasonal Naive | 1 | 0 | 305.374 | 58.685 | 441.371 | 73.362 | −81.806 | −11.793 | 87.732% | 49.203% |
| Multiple Linear Regression | 1 | 2 | 182.116 | 46.865 | 205.218 | 55.783 | −52.476 | −19.586 | 106.356% | 75.999% |
| Random Forest | 20 | 6 | 104.968 | 28.219 | 116.345 | 31.078 | −32.767 | −1.566 | 63.062% | 25.898% |
| XGBoost | 17 | 13 | 80.536 | 27.146 | 93.348 | 32.125 | −12.143 | −1.944 | 47.128% | 29.110% |

## Tests and walkthrough

- `python -m scripts.train_all_models` — **passed**, 60/60 series; 300 model artifacts; zero model issues; 115.91 seconds.
- Focused pytest command — **incomplete**. Two invocations produced partial progress dots but no test summary; the longer run was interrupted after stalling. The new API test's pass status is not established. Per instruction, it was not retried after termination. The user's prior full-suite result (43 passed) was not rerun.
- `node --check frontend/app.js` and `python -m py_compile` for changed Python files — passed.
- The real retained DB received only model metadata/artifact maintenance; no walkthrough sale, supplier, PO, receipt, or operational transaction was posted to it. Auto-review rejected the live sale write. The end-to-end workflow therefore ran on a fresh isolated clone of `inventory.db`, which contains the actual imported observations and starting ledger snapshot.

Walkthrough on the isolated clone (GMS Road / AAC Blocks):

1. Dashboard — API returned 200; as-of date 2026-11-02.
2. Stock lookup — 675.1818 pieces.
3. Sale — recorded 1 piece; balance became 674.1818.
4. Forecast — API returned 200; XGBoost selected from five candidates; 30 holdout periods reported.
5. Replenishment — with a stated 7-day lead time and 30-day safety stock, recommendation was 886.7726 pieces. Inputs: forecast lead-time demand 344.5264; safety stock 1,216.4280; current stock 674.1818; eligible incoming 0; lead time 7 days.
6. Purchase — created PO `PO-20261102-001` as Draft; submitted and approved through the status API.
7. Receipt — received 886.7726 pieces; PO status became Received; stock increased from 675.1818 before the sale to 1,560.9544 after receipt.

## Feature status

| Feature | Status | Evidence / remaining work |
|---|---|---|
| Forecast API and per-series model comparison | Done | Five candidate rows and a 30-period holdout returned in the API walkthrough; artifacts persisted for 60 pairs. |
| Rolling-origin model selection and Naive fallback | Done | Three pre-holdout folds, MAE-only selection and fallback are in code; 39/60 series select Naive. |
| Pooled/global features and log1p comparison | Partial | Not implemented. Models still fit each site/material series separately and do not use category, project phase, price or lead-time features. |
| Forecast comparison UI | Done | Comparison table, actual/predicted chart, per-series model leaderboard and generated holdout note are present. |
| Replenishment arithmetic and visible inputs | Done | Approved PO pipeline is deducted; result displays forecast inputs, safety stock, stock, incoming, lead time and rounded quantity. Precision regression coverage was added but pytest did not complete. |
| Supplier and purchase workflow | Done | API/UI endpoints and isolated end-to-end API flow completed through a Received PO and changed stock. Automated API test was added but not confirmed passing. |
| Dataset/database integrity | Done | `docs/DATA_CHECK.md` reconciles 8,940 CSV observations, 60 series and every DB table; retained DB contains no walkthrough transactions. |
| Artifacts | Done | 600 artifact rows match 600 existing `.joblib` files; zero orphan files. |
| Plain pytest configuration | Done | `pytest.ini` added; plain full-suite command not run due the no-repeat instruction. |
| Streamlit cleanup | Done | No Streamlit dependency or usage; `.streamlit/` removed. No other dependencies were removed without evidence they were unused. |
| End-to-end API walkthrough | Done | Completed on an isolated clone; live operational DB writes were blocked by automatic review. |

## COMMANDS FOR THE USER TO RUN

Run these from the project root. The focused pytest command below was invoked twice and stalled without a summary; it is listed for a fresh, single attempt if you want the new API regression test result.

1. `python -m scripts.train_all_models` — retrains and persists per-series models, reconciles artifact rows/files, and prints per-pair outcomes. Expect about 2 minutes on this machine. Success is `60/60 pair(s)`, `0 issue(s)`, and a model-artifact count.
2. `python -m pytest -q` — runs the full suite; may take about 200 seconds as in the user's earlier run. Success is a final summary such as `43 passed` and exit code 0. It was not rerun here.
3. `python -m pytest -q tests/test_procurement.py tests/test_procurement_api.py` — runs procurement service/API tests only. The previous invocation stalled without a summary; it may take several minutes because each fixture imports the 6,300-row CSV. Success is a final all-passed summary and exit code 0.
4. `pytest -q` — verifies the plain pytest entry point and runs the same full suite; it was skipped to avoid repeating the full suite. Expect roughly 200 seconds; success is the final all-passed summary and exit code 0.
5. `uvicorn api.main:app --host 127.0.0.1 --port 8000` — starts the normal app. It stays running until Ctrl+C; success prints `Application startup complete` and a local URL. The first sandboxed attempt could not be reached due socket restrictions, and the later port-8000 attempt found the port occupied.
6. `uvicorn api.main:app --host 127.0.0.1 --port 8765` — starts the app on an alternate local port; it stays running until Ctrl+C. Success prints `Application startup complete` and `Uvicorn running`. The successful server sessions were stopped after their walkthroughs.
7. `$env:INVENTORY_DB_URL='sqlite:///D:/myproject/inventory/workspace-01a19a5e-bdb8-707d-977a-9c6daa143d43/data/walkthrough.db'; $env:INVENTORY_ARTIFACTS_DIR='D:/myproject/inventory/workspace-01a19a5e-bdb8-707d-977a-9c6daa143d43/data/walkthrough_artifacts'; uvicorn api.main:app --host 127.0.0.1 --port 8765` — starts SiteStock against an isolated clone for a repeatable write walkthrough, not the retained ledger. Expect several seconds; success prints startup complete and the local URL. The walkthrough clone and temporary artifacts have been removed.
