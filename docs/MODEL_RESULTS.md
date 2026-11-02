# All-Series Forecast Results — Extended Observation Set

Updated 2026-11-02 (Asia/Kolkata). These results describe model behavior on the imported observation table, not verified future demand.

## Data scope and provenance

The retained original CSV is unchanged (SHA-256 `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`): 6,300 rows through 2025-12-29. A separate deterministic extension contributes 2,640 rows (`source_tag=sample_extension`), 44 weekly observations for each of the same 60 site/material pairs, dated 2026-01-05 through 2026-11-02. The database now contains 8,940 observations, 149 per pair, with historical and extension tags retained separately.

Forecast training uses the observation table (the API source label remains **Historical CSV**). Operational sample sales are not training observations and are excluded from operational-sales forecast eligibility by `source_tag=sample_ledger`. The extension's later rows are generated data; metrics involving its holdout are diagnostics of that generation, not evidence of real-world accuracy or demand.

## Method and run

Each pair is evaluated independently in its recorded unit. The chronological fixed-origin holdout uses 119 earlier weekly observations for training and the final 30 for scoring; across pairs, the evaluation window is 2026-04-13 through 2026-11-02. No random split or future-test feedback is used. Features remain past-only (lags 1–4 and trailing four-period statistics). Five models were run for each series: Naive, Seasonal Naive, Multiple Linear Regression, Random Forest and XGBoost.

Training completed for **60/60 pairs**, with **300 new model artifacts** and **0 issues** in **129.63 seconds**. The previous 300 artifacts were preserved; the database now has 600 artifacts in total across the old and extended observation hashes.

## Pair-level summary

The best model is the lowest chronological-holdout MAE for each pair. WAPE and R² are medians of the per-pair metrics; quantities are not pooled across units.

| Model | Best-model wins / 60 | Median WAPE | Median R² |
|---|---:|---:|---:|
| Naive | 21 | 29.83% | −2.014 |
| Random Forest | 20 | 25.90% | −1.566 |
| XGBoost | 17 | 29.11% | −1.944 |
| Seasonal Naive | 1 | 49.20% | −11.793 |
| Multiple Linear Regression | 1 | 76.00% | −19.586 |

Median R² is negative for every model. The holdout includes generated extension rows, so these values are strictly retrospective diagnostics on the chosen sample series. They must not be presented as measured accuracy on actual post-2025-12-29 demand.

## How to read these scores

WAPE is the headline error; lower is better. R² is judged against predicting the holdout average: 0 means no improvement over that baseline, positive is better, and negative is worse. The app labels the best model by the lowest holdout MAE, while surfacing that model and its WAPE above the comparison table.

## Limits

- The extension is clearly tagged but constructed, not source-backed. The original CSV and its 2025-12-29 cutoff remain intact.
- Operational sample costs are synthetic recorded values at 82–93% of the corresponding extension-week unit price. Sample sales are reportable but cannot qualify as real operational-sales forecast history.
- Data is scoped by site/material and unit; no cross-material aggregation is performed.
- Missing calendar periods remain missing, not zero. The seven-day Asia/Kolkata freshness gate and 90-day weekly horizon guard remain active for replenishment.
- Old and new model artifacts coexist; no prior model artifact was deleted.
