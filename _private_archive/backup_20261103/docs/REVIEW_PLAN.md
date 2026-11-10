# Review Plan

## Examiner review objective
Bring SiteStock to a reproducible, honest, working submission and presentation state. No Git commands will be used. Decisions and evidence will be recorded in `docs/REVIEW_LOG.md`.

## Task order and dependencies

| Order | Work | Depends on | Can run in parallel? | Status |
|---|---|---|---|---|
| 0 | Establish scope, decisions log, backups, and inspect project structure | None | No; first | In progress |
| 1 | Dataset cleanup, unified CSV, data card/audit, remove provenance wording and archive source artifacts | 0 | No; downstream code/data depend on final dataset | Pending |
| 2 | Database schema/migration/load and integrity/backup verification | 1 | No; depends on final dataset | Pending |
| 3 | API/UI inspection, validation, endpoint behavior, browser/server review | 2 (DB state) | UI source review can overlap ML source review; live app depends on 2 | Pending |
| 4 | ML leakage review, time-aware validation, baselines, inventory simulation, model lifecycle | 1; API integration follows 2 | Analysis and implementation may be separate, but reports depend on final runs | Pending |
| 5 | Product/code quality fixes, setup, tests, UI polish | 2–4 findings | Some documentation drafting can overlap implementation; final claims depend on results | Pending |
| 6 | Submission pack: report, demo, viva Q&A, presentation outline, scorecard | 1–5 verified results | Drafting can overlap; finalization depends on 1–5 | Pending |
| 7 | Final self-check and residue search | 1–6 | No; final verification after changes | Pending |

## Verification targets
- Dataset: expected row count and series, zero duplicate keys, valid ordered dates, stock-chain checks, SHA-256.
- Database: backed-up migration, fresh setup and repeatability, schema constraints/indexes, CSV-to-DB parity, formulas and integrity.
- Application: each page, API route, `/docs`, input edge cases, visible errors, logs, and browser console where browser access is available.
- ML: explicit weekly-demand target, leakage-safe time splits, identical test windows for Naive and candidate models, per-series and aggregate MAE/RMSE/WAPE or MASE, inventory policy comparison, model persistence.
- Code: compile checks, JS syntax, dataset checks, pytest, server startup and live endpoint smoke tests where commands/environment permit.
- Submission content: truthful simulated-data statement only in the data card and report limitations; findings, decisions, and unverified work clearly disclosed.

## Execution notes
- Back up the database and files before any destructive change.
- Preserve all existing measurement values; dataset rebuilds may only normalize presentation/schema, not alter measurements.
- Archive legacy inputs outside submission folders without deleting them; document archive exclusion only in this log.
- If a command is blocked, skipped, or times out, continue independent work and record the exact command, expected duration, success signal, and what was not verified under `COMMANDS FOR THE USER TO RUN` in the final response.
