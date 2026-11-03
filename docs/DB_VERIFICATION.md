# Database Verification

## Current evidence

Verified on 2026-11-03 against `data/inventory.db` after schema v6 migration and canonical price/level rebase:

- Schema version 6; application tables created.
- Historical observations: 8,940 rows, 60 series, 149 each; CSV/DB counts agree.
- Current price and demand/price level values are populated for all canonical rows.
- Duplicate natural keys: zero; missing/invalid labels: zero.
- SQLite `integrity_check`: `ok`; `foreign_key_check`: zero violations.
- Adjacent stock-chain comparisons: 8,880; mismatches: zero within 1e-6.
- Historical data did not initialize or create operational inventory transactions.
- Fresh pre-change copy and SQLite online backup: `_private_archive/backup_20261103_phase2/`.
- Fresh-install smoke check: `scripts.init_database` created an isolated temp DB, imported all 8,940 rows, and created no operational stock transactions.

## Schema and migration

Initialization applies versioned additive updates. Schema 6 adds `demand_level` and `price_level` to historical observations after their definitions were added to the canonical source. Historical redundant `source_tag` is removed; operational source tags remain internal. The migration checks columns before altering them and advances the version after applying the schema.

`scripts.init_database` creates the schema and imports the canonical CSV idempotently for a fresh installation. `scripts.rebase_database_prices` is for an existing imported database; it validates natural keys and unchanged quantity fields before updating historical prices/derived labels and documented catalogue reference medians. No ledger rows are created. A SQLite online backup should be taken before schema or data updates.

## Formula and API verification

The shared `inventory_app.risk.calculate_inventory_risk` module is used by both replenishment API and dashboard. Twelve boundary tests pass. Direct invocation of the dashboard route against the active database returned 60 risk pairs, counts across all pairs, and 30 prioritized display rows. Direct HTTP verification of the newly edited app is pending because port 8000 is occupied by a stale process and this environment's TestClient hangs at startup even for a trivial app.

Replenishment uses lead-time demand + service-level safety stock, incoming quantity, order-up-to gap, EOQ candidate, minimum order and pack rounding. High/Medium/Low precedence and overstock rules are documented in `INVENTORY_LOGIC.md`. The UI includes 90/95/98% service options; final browser/API verification must be repeated after restarting the current application.
