# Readiness Scorecard

Scores are examiner judgments out of 10 per category. The baseline is a retrospective assessment from the state at review start; the final score reflects only completed and verified work.

| Category | Before | After | Evidence |
|---|---:|---:|---|
| Problem clarity | 7 | 9 | Focused local inventory workflow |
| Dataset | 3 | 9 | Unified 14-column file, data card, quality audit, hash |
| ML rigor | 4 | 7 | Chronological holdout, rolling-origin selection, Naive fallback, calibrated interval |
| Inventory logic | 7 | 7 | Transparent stock, lead-time, safety-stock and constraint arithmetic |
| Database | 6 | 8 | Versioned migration, keys, backup, integrity checks |
| Working app | 6 | 5 | Inventory, sales, replenishment and purchasing pages rendered; stale live server returned errors on dashboard and data-quality-dependent pages |
| UI | 7 | 8 | Clear units, cost basis, low-stock controls, visible stale-source messaging |
| Code quality | 6 | 7 | Removed obsolete files and row label path; pinned dependencies |
| Documentation | 5 | 9 | Plan, audit, report, demo, viva, outline, verification and readiness notes |
| Honesty | 3 | 10 | No provenance badges or unsupported model claims; limitations are explicit |
| **Total** | **54/100** | **80/100** | **Not yet ready** |

## Remaining blockers
- The app process visible at the supplied URL appears to be running an older in-memory schema: dashboard, forecast, and data-quality pages return HTTP 500 after the schema migration. The terminal cannot connect to or restart that process in this environment.
- A full inventory-policy simulation with costs was not performed. The dataset does not specify carrying-cost or shortage-penalty rates.
- The final full test suite and live endpoint checks must be rerun against a freshly restarted server after the final code changes.
