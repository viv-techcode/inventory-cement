# Construction Materials Dehradun Dataset — Profile

The active dataset is `data/construction_materials_dehradun_dataset.csv`, containing 8,940 rows: 6,300 self-created rows plus 2,640 deterministic generated rows. It is not real observed demand. See [`DATASET_CARD.md`](DATASET_CARD.md) for the column descriptions and [`DATASET_AUDIT.md`](DATASET_AUDIT.md) for the quality audit.

- 6 sites × 10 materials = 60 site/material series
- 149 weekly observations per series
- Calendar coverage: 2024-01-01 through 2026-11-02
- `data_origin`: 6,300 `original_self_created`; 2,640 `generated_extension`
- All 1,800 rows in the final 30-week-per-series holdout are generated (100%).
- All 14 original source fields are retained in order, with `data_origin` appended.

This document now describes the unified active file. The two source CSVs and the extension generator are preserved in `data/archive/pre_merge/` with hash evidence in `MANIFEST.txt`.
