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
