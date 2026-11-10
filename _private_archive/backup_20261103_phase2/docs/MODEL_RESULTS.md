# Model Evaluation Results

## Protocol

Target: aggregated weekly consumption quantity for one site/material series, in that material's unit.
Each candidate uses the same chronological training and final 20% test window for each series. Model choice uses three expanding-window rolling-origin folds strictly before the final holdout. Feature rows use lag 1–4 and trailing four-period mean and standard deviation from prior observations only. The final model fit used for future forecasts is separate from the fit used to score the holdout.
Metrics are macro-averages across 60 series. MAE and RMSE retain each series' own unit; WAPE is computed per series before averaging. They are not a pooled physical-unit error.

## Overall holdout metrics

| Model | MAE mean | RMSE mean | WAPE mean |
|---|---:|---:|---:|
| Naive | 65.219 | 73.825 | 30.282% |
| Seasonal Naive | 305.374 | 441.371 | 87.732% |
| Multiple Linear Regression | 182.116 | 205.218 | 106.356% |
| Random Forest | 104.968 | 116.344 | 63.066% |
| XGBoost | 80.536 | 93.348 | 47.128% |

## Validated choice per series

Selection used pre-holdout rolling MAE; a learned model was kept only when it beat Naive on that score. Naive fallback was selected for 39 of 60 pairs. Choice counts: Multiple Linear Regression: 2, Naive: 39, Random Forest: 6, XGBoost: 13.
Holdout MAE of the per-series choice averaged 65.733. This result describes this fixed dataset and split only.

## Worst and best selected holdout changes versus Naive

- Largest selected-model MAE increase: Paltan Bazaar, Dehradun / Bricks, XGBoost MAE 422.811 versus Naive 337.469 (increase 85.342).
- Largest selected-model MAE reduction: Jakhan, Dehradun / AAC Blocks, XGBoost MAE 113.828 versus Naive 149.048 (reduction 35.220).

## Feature importance and interval

The API exposes Random Forest feature importance per evaluated series for lag 1–4, rolling mean, and rolling standard deviation. Importance is model-specific association, not causal evidence. The 90% forecast interval uses the 90th percentile of absolute errors on pre-holdout rolling-origin predictions; the final holdout does not set interval width. Future coverage is not guaranteed.

## Per-series evidence

docs/model_metrics.json stores per-series/model MAE, RMSE, WAPE, rolling selection MAE, train/test dates, observation counts, and evaluation failures. The current metric run completed 60/60 pairs with no failures.

Inventory-policy costs are not reported: the dataset has no carrying-cost rate or shortage penalty, and choosing these values would introduce unsupported assumptions.
