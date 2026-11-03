# Dataset Quality Audit

## Scope and method

Audited `data/construction_materials_dehradun_dataset.csv` with the dataset builder and pandas checks. Natural key: `(project_site_id, material, date)`. Stock flow was checked as `closing = opening_stock_qty + incoming_qty − consumption_qty`; adjacent observations compare current opening stock with the prior calculated close. Consumption outliers use Tukey's 1.5×IQR within each site/material series. Price changes were limited to `unit_price_inr`; source measurements and all stock-flow quantities were compared with the pre-repricing backup.

## Results

| Check | Result |
|---|---|
| Rows and columns | 8,940 rows × 16 columns |
| Sites, materials, series | 6 sites, 10 materials, 60 series |
| Rows per series | 149 for each series |
| Timestamp range | 2024-01-01 through 2026-11-02 |
| Missing values | 0 across all 16 columns |
| Exact duplicate rows / natural keys | 0 / 0 |
| Calendar cadence | 7 days within every series |
| Numeric validity | No nonnumeric/missing numeric values, negative quantities, or nonpositive prices/lead times |
| Calculated closing stock | No negative closing balances |
| Adjacent stock-chain checks | 0 mismatches over 8,880 comparisons, tolerance 1e-6 |
| Material-unit consistency | One unit per material across sites |
| Consumption IQR flags | 250 across 60 series; retained unchanged |
| Price plausibility | All prices within documented material bounds |
| Demand / price levels | Past-only expanding thresholds; ties classified Medium |
| Source hash | `4b60db1190bce14bbe057c7772fcb00a7024365f18e623e2d406018fd90faee4` |

### Rebased price range by material

Ranges are observed across all dates and sites after rebasing; they are not verified purchase invoices.

| Material | Minimum (INR / dataset unit) | Maximum (INR / dataset unit) |
|---|---:|---:|
| AAC Block | 75.0946 | 88.1361 |
| Binding Wire | 57.2076 | 64.7062 |
| Bricks | 8.2659 | 9.6354 |
| Cement OPC 43 | 383.2649 | 471.3244 |
| Coarse Aggregate | 1,757.2063 | 2,080.2526 |
| PVC SWR Pipe | 956.6420 | 1,060.6537 |
| Ready Mix Concrete M20 | 4,750.5206 | 5,614.0789 |
| River Sand | 3,611.9629 | 4,286.6182 |
| TMT Bar 12mm Fe500D | 58.0601 | 69.5414 |
| Vitrified Tiles | 857.1127 | 947.7570 |

## Interpretation

IQR flags identify values for review, not errors. No external evidence justifies changing the measured quantities. Historical price rows are synthetic rebased reference estimates using the dated sources and conversions documented in `docs/PRICE_SOURCES.md`; they are not quotes or transaction prices. `wpi_reference_month` is a month key only. Supplier identities and confirmed procurement lead times are not present.

Rebuild and audit with `python -m scripts.build_dataset`. The builder validates schema, row count, duplicate keys, numeric/range checks, levels, and the complete stock-flow chain.
