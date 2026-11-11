# Additive schema migration 002

**Schema version:** 1 → 2  
**Purpose:** support recorded operational inventory costs, customer sales, and per-site/material reorder rules.  
**Status:** implemented in `inventory_app/database.py` and applied idempotently at API startup.

## Changes

1. `inventory_transactions.unit_cost_inr NUMERIC(18,4) NULL` is added when an existing ledger table does not already have the column. It records an operator-supplied cost per material unit for stock entering the ledger. A sale movement may also store the FIFO-derived outgoing unit cost when fully known. The field is nullable by design.
2. `customers` is a new optional customer directory.
3. `sales_records` is a new table for idempotent sales, revenue, optional recorded FIFO cost of goods sold and gross margin. Each row references one stock-consuming `inventory_transactions` row.
4. `reorder_rules` is a new table with a unique `(site_id, material_id)` pair and reorder point, lead-time/safety-stock overrides, optional order constraints, activation, and notes.
5. Forecast artifact model version is 1.2. Source label is part of the series hash, so a Historical CSV assessment cannot be silently reused as an Operational sales assessment. Older artifact/database records are retained but are no longer treated as compatible.

## Migration behavior

- `Base.metadata.create_all()` creates only absent tables.
- `_apply_additive_migrations()` inspects `inventory_transactions` and runs `ALTER TABLE ... ADD COLUMN unit_cost_inr` only if needed.
- The migration is safe to run repeatedly. The schema version advances to 2 only after the additive step.
- Existing transaction rows are preserved and receive `NULL` for the new cost column. No historical unit price or catalogue benchmark is copied into the ledger.
- Existing historical observations, import runs, rejected rows, site/material IDs, settings, forecast metadata, and legacy-compatible supplier/purchase-order data are not deleted or reset.
- No CSV observation is converted to an inventory transaction or sale.

## Validation

`tests/test_database_migrations.py` simulates a v1 database by removing the nullable cost column from a test database, sets schema version 1, runs initialization twice, and checks that the column exists, the version is 2, and the pre-existing transaction row and unknown-cost status remain intact. The project database is also exercised at startup; it retained all 6,300 historical observations and had zero operational transactions/sales before use.
