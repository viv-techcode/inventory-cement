# Work Items & Execution Plan

1. [x] Step 1: Complete and verify audit baseline measurements across the 7 application pages, dataset forensics, cross-page totals, and repo deployment.
   - Done when: All Step 1 audit numbers, forensic distributions, XSS tests, and deployment checks are documented in `../audit_out/`.
   - Verified by: `py -3.13 ../audit_out/run_audit.py` and output logs in `../audit_out/`.

2. [x] Step 1.5: Analyze forecasting sparsity, intermittency, and signal across the 90 series and 15 materials; decide top-down vs direct modeling.
   - Done when: ADI, CV^2, Syntetos-Boylan classification, seasonal decomposition, and holdout benchmarks are calculated and logged in `docs/DECISIONS.md`.
   - Verified by: `../audit_out/step1_5_forecasting_data_diagnostics.txt`.

3. [x] Step 2A: Revise dataset generator (`scripts/build_ledger.py`) for realism inside hard constraints (8,490 rows, seed, 6 sites, 15 SKUs).
   - Done when: Ledger includes customer price tiers, supplier material specialization, March 2025 steel margin squeeze, net non-zero adjustments, supplier delays, stock-outs, distinct site personalities, and differentiated inventory turns.
   - Verified by: `py -3.13 -m scripts.build_ledger` producing 8,490 rows, SHA-256 reproducibility, zero negative running stock, and forensic validation script.

4. [x] Step 2B: Align Dashboard to company-level default view with optional site/material filters and exact Sales page reconciliation.
   - Done when: First-load Dashboard displays company-wide totals matching Sales page, with clear optional filters and full reorder alert count.
   - Verified by: HTTP GET `/api/dashboard` compared with `/api/sales` and Playwright page checks.

5. [x] Step 2C: Implement robust XSS defense and server-side markup sanitization/rejection across all free-text fields.
   - Done when: Dynamic strings in `frontend/app.js` use the `esc()` helper; API schemas reject or sanitize HTML tags in customer and notes fields; tests prove script injections are stored inert and rendered harmless.
   - Verified by: Pytest security tests and Playwright script injection tests.

6. [x] Step 2D: Fix inventory costing and valuation to ensure weighted-average cost is never None/Unavailable at baseline.
   - Done when: Opening balance assigns valid unit costs across all 90 pairs; stock value is fully costed from recorded costs; alert counts reconcile across all views.
   - Verified by: Recomputed inventory valuation across all 90 pairs via `/api/inventory/balances` and `/api/dashboard`.

7. [x] Step 2E: Upgrade forecasting engine and model outputs.
   - Done when: Expanding-window walk-forward folds are surfaced in the UI/docs; holdout evaluation metrics (WAPE, MASE, coverage, residuals) are updated in `docs/model_metrics.json`; material-level and top-down insights are presented honestly.
   - Verified by: `py -3.13 -m scripts.train_models` and API evaluation tests.

8. [x] Step 2F: Clean repository tracking, dependencies, and deployment configuration.
   - Done when: Tracked `.db` files and model binaries are removed from git index; `.gitignore` is updated; `pytest` is moved to `requirements-dev.txt` while keeping `requirements.txt` minimal for Render; app runs without archive folder.
   - Verified by: `git ls-files "*.db"` returning empty and test run with archive folder moved.

9. [x] Step 2G: Implement comprehensive pytest test suite.
   - Done when: Tests cover ledger integrity, nonnegative stock, sales margin calculations, PO link integrity, cross-page reconciliation, reset idempotency, XSS defense, and banned-word scanner.
   - Verified by: `pytest` passing all 14 test cases.

10. [x] Step 2H: Update project documentation to final state.
    - Done when: `README.md`, `docs/DATASET_CARD.md`, `docs/PRESENTATION_GUIDE.md`, `docs/PLAN.md`, `docs/DECISIONS.md`, and `docs/RENDER_DEPLOYMENT.md` reflect final verified figures with no banned words or AI disclosures.
    - Verified by: Banned-word scanner script returning zero hits across all active files.

11. [x] Step 2I: Execute git commit and push attempt.
    - Done when: All changes are committed with concise student-style commit messages (max 5 words); `git push origin master` is executed and its exact outcome/credentials status is recorded in `docs/VERIFICATION_LOG.md`.
    - Verified by: `git log` and terminal push output.

12. [x] Step 3: Run independent 4-persona self-review loop (Professor, Student presenting, Distributor ops manager, External accountant) and handoff checks.
    - Done when: Each persona evaluates the system with READY/NOT READY verdict backed by execution evidence; `../audit_out/handoff_checks.md` is authored; database reset is proven.
    - Verified by: Execution of `scripts/reset_database.py` and review against criteria.
