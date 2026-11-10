# Database and dataset reconciliation

Checked 2026-11-03 after the dataset metadata migration. The active source is the single `data/construction_materials_dehradun_dataset.csv` file. The SQLite database contains 8,940 historical observations across 60 site/material series: 6,300 tagged `original_self_created` and 2,640 tagged `generated_extension`.

| Table | Rows |
|---|---:|
| historical_observations | 8,940 |
| import_runs | 2 legacy runs plus 1 merged-file reconciliation run |
| sales_records | 2,640 |
| inventory_transactions | 3,330 |
| reorder_rules | 60 |
| customers | 30 |
| suppliers | 0 |
| purchase_orders | 0 |
| receipt_records | 0 |
| rejected_rows | 0 |

Operational ledger snapshots before and after metadata migration matched exactly: sales_records 2,640 rows, inventory_transactions 3,330 rows, suppliers 0, purchase_orders 0. No receipt_records table exists in this schema. Database backup integrity check returned `ok` at `data/inventory.backup.db`.

The merged file has 8,940 rows, 60 pairs, and zero duplicate `(project_site_id, material, date)` keys. Archived input fingerprints and full audit results are in [`DATASET_AUDIT.md`](DATASET_AUDIT.md) and `data/archive/pre_merge/MANIFEST.txt`. The dataset is self-created and partly generated, not real observed demand.
