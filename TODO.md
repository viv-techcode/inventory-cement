# Work Items

1. [x] Audit the repository and record the starting state.
   - Done when: `docs/PLAN.md` records the existing architecture, dataset, routes, deployment, missing files, and working-tree state.
   - Verified by: `git status --short --branch`; inspect `api/`, `inventory_app/`, `scripts/`, `tests/`, `README.md`, and `docs/`.
2. [x] Research material prices, GST, seasonality, inventory policy, forecasting, and Render deployment.
   - Done when: sources and consultation dates are recorded in `docs/DECISIONS.md` and `docs/PRICE_REFERENCES.md`.
   - Verified by: source URLs and extracted rate/method/platform facts are checked against primary or clearly identified reference pages.
3. [x] Finalize data and system design.
   - Done when: schema, company identity, turnover target, units, forecast hierarchy, and deployment settings are recorded.
   - Verified by: review `docs/PLAN.md` and `docs/DECISIONS.md` against the project requirements.
4. [x] Build and validate the single ledger.
   - Done when: a reproducible 8,490-row ledger meets every schema, date, identifier, site, unit, and stock-flow condition.
   - Verified by: `python -m scripts.build_ledger` and the ledger audit command documented with the builder.
5. [ ] Rebuild the database from the ledger and align all application pages and APIs.
   - Done when: baseline counts and financial/stock totals reconcile across all pages, and operational actions work end to end.
   - Verified by: focused reconciliation and API checks recorded in `docs/VERIFICATION_LOG.md`.
6. [ ] Complete forecasting, reporting, reset, and smoke tooling.
   - Done when: the saved model comparison and reports meet the forecasting design, and reset/smoke scripts work.
   - Verified by: training, reset, and URL smoke commands with output in `docs/VERIFICATION_LOG.md`.
7. [ ] Complete supporting documents and deployment configuration.
   - Done when: all required documents, `render.yaml`, and deployment instructions agree and meet content rules.
   - Verified by: Markdown/content audit and Render Blueprint validation.
8. [ ] Run the final acceptance audit and inspect each page.
   - Done when: every acceptance item in `docs/PLAN.md` is green or an external access limitation is precisely documented.
   - Verified by: full test, HTTP/API, static page, ledger, forecast, content, and consistency checks in `docs/VERIFICATION_LOG.md`.
9. [ ] Commit the finished milestones and push `master`.
   - Done when: all intended project changes are committed and `origin/master` matches local `master`.
   - Verified by: `git status --short --branch` and `git rev-parse HEAD origin/master`.
