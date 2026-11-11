# Work Items

1. [x] Audit the repository and record the starting state.
   - Done when: `docs/PLAN.md` records the starting architecture, data, routes, deployment, missing files, and working-tree state.
   - Verified by: `git status --short --branch`; source and document inspection.
2. [x] Research material pricing, tax, seasonality, inventory policy, forecasting, and Render deployment.
   - Done when: consulted sources and dates appear in `docs/DECISIONS.md` and `docs/PRICE_REFERENCES.md`.
   - Verified by: source URLs and reference details recorded for each design choice.
3. [x] Finalize the ledger and application design.
   - Done when: identity, units, turnover, forecast granularity, date cutoff, and hosting settings are recorded.
   - Verified by: review `docs/PLAN.md` and `docs/DECISIONS.md` against the request.
4. [x] Build and validate the single ledger.
   - Done when: the reproducible ledger meets its row count, schema, ID, date, site, unit, and stock-flow requirements.
   - Verified by: two runs of `python -m scripts.build_ledger` produced the same SHA-256; row and flow checks passed.
5. [x] Load the database and align pages, APIs, and operating actions.
   - Done when: baseline records reconcile, app-entered sales and receipts update stock, planner runs are recorded, and baseline records restore cleanly.
   - Verified by: `python -m pytest -q` returned 5 passed; direct planner, health, and report checks passed; isolated reset returned 8,490 events and 90 planner reviews.
6. [x] Complete forecasting, reports, reset, and smoke tooling.
   - Done when: saved model comparisons include holdout and forward predictions; metrics, residuals, reset, and URL smoke tooling are available.
   - Verified by: `python -m scripts.train_models` completed 90/90 series; `docs/model_metrics.json` includes 16 holdout weeks, 13 future weeks, and residual/feature details; isolated reset passed.
7. [x] Complete supporting documents and deployment configuration.
   - Done when: required project documents, Render Blueprint, and deployment guide agree and pass the wording audit.
   - Verified by: YAML parse, active-file content scan, and review of all required documents.
8. [x] Run final local acceptance and record external-access limits.
   - Done when: automated reconciliation, ledger, model, content, and static checks pass; HTTP/browser and Render limitations are stated precisely.
   - Verified by: `python -m pytest -q`, `compileall`, `node --check`, database scan, direct `_self_check`, and `docs/VERIFICATION_LOG.md`.
9. [ ] Push the finished commits to `origin/master`.
   - Done when: intended work is committed and `origin/master` matches local `master`.
   - Verified by: `git push origin master` returned HTTP 403; `git rev-parse HEAD origin/master` confirms local `master` is six commits ahead after recording this access failure.
   - Blocker: the configured GitHub identity lacks write permission to the configured repository.
