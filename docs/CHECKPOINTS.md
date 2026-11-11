# Checkpoints Log

## Milestone 1: Audit Baseline & Diagnostics (Steps 1 & 1.5)
- **Status:** Complete.
- **Evidence Reference:**
  - `../audit_out/step1_app_browser.json` (Playwright headless browser audit of 7 tabs)
  - `../audit_out/step1_cross_page_totals.txt` (Reconciliation of revenue, COGS, margins, stock value, open POs)
  - `../audit_out/step1_dataset_forensics.txt` (Quarterly prices, customer distribution, margins, site mix)
  - `../audit_out/step1_forecasting_source.txt` (Source inspection of models, holdout WAPE/MASE, coverage)
  - `../audit_out/step1_repo_deployment.txt` (Tracked files, .db detection, banned words, render.yaml)
  - `../audit_out/step1_xss.txt` (XSS payload evaluation)
  - `../audit_out/step1_5_forecasting_data_diagnostics.txt` (90 series vs 15 material series intermittency analysis)
- **Key Findings:**
  1. Dashboard sales default was scoped to single site/material instead of company-level totals.
  2. Syntetos-Boylan analysis confirmed 81/90 site-level series are Lumpy, while all 15 material-level series are Smooth/Erratic, achieving 45.88% holdout WAPE.
  3. All 28 adjustments formed cancelling pairs; customer pricing was uniform; suppliers were unspecialized.
  4. Tracked `.db` files existed in git index in `_private_archive`.
## Milestone 2: Step 2 Comprehensive Fixes & Verification
- **Status:** Complete.
- **Evidence Reference:**
  - `data/construction_materials_ledger.csv`: SHA-256 `798dd4658f147885d2f831496a08ced623819dd10d11bec5803dd703e7c33d77`, exactly 8,490 rows, 0 negative running stock.
  - `docs/model_metrics.json`: 450 models trained, 16-week holdout, walk-forward folds, empirical coverage 83.9%.
  - `tests/test_compliance_and_reconciliation.py` & `tests/test_ledger.py`: 14 passed pytest suite.
  - Reset proof: `py -3.13 -m scripts.reset_database` restored baseline with 8,490 ledger rows, 7,932 sales, 440 receipts, 28 POs, 90 planner reviews.
- **What is Next:**
  - Milestone 3: Step 3 Independent 4-Persona Review Loop and handoff verification.
- **Open Risks:**
  - Remote repository write permissions on `origin/master`.
