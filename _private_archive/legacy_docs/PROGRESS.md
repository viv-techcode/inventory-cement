# Progress

Updated 2026-11-03. Current evidence and outstanding checks are maintained in `PROJECT_STATUS.md`, `REVIEW_PLAN.md`, `REVIEW_LOG.md`, and `READINESS_SCORECARD.md`.

## Completed

- Rebased only historical reference prices; preserved quantity and stock-flow values. Canonical source hash is recorded in the data card and audit.
- Migrated the database to schema 6 and verified SQLite integrity and foreign keys.
- Added past-only demand/price labels and source-documented price assumptions.
- Centralized inventory risk and wired it to replenishment and dashboard.
- Trained five weekly forecast candidates across 60 pairs; all 300 current model artifacts completed without issues.
- Completed 60-series policy replay across three policies and nine cost scenarios.
- Built a submission ZIP that excludes local database state, model artifacts, backups, logs, caches, and virtual environments.

## Verification still open

- Full pytest timed out after 180 seconds; focused dataset/risk tests passed (14), broader database/calculation subset passed 43 with one stale test expectation corrected and that test passed separately.
- Browser/API verification against a clean process remains blocked by the stale server bound to port 8000 and socket permission denial on port 8001.
