# Project Status

The active bundled data source is the **Construction Materials Dehradun Dataset**, stored in `data/construction_materials_dehradun_dataset.csv`.

- 8,940 rows: 6,300 self-created and 2,640 generated
- 60 site/material series with 149 weekly rows each, through 2026-11-02
- `data_origin` distinguishes source rows; all 1,800 rows in the final 30-week holdout are generated
- The archive and deterministic rebuild script are documented in [`DATASET_AUDIT.md`](DATASET_AUDIT.md)
- The data is not real observed demand; current forecast results are diagnostics, not validated real-world accuracy

The application maintains separation between historical dataset observations and the operational stock/sales/purchasing ledger. The active loader, API auto-import, tests, and documentation point to the one merged CSV. `data/archive/pre_merge/extend_dataset.py` is archived and no longer participates in normal loading.

Historical implementation and QA snapshots may describe earlier application behavior; current dataset details are in [`DATASET_CARD.md`](DATASET_CARD.md), [`DATA_PROFILE.md`](DATA_PROFILE.md), and [`DATA_CHECK.md`](DATA_CHECK.md).
