# Migration 004 — Unified dataset provenance

Schema version 4 performs idempotent metadata updates only:

- `historical_observations.source_tag`: `historical_csv` → `original_self_created`; `sample_extension` → `generated_extension`.
- `import_runs.file_name` and `source_kind` for the two bundled dataset imports are renamed to the unified dataset file and source label.
- Operational tables (`sales_records`, `inventory_transactions`, `suppliers`, `purchase_orders`, and receipt data) are not updated.

The migration was applied after creating `data/inventory.backup.db`; its integrity check returned `ok`. The sales, inventory-transaction, supplier, and purchase-order row snapshots matched before and after migration.
