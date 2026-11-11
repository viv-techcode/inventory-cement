# Model Evaluation Results

## Protocol

Target: weekly consumption quantity for each site/material series, in that material's unit. Each candidate uses the same chronological split: 119 training observations and 30 final holdout observations per complete 149-row series. Selection uses three expanding-window rolling-origin folds that end before the final holdout. Lag 1–4 and rolling four-period mean/standard deviation use prior observations only. MAE/RMSE are macro-averages of per-series scores; WAPE and MASE are also averaged by series and are not pooled across different physical units.

The model-selection rule retains a learned model only when it beats Naive on pre-holdout rolling-origin MAE. The final holdout is used only for diagnostics. The 90% interval radius comes from the 90th percentile of rolling-origin absolute errors; holdout coverage is reported afterward and does not calibrate the radius.

Dataset hash: `4b60db1190bce14bbe057c7772fcb00a7024365f18e623e2d406018fd90faee4`  
Model version: `1.4`  
Training command: `python -m scripts.train_all` (about 222 seconds in this run; 60/60 pairs, 300 model artifacts, zero issues).

## Mean holdout metrics across 60 series

| Model | MAE | RMSE | WAPE | MASE |
|---|---:|---:|---:|---:|
| Naive | 65.219 | 73.825 | 30.282% | 0.148 |
| Seasonal Naive | 305.374 | 441.371 | 87.732% | 0.312 |
| Multiple Linear Regression | 182.116 | 205.218 | 106.356% | 0.342 |
| Random Forest | 104.968 | 116.344 | 63.066% | 0.179 |
| XGBoost | 80.536 | 93.348 | 47.128% | 0.166 |

The selected model per series was Naive for 39 pairs, XGBoost for 13, Random Forest for 6, and Multiple Linear Regression for 2. The selected models' mean holdout scores were MAE 65.733, RMSE 74.040, WAPE 34.046%, and MASE 0.150. The average per-series empirical coverage of their nominal 90% intervals was 94.94%. Coverage varies by series and does not guarantee future coverage.

## Interval coverage by selected model

| Selected model | Selected series | Mean observed holdout coverage |
|---|---:|---:|
| Naive | 39 | 93.42% |
| XGBoost | 13 | 97.69% |
| Random Forest | 6 | 97.22% |
| Multiple Linear Regression | 2 | 100.00% |

## Limitations and artifacts

The input series are synthetic, and macro MAE values still combine different units through averaging. Large errors in bricks, AAC blocks, or tiles are numerically larger because those series are measured in pieces or square metres; they should not be compared as if they were one pooled material quantity. The repeated demand patterns make the Naive baseline strong in this fixed sample. No external validation period is available.

`docs/model_metrics.json` contains per-series/per-model MAE, RMSE, WAPE, MASE, rolling selection MAE, training/test dates, interval radius, error sigma, and selected-model holdout coverage. Refresh interval metadata without refitting via `python -m scripts.train_all --metrics-only`. Model files are retained under `artifacts/models`; archived unreferenced files are outside the submission bundle.

See `docs/policy_simulation_summary.json` and `docs/policy_simulation.csv` for the separate retrospective replenishment-policy experiment and its cost sensitivities.
