# Database Verification

## Severity summary
- **Critical — live process mismatch:** the UI at the supplied URL returns HTTP 500 on dashboard and data-quality endpoints after schema version 5. The migrated database itself passes integrity checks; the live process appears to have loaded the pre-migration model. Restart and repeat endpoint checks.
- **Major — policy cost validation:** the dataset has no carrying-cost or shortage-penalty rates, so a defensible cost comparison is unavailable.
- **Minor — SQLite operational tags:** internal tags remain on operational records for idempotency and sample-data isolation. Historical observations have no row-label field, and API/export serializers omit those internal tags.

## Schema and integrity evidence
Verified against data/inventory.db on 2026-11-03 after migration:
- Schema version 5; 17 application tables.
- Historical observations: 8,940 rows; unique source key and natural key; unique date/site/material constraint; site/material/date index.
- Historical row-label column absent. Historical observations retain a foreign key to import_runs.
- SQLite integrity check returned ok.
- Foreign-key check returned zero violations.
- Duplicate date/site/material keys: zero.
- CSV and DB observation counts both equal 8,940.
- Per-series row counts are 149; 60 series.
- Historical missing values, stock-chain breaks, and negative calculated closing balances: zero.

## Keys, constraints, and indexes
SQLAlchemy models define primary keys across tables, unique site identifiers and material names, idempotency keys on transactional records, unique site/material reorder rules, and foreign keys from ledger, sales, PO lines, receipts, and observations. Quantity, price, status, and date-related check constraints reject invalid persisted states. The historical lookup index orders site/material/date.

## Migration, transaction, backup, and restore
- Schema version was advanced to 5. Migration drops only the historical observation label field; operational tables and measurements remain unchanged.
- Database initialization was run twice as part of migration/re-import checks. The canonical import recorded the new file fingerprint without creating duplicate observations.
- A SQLite online backup was created before changes at _private_archive/backup_20261103/inventory.pre_review.db.
- Restore path: stop the app, restore the backup with SQLite's backup API to a separate target, point INVENTORY_DB_URL to that path, and run initialization. Do not copy only a live WAL database file.
- Service functions use SQLAlchemy transactions and rollback on exceptions; sales and sample-ledger operations use transaction scopes. Database integration tests cover idempotency and transaction integrity; the full test run is pending.

## Formula check
The service formula is max(0, lead-time demand + safety stock − usable stock − eligible incoming), then minimum quantity and upward multiple rounding, with maximum-stock conflict detection. Safety stock is historical mean daily demand times configured days. The same helper powers the API route. A live API-versus-manual comparison for ten pairs is not complete because the running server process returns HTTP 500 for historical data and has no current-source freshness window.
