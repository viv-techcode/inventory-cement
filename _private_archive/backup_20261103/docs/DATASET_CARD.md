# Construction Materials Dehradun Dataset

## Purpose

This dataset supports development and demonstration of construction-material inventory, data-quality, and forecasting workflows for six Dehradun project sites.

## How it was made

The active file is `data/construction_materials_dehradun_dataset.csv` (SHA-256 `7ef197afc1cb5e5bf64e1910351c9d38050014972663e158e157ae36011d2360`). It combines 6,300 self-created rows with a deterministic generated extension of 2,640 rows. The original CSV, extension CSV, and extension generator are archived under `data/archive/pre_merge/`; `MANIFEST.txt` records their row counts and SHA-256 hashes. Rebuild with `python -m scripts.merge_dataset`.

This is self-created and partly generated data. It is not real observed demand, transactions, or supplier history.

## Coverage

- 8,940 total rows: 6,300 `original_self_created`; 2,640 `generated_extension`
- 6 sites × 10 materials = 60 site/material series; 149 weekly observations per series
- Calendar dates: 2024-01-01 to 2026-11-02
- The last 30 observations of every series are generated; the 30-week holdout is 1,800 generated rows out of 1,800 (100%).

## Columns and units

| Column | Meaning / unit |
|---|---|
| `date` | Observation timestamp |
| `project_site_id` | Site identifier |
| `city`, `state` | Site location |
| `project_type`, `project_phase` | Project classification |
| `material` | Construction material |
| `unit` | Quantity unit for the material |
| `consumption_qty` | Consumed quantity in `unit` |
| `opening_stock_qty` | Opening quantity in `unit` |
| `incoming_qty` | Incoming quantity in `unit` |
| `unit_price_inr` | INR per `unit` |
| `supplier_lead_time_days` | Lead time in days; supplier identity is not supplied |
| `wpi_reference_month` | `YYYY-MM` month key; no WPI index value is supplied |
| `data_origin` | `original_self_created` or `generated_extension`; optional for older-format imports |

Material units: AAC Blocks/pieces; Binding Wire/kg; Bricks/pieces; Cement/50-kg bags; Coarse Aggregate/m3; PVC Pipes/pieces; Ready-Mix Concrete/m3; River Sand/m3; TMT Steel/kg; Tiles/m2.

## Known limitations

The extension is deterministic and not evidence of real demand. Original timestamps include varying clock times, although calendar dates are weekly. The extension begins one calendar week after the original cutoff and its distribution can differ from the earlier data. Supplier identities, verified price provenance, reorder thresholds, and external weather/project records are absent. The existing forecast evaluation does not establish reliable real-world performance.

See [`DATASET_AUDIT.md`](DATASET_AUDIT.md) for detailed methods and findings.
