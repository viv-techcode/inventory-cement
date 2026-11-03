# Data Card: Construction Materials Dehradun Dataset

## Purpose
A fixed teaching and software-demonstration dataset for inventory workflows and weekly demand forecasting across six Dehradun project-site identifiers.

## Construction
This dataset is self-created and simulated from stated demand assumptions and indicative published 2026 Dehradun price anchors; it is not real recorded site data.

It contains 8,940 weekly records organized as 60 site/material series, with 149 records per series. Demand assumptions use a bounded month-of-year seasonal factor (0.75–1.25 of each series median), a small deterministic trend capped at 0.15% per week, and deterministic demand variation bounded to ±4%. Prices are rebased by the reproducible method in PRICE_SOURCES.md: category drift, a small seasonal factor, and fixed-seed noise are normalized to a November 2026 Dehradun indicative anchor. Supplier lead times are positive whole-day scenario values. Receipts follow a stock-cover rule based on lead time and target cover. Construction phases change on a 26-week schedule. Demand and price levels use past-only expanding thresholds as defined in INVENTORY_LOGIC.md.

## Coverage
- File: data/construction_materials_dehradun_dataset.csv
- Rows: 8,940; series: 60 (6 sites × 10 materials); 149 rows per series
- Timestamp range: 2024-01-01 to 2026-11-02; calendar observations advance weekly
- SHA-256: 4b60db1190bce14bbe057c7772fcb00a7024365f18e623e2d406018fd90faee4
- Rebuild, reprice, derive labels, and validate with: `python -m scripts.build_dataset`

## Columns, types, and units
| Column | Type | Meaning / unit |
|---|---|---|
| date | timestamp | Weekly observation timestamp |
| project_site_id | string | Scenario site identifier |
| city | string | City |
| state | string | State |
| project_type | string | Project classification |
| project_phase | string | Construction phase |
| material | string | Material name |
| unit | string | Quantity unit used for this material |
| consumption_qty | decimal | Consumed quantity in unit |
| opening_stock_qty | decimal | Opening quantity in unit |
| incoming_qty | decimal | Receipt quantity in unit |
| unit_price_inr | decimal | INR per dataset unit |
| demand_level | category | Expanding past-only demand band: Low / Medium / High |
| price_level | category | Expanding past-only price band: Low / Medium / High |
| supplier_lead_time_days | integer | Scenario lead time in days |
| wpi_reference_month | YYYY-MM string | Month key; no index value is provided |

Material units: AAC Blocks/pieces; Binding Wire/kg; Bricks/pieces; Cement/50-kg bags; Coarse Aggregate/m³; PVC Pipes/pieces; Ready-Mix Concrete/m³; River Sand/m³; TMT Steel/kg; Tiles/m². Product mappings and conversions are documented in PRICE_SOURCES.md.

## Limitations
The 60 series are short and scenario-based. Indicative prices and supplier lead times do not identify confirmed suppliers or procurement terms. Bulk density, unspecified product grades, and pack-size conversions are assumptions. The month key does not contain an external price index. There are no weather, festival, project-progress, or verified procurement records. Forecast scores on this file do not establish field performance. See DATASET_AUDIT.md and the report limitations.
