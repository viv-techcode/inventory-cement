# Readiness Scorecard

Scores are examiner judgments out of 10. “Before” describes the review-start state; “After” scores the current code and artifacts, with evidence and live-environment limitations called out separately.

| Category | Before | After | Evidence |
|---|---:|---:|---|
| Problem clarity | 7 | 9 | Focused local inventory workflow |
| Dataset | 3 | 9 | 16-column dataset, audited rebased prices, quantity preservation, stock-chain validation, hash |
| ML rigor | 4 | 8 | 60/60 series, rolling-origin selection, holdout MAE/RMSE/WAPE/MASE and interval coverage |
| Inventory logic | 7 | 9 | Shared risk function, service-level safety stock, dashboard counts, boundary tests, cost sensitivity simulation |
| Database | 6 | 8 | Schema v6, additive migration, 8,940 observations, SQLite integrity OK and zero FK violations |
| Working app | 6 | 5 | Current code has diagnostics and faster forecast path; live port 8000 is a stale server and TestClient hangs even for a trivial app |
| UI | 7 | 9 | Risk dashboard, service-level control, forecast MASE/coverage, clear unit and source notes |
| Code quality | 6 | 7 | Shared risk/pricing/level modules, offline training and timeouts; full suite/live smoke still pending |
| Documentation | 5 | 9 | Price sources, dataset audit, risk logic, model results, policy simulation, demo, viva, outline, report and log |
| Honesty | 3 | 10 | Simulated data, reference prices, assumed policy costs, limits and unverified live checks disclosed |
| **Total** | **54/100** | **82/100** | **Code and artifacts are substantially complete; live readiness is not verified** |

## Remaining verification

- The app running at port 8000 is an older process: its health response lacks current checks and `/api/diagnostics` returns 404. A current-code direct dashboard route check works, but a browser check against a newly started process remains outstanding.
- FastAPI `TestClient` initialization stalls in this environment, including with a trivial app. Fifteen focused dataset/risk/ingestion tests pass; a broader database/calculation subset had 43 passes and one stale expectation, which passed after correction. The complete suite timed out at 180 seconds without output.
- Verify forecast API and replenishment end-to-end after the current process is restarted in a normal shell. Dashboard direct invocation covers all 60 pairs, but it is not an HTTP/browser smoke test.
- Policy costs and unit values are scenarios, not observed economics. Do not present simulated cost reduction as realized savings or use suggestions as purchasing authority.
