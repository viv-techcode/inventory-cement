# Additive schema migration 003

**Schema version:** 2 → 3  
**Purpose:** retain row-level provenance on historical observations and operational records.  
**Status:** implemented and applied idempotently to `data/inventory.db`.

## Changes

Adds a non-null `source_tag` field to the existing `historical_observations`, `inventory_transactions`, `customers`, `sales_records`, and `reorder_rules` tables. There are no table drops, row rewrites, key changes, or inferred values.

- Existing observations receive the conservative default `historical_csv`.
- Existing operational rows receive the default `operator`.
- New bundled-source observations use `historical_csv`; generated extension observations use `sample_extension`.
- The explicitly seeded ledger, customers, sales and reorder rules use `sample_ledger`.
- Other application-created operational records continue to default to `operator` unless the service caller supplies another valid tag.

Schema v2's nullable `inventory_transactions.unit_cost_inr` column remains nullable; no transaction cost is inferred from any observation or reference price. The prior v2 migration behavior is documented in [`MIGRATION_002.md`](MIGRATION_002.md).

## Migration behavior and verification

`Base.metadata.create_all()` creates only absent tables. `_apply_additive_migrations()` inspects each existing table and issues `ALTER TABLE ... ADD COLUMN source_tag ... DEFAULT ...` only when the column is absent. Repeated initialization is safe. The version advances to 3 only after the additive step.

`tests/test_database_migrations.py` simulates a pre-v3 database missing the cost and tag columns, initializes it twice, and verifies all new columns, the `operator` legacy default, preserved legacy transaction fields and schema version 3. The retained database migration preserved all pre-existing rows, including 6,300 observations, the original import, 300 old forecast artifacts, catalogue/settings, and all legacy tables.
