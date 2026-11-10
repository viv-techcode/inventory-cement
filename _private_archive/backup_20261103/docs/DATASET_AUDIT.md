# Dataset Audit

Audit basis: read-only pandas inspection of the two active CSVs on 2026-11-03. The source rows are self-created Dehradun construction-materials data, not independently observed demand. The extension is deterministic generated data. No source values were changed during this audit.

## Discovery map

| File | Role |
|---|---|
| `data/archive/pre_merge/Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv` | Original 6,300-row, 14-column self-created source. SHA-256 `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`. |
| `data/archive/pre_merge/Dehradun_Inventory_Dataset_Sample_Extension.csv` | 2,640-row generated extension, same 14 fields plus `source_tag`. SHA-256 `e9c25f5b7d9538b6d47bc3297c76886884cce686b4a614492daa20f9c5347d3a`. |
| `data/archive/pre_merge/extend_dataset.py` | Archived deterministic extension generator; SHA-256 `05cd4c3f3b333720f0cfef99b9e5fe29002267b2b27260cb0d04e88db0354474`; no longer active. |
| `data/archive/pre_merge/uploads_original_copy.csv` | Redundant archived copy formerly in uploads; 6,300 rows, SHA-256 `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`, verified identical to the original CSV. |
| `scripts/load_operations.py` | Optional sample operational ledger loader; consumes extension rows for synthetic receipts/sales. |
| `inventory_app/config.py` | Active CSV paths. |
| `inventory_app/ingestion.py` | Required schema, row validation, idempotent DB import. |
| `inventory_app/data_quality.py` | Derived data quality and stock-flow diagnostics. |
| `api/main.py` | Startup auto-import. |
| `tests/test_dataset_source_integrity.py`, `tests/test_sample_data_pipeline.py`, `tests/test_ingestion_quality.py` | Source integrity, extension pipeline and ingestion coverage. |
| `README.md`, `docs/*`, `frontend/app.js` | Dataset descriptions, metrics and UI labels. |

Original CSV: 6,300 rows × 14 columns. Extension CSV: 2,640 × 15. `pandas.read_csv` inferred `date` and the site/city/state/type/phase/material/unit/WPI month fields as object/string; consumption/opening/incoming/price as float64; lead time as int64. Extension adds string `source_tag`. Combined: 8,940 rows, 15 columns after the `data_origin` merge field is added.

## Findings

| Finding | Observed result | Severity | Proposed fix |
|---|---|---|---|
| Schema and units | Required fields are date, site, city, state, project type/phase, material, unit, consumption, opening stock, incoming, unit price, supplier lead days, and WPI reference month. All 14 source fields are populated. Units: AAC Blocks/pieces; Binding Wire/kg; Bricks/pieces; Cement/50-kg bags; Coarse Aggregate/m3; PVC Pipes/pieces; Ready-Mix Concrete/m3; River Sand/m3; TMT Steel/kg; Tiles/m2. `wpi_reference_month` is a month key, not an index value. | Nice to have | Keep units explicit in the data card; source a true index series and supplier/site identifiers in a future version if needed. |
| Required vs optional | Existing 14 fields remain required to keep ingestion semantics. New `data_origin` is optional for old-format imports. | Should fix | Make the merged-file origin explicit while retaining old import compatibility. |
| Coverage | 6 sites × 10 materials = 60 series, each 149 rows. Date span is 2024-01-01 to 2026-11-02. There are zero duplicate `(site, material, date)` keys. By calendar date each series advances weekly. Raw timestamps have varying time-of-day, yielding 6- or 7-day timestamp deltas (3,136 and 5,744 intervals); normalized calendar-date deltas are 7 days. | Should fix | Preserve source values; audit calendar dates, and document timestamp-time variation because rewriting timestamps would change source values. |
| Missing/invalid values | Zero missing values in the 14 shared fields; `source_tag` is absent only on all 6,300 original rows. Zero negative or zero consumption values; zero price ≤ 0; zero lead time ≤ 0; zero negative calculated closing balances. | Nice to have | Keep the optional origin field separate from source validity and report its counts. |
| Consumption outliers | Per-series Tukey 1.5×IQR scan flags 250 consumption values over 60 series. These are not automatically errors; no values were changed. | Should fix | Review against source provenance before correction; retain values absent evidence of error. |
| Stock chain | For every row, calculated closing is opening + incoming − consumption. All 8,880 adjacent-series comparisons match the following opening within 1e-6 (floating representation maximum residual ≈ 7.3e-12); all closing values are nonnegative. | Nice to have | Keep the chain assertion in the deterministic merge audit. |
| Original/extension boundary | Calendar series continue from 2025-12-29 to 2026-01-05, with no missing weekly date. Across the 60 series, the unweighted average per-series consumption mean is 676.92 original versus 239.09 generated; average per-series standard deviation is 490.91 versus 46.19; average per-series price mean is INR 961.61 versus INR 1,048.64. Per-series generated/original consumption-mean ratios range 0.125–3.183. Example Clement Town/AAC means and std change from 675.93/561.00 to 375.40/80.07 and mean price from INR 66.50 to INR 72.86. The generated file is not evidence of observed continuity. | Should fix | Preserve both provenance classes and call out the generated boundary in all model interpretations. Do not smooth the values. |
| Holdout composition | Last 30 observations in every 149-row series are generated: 1,800/1,800 holdout rows (100%). | Blocker | Show the exact generated holdout count and label scores as generated-data diagnostics. |
| Realism / learnable signal | Mean consumption in Jul–Sep is 479.44 versus 572.65 outside those months (about 16.3% lower), a descriptive pattern that does not prove a monsoon cause. Unadjusted project-phase means are Foundation 364.81, Structure 751.16, Finishing 914.73, and MEP 193.88; phase explains 4.15% of raw consumption variance, but material/site scale and synchronized/cyclic phase labels confound this association. Price correlation with date ordinal is 0.024 overall, so there is no clear aggregate price drift. Existing results report negative median R² for all model families and choose Naive for 39/60 production pairs. The data has some descriptive patterns, but no evidence of reliable learnable signal beyond naive last-value for real demand. | Should fix | Avoid a claim of useful signal; retain a naive benchmark and evaluate on independently observed future data. Step 6 proposal below. |
| Missing operational fields | The source has no supplier identity, site-specific supplier assignment, reorder/minimum/maximum stock levels, actual purchase/receipt evidence, or provenance for observed prices. It does include lead time, unit price, and opening stock per site/material/week. | Should fix | Obtain verified vendor and policy data before using the series for purchasing decisions; do not infer these fields from generated rows. |

## Step 4 merge change log

No source measurements were repaired or altered. The merge adds one provenance field: 6,300 original rows receive `data_origin=original_self_created`; 2,640 extension rows receive `data_origin=generated_extension`. Extension `source_tag` is not carried as a measurement column. Output is sorted by site, material, date while retaining the original 14-column order and appending `data_origin`. Rows touched: 8,940 (origin annotation only); before/after measurement values are identical to archived inputs. Merged file SHA-256: `7ef197afc1cb5e5bf64e1910351c9d38050014972663e158e157ae36011d2360`.

## Future work: v2 synthetic generator

If a synthetic dataset is needed for development, design a separately versioned, seeded and deterministic generator with explicit parameter documentation: material-specific monsoon seasonality, phase-driven demand profiles, bounded price drift informed by a documented external index assumption, and a longer history. Keep generated values tagged and evaluate separately from self-created rows. Do not present synthetic patterns as observed demand. This is future work and is not implemented here.
