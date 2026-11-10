# Project Summary

SiteStock is an offline-first construction-material inventory, sales, forecasting and replenishment application. Its single bundled source, the **Construction Materials Dehradun Dataset**, has 8,940 rows across 60 site/material series (149 weekly rows each). It contains 6,300 self-created rows and a deterministic generated extension of 2,640 rows. The dataset is not real observed demand.

The active file is `data/construction_materials_dehradun_dataset.csv`; source files and the prior generator are archived under `data/archive/pre_merge/`. The `data_origin` column preserves provenance. The final 30 rows per series are generated, so all 1,800 rows in the 30-week holdout are generated and model scores are diagnostics only.

Historical observations are kept separate from operational inventory, sales and purchase records. CSV stock values do not initialize the live ledger, and CSV prices are not acquisition costs. See [`DATASET_CARD.md`](DATASET_CARD.md), [`DATASET_AUDIT.md`](DATASET_AUDIT.md), and [`MODEL_RESULTS.md`](MODEL_RESULTS.md).
