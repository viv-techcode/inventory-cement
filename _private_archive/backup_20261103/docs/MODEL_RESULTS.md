# Forecast model results

Updated 2026-11-02. Results describe retrospective model behavior on the Construction Materials Dehradun Dataset (6,300 self-created rows plus 2,640 generated rows). Generated rows are not real observed data. The final holdout is composed of generated rows, so the scores are diagnostics of the synthetic series rather than measured accuracy on future real demand.

## Evaluation method

Production forecasting fits per-series Naive, Seasonal Naive, MLR, Random Forest, and XGBoost models. Rolling-origin MAE selects the model, with Naive fallback when no eligible candidate beats it. The pooled model is implemented and evaluated as an experiment only in `inventory_app/pooled_forecasting.py`, `scripts/train_pooled.py`, and `docs/pooled_results.json`; it is not used by the API or replenishment. The pooled experiment is evaluated separately below; holdout results are not used for tuning. Weekly series have 149 periods. Three expanding-window rolling-origin folds inside the earlier 119 periods are used for model selection: 10 periods per fold at origins 65, 75, and 85. Each fold fits on its past only, and its prediction context is recursive. Lag and trailing rolling features use only observations before each prediction. No random split is used.

The sole selection metric is mean absolute error (MAE) averaged across the three pre-holdout folds. If no ML model beats Naive on this score, the series selects Naive. Holdout metrics below are computed separately and do not select or tune a model. MAE and RMSE retain each series' physical unit; averages across differently scaled units are shown only as macro-averages of per-series scores, not pooled quantities.

## Before vs. after

The before values use the previous fixed-origin selection. The after values use the rolling-origin MAE selection. The fitted per-series estimators and untouched holdout are unchanged, so holdout diagnostics are numerically identical; what changed is the selection protocol and the selected-model distribution.

| Model | Before median MAE | After median MAE | Before median RMSE | After median RMSE | Before median R² | After median R² | Before median WAPE | After median WAPE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Naive | 27.050 | 27.050 | 34.080 | 34.080 | −2.014 | −2.014 | 29.835% | 29.835% |
| Seasonal Naive | 58.685 | 58.685 | 73.362 | 73.362 | −11.793 | −11.793 | 49.203% | 49.203% |
| Multiple Linear Regression | 46.865 | 46.865 | 55.783 | 55.783 | −19.586 | −19.586 | 75.999% | 75.999% |
| Random Forest | 28.219 | 28.219 | 31.078 | 31.078 | −1.566 | −1.566 | 25.898% | 25.898% |
| XGBoost | 27.146 | 27.146 | 32.125 | 32.125 | −1.944 | −1.944 | 29.110% | 29.110% |

The table below reports macro-mean and median across the 60 per-series holdout metrics, along with the same summary statistics for the rolling-origin selection MAE.

| Model | Mean holdout MAE | Median holdout MAE | Mean RMSE | Median RMSE | Mean R² | Median R² | Mean WAPE | Median WAPE | Mean rolling MAE | Median rolling MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Naive | 65.219 | 27.050 | 73.825 | 34.080 | −2.221 | −2.014 | 30.282% | 29.835% | 209.393 | 35.933 |
| Seasonal Naive | 305.374 | 58.685 | 441.371 | 73.362 | −81.806 | −11.793 | 87.732% | 49.203% | 852.006 | 114.079 |
| Multiple Linear Regression | 182.116 | 46.865 | 205.218 | 55.783 | −52.476 | −19.586 | 106.356% | 75.999% | 294.837 | 43.792 |
| Random Forest | 104.968 | 28.219 | 116.345 | 31.078 | −32.767 | −1.566 | 63.062% | 25.898% | 275.719 | 39.056 |
| XGBoost | 80.536 | 27.146 | 93.348 | 32.125 | −12.143 | −1.944 | 47.128% | 29.110% | 267.577 | 45.555 |

MAE/RMSE averages and medians are numeric macro-averages across 60 unit-specific series, not a physically pooled score. The before run's pair winners were Naive 21, Random Forest 20, XGBoost 17, Seasonal Naive 1, and MLR 1. After rolling-origin selection the winners are Naive 39, XGBoost 13, Random Forest 6, MLR 2, and Seasonal Naive 0. ML beats Naive in 21 of 60 series by the selection score; the remaining 39 use Naive.

## Pooled-model before/after results

The pooled evaluator uses the same three expanding-window folds and final untouched 20% chronological holdout as the per-series evaluator. Transform selection and pooled-versus-Naive fallback use backtest MAE only. MAE, RMSE, R² and WAPE below are holdout diagnostics summarized by mean and median across series. The data is a Construction Materials Dehradun Dataset (6,300 self-created rows plus 2,640 generated rows), not real observed demand; holdout scores include generated periods.

<!-- BEGIN GENERATED POOLED RESULTS -->
Pooled transform selection uses macro-mean per-series backtest MAE across the three expanding folds. Each series then uses its best pooled model only when that model's backtest MAE is strictly lower than Naive; otherwise the result falls back to Naive. Final holdout metrics below are diagnostics only.

**Selection outcome:** Pooled models do not beat Naive in most series: a pooled model was selected for 30/60; the rest fall back to Naive.

### Overall before/after holdout metrics

Mean and median are calculated across the per-series holdout metrics; MAE and RMSE remain in each series' unit.

| Scenario | Metric | Mean | Median |
|---|---|---:|---:|
| Before · Naive | MAE | 65.219 | 27.050 |
| Before · Naive | RMSE | 73.825 | 34.080 |
| Before · Naive | R2 | -2.221 | -2.014 |
| Before · Naive | WAPE | 30.282% | 29.835% |
| After · pooled or Naive fallback | MAE | 85.556 | 20.579 |
| After · pooled or Naive fallback | RMSE | 100.986 | 22.897 |
| After · pooled or Naive fallback | R2 | -4.798 | -1.844 |
| After · pooled or Naive fallback | WAPE | 33.828% | 29.028% |

### Before/after holdout metrics by material

| Material | Scenario | Metric | Mean | Median |
|---|---|---|---:|---:|
| AAC Blocks | Before · Naive | MAE | 123.293 | 127.844 |
| AAC Blocks | Before · Naive | RMSE | 143.149 | 146.923 |
| AAC Blocks | Before · Naive | R2 | -2.683 | -2.751 |
| AAC Blocks | Before · Naive | WAPE | 31.241% | 31.602% |
| AAC Blocks | After · pooled or Naive fallback | MAE | 176.421 | 127.844 |
| AAC Blocks | After · pooled or Naive fallback | RMSE | 212.990 | 146.923 |
| AAC Blocks | After · pooled or Naive fallback | R2 | -11.952 | -2.751 |
| AAC Blocks | After · pooled or Naive fallback | WAPE | 44.533% | 31.602% |
| Binding Wire | Before · Naive | MAE | 2.878 | 2.904 |
| Binding Wire | Before · Naive | RMSE | 3.332 | 3.436 |
| Binding Wire | Before · Naive | R2 | -2.140 | -2.204 |
| Binding Wire | Before · Naive | WAPE | 32.798% | 33.215% |
| Binding Wire | After · pooled or Naive fallback | MAE | 2.878 | 2.904 |
| Binding Wire | After · pooled or Naive fallback | RMSE | 3.332 | 3.436 |
| Binding Wire | After · pooled or Naive fallback | R2 | -2.140 | -2.204 |
| Binding Wire | After · pooled or Naive fallback | WAPE | 32.798% | 33.215% |
| Bricks | Before · Naive | MAE | 299.682 | 296.856 |
| Bricks | Before · Naive | RMSE | 324.897 | 327.941 |
| Bricks | Before · Naive | R2 | -1.325 | -1.016 |
| Bricks | Before · Naive | WAPE | 25.263% | 23.359% |
| Bricks | After · pooled or Naive fallback | MAE | 477.266 | 326.742 |
| Bricks | After · pooled or Naive fallback | RMSE | 564.331 | 356.336 |
| Bricks | After · pooled or Naive fallback | R2 | -9.940 | -1.524 |
| Bricks | After · pooled or Naive fallback | WAPE | 37.159% | 26.169% |
| Cement | Before · Naive | MAE | 52.162 | 50.816 |
| Cement | Before · Naive | RMSE | 60.464 | 59.110 |
| Cement | Before · Naive | R2 | -1.876 | -1.749 |
| Cement | Before · Naive | WAPE | 24.217% | 24.252% |
| Cement | After · pooled or Naive fallback | MAE | 41.687 | 45.500 |
| Cement | After · pooled or Naive fallback | RMSE | 47.537 | 51.198 |
| Cement | After · pooled or Naive fallback | R2 | -0.760 | -0.423 |
| Cement | After · pooled or Naive fallback | WAPE | 19.213% | 18.586% |
| Coarse Aggregate | Before · Naive | MAE | 10.702 | 10.303 |
| Coarse Aggregate | Before · Naive | RMSE | 12.386 | 12.495 |
| Coarse Aggregate | Before · Naive | R2 | -3.009 | -2.523 |
| Coarse Aggregate | Before · Naive | WAPE | 34.260% | 32.323% |
| Coarse Aggregate | After · pooled or Naive fallback | MAE | 9.003 | 8.509 |
| Coarse Aggregate | After · pooled or Naive fallback | RMSE | 10.125 | 9.871 |
| Coarse Aggregate | After · pooled or Naive fallback | R2 | -1.942 | -1.823 |
| Coarse Aggregate | After · pooled or Naive fallback | WAPE | 29.152% | 29.023% |
| PVC Pipes | Before · Naive | MAE | 51.813 | 48.257 |
| PVC Pipes | Before · Naive | RMSE | 66.778 | 64.039 |
| PVC Pipes | Before · Naive | R2 | -1.446 | -1.344 |
| PVC Pipes | Before · Naive | WAPE | 27.627% | 27.251% |
| PVC Pipes | After · pooled or Naive fallback | MAE | 43.041 | 43.274 |
| PVC Pipes | After · pooled or Naive fallback | RMSE | 51.152 | 53.023 |
| PVC Pipes | After · pooled or Naive fallback | R2 | -0.585 | -0.264 |
| PVC Pipes | After · pooled or Naive fallback | WAPE | 23.364% | 23.631% |
| Ready-Mix Concrete | Before · Naive | MAE | 2.053 | 2.156 |
| Ready-Mix Concrete | Before · Naive | RMSE | 2.338 | 2.411 |
| Ready-Mix Concrete | Before · Naive | R2 | -3.164 | -2.760 |
| Ready-Mix Concrete | Before · Naive | WAPE | 37.252% | 36.418% |
| Ready-Mix Concrete | After · pooled or Naive fallback | MAE | 3.650 | 4.212 |
| Ready-Mix Concrete | After · pooled or Naive fallback | RMSE | 4.313 | 4.877 |
| Ready-Mix Concrete | After · pooled or Naive fallback | R2 | -15.058 | -13.662 |
| Ready-Mix Concrete | After · pooled or Naive fallback | WAPE | 67.950% | 69.215% |
| River Sand | Before · Naive | MAE | 8.993 | 9.152 |
| River Sand | Before · Naive | RMSE | 10.276 | 10.651 |
| River Sand | Before · Naive | R2 | -2.721 | -2.715 |
| River Sand | Before · Naive | WAPE | 33.058% | 33.675% |
| River Sand | After · pooled or Naive fallback | MAE | 8.273 | 8.299 |
| River Sand | After · pooled or Naive fallback | RMSE | 9.785 | 9.823 |
| River Sand | After · pooled or Naive fallback | R2 | -2.615 | -2.163 |
| River Sand | After · pooled or Naive fallback | WAPE | 30.956% | 31.957% |
| TMT Steel | Before · Naive | MAE | 90.052 | 95.042 |
| TMT Steel | Before · Naive | RMSE | 101.751 | 106.629 |
| TMT Steel | Before · Naive | R2 | -1.958 | -1.927 |
| TMT Steel | Before · Naive | WAPE | 30.804% | 31.447% |
| TMT Steel | After · pooled or Naive fallback | MAE | 83.617 | 95.042 |
| TMT Steel | After · pooled or Naive fallback | RMSE | 94.877 | 106.629 |
| TMT Steel | After · pooled or Naive fallback | R2 | -1.558 | -1.844 |
| TMT Steel | After · pooled or Naive fallback | WAPE | 28.568% | 31.447% |
| Tiles | Before · Naive | MAE | 10.561 | 10.079 |
| Tiles | Before · Naive | RMSE | 12.884 | 12.578 |
| Tiles | Before · Naive | R2 | -1.893 | -2.032 |
| Tiles | Before · Naive | WAPE | 26.296% | 27.614% |
| Tiles | After · pooled or Naive fallback | MAE | 9.724 | 9.407 |
| Tiles | After · pooled or Naive fallback | RMSE | 11.415 | 10.891 |
| Tiles | After · pooled or Naive fallback | R2 | -1.432 | -1.315 |
| Tiles | After · pooled or Naive fallback | WAPE | 24.592% | 23.426% |

Transform chosen per model by backtest MAE (holdout excluded):

| Pooled model | Transform | Macro-mean backtest MAE |
|---|---|---:|
| Pooled MLR | raw | 275.912 |
| Pooled Random Forest | log1p | 238.386 |
| Pooled XGBoost | log1p | 212.499 |

Evaluation window: 149 calendar weeks; untouched holdout 2026-04-13 through 2026-11-08. See `pooled_results.json` for series-level model choice, fold scores, and metrics.
<!-- END GENERATED POOLED RESULTS -->

### Pooled experiment interpretation

Macro-mean after values are higher than the before Naive baseline for all three requested error measures: MAE 85.556 vs. 65.219, RMSE 100.986 vs. 73.825, and WAPE 33.828% vs. 30.282%. Medians are lower after selection (MAE 20.579 vs. 27.050; RMSE 22.897 vs. 34.080; WAPE 29.028% vs. 29.835%), but the worse macro means do not support an overall holdout improvement claim. Among the 30 series selected as pooled by backtest, pooled holdout MAE is lower than that series' Naive holdout MAE in 20 and higher in 10. Backtest selection therefore fails to generalize to the holdout in one third of pooled-selected series; across those 30, mean pooled MAE is 103.719 versus 63.044 for Naive. Median R² after selection is −1.844, so it remains negative.

The largest holdout MAE losses among the pooled-selected series are concentrated in high-volume Bricks and AAC Blocks series. This pattern is consistent with series-scale differences being a likely contributor to pooled errors, alongside short training histories and the deterministic generated extension; it is evidence of association, not proof of cause. Values below compare each series' Naive holdout MAE with its selected pooled model's holdout MAE; they are read directly from `pooled_results.json` and sorted by the increase.

| Site | Material | Selected pooled model | Naive holdout MAE | Pooled holdout MAE | Increase |
|---|---|---|---:|---:|---:|
| Sahastradhara Road, Dehradun | Bricks | Pooled Random Forest | 294.022 | 1477.559 | 1183.537 |
| Sahastradhara Road, Dehradun | AAC Blocks | Pooled MLR | 137.940 | 456.704 | 318.763 |
| Jakhan, Dehradun | Bricks | Pooled XGBoost | 299.689 | 415.579 | 115.890 |
| GMS Road, Dehradun | Ready-Mix Concrete | Pooled XGBoost | 1.463 | 4.839 | 3.376 |
| Jakhan, Dehradun | Ready-Mix Concrete | Pooled XGBoost | 2.094 | 4.234 | 2.140 |

## Artifact run

`python -m scripts.train_all_models` completed 60/60 series with 300 version 1.3 model records and zero series issues in 115.91 seconds. The script retired 305 unreferenced `.joblib` files. A subsequent audit removed 300 stale version 1.2 database rows whose stored `/home/user/...` artifact paths were absent in this workspace. The database now has 600 artifact rows (300 retained version 1.2 references and 300 version 1.3 references), all 600 referenced files exist, and there are 600 `.joblib` files.

## Interpretation and limits

Median R² remains negative for every model, including the pooled-or-Naive result (−1.844). Naive is selected for 39/60 production per-series pairs and pooled models for 30/60 experiment series; the ML models do not consistently improve on the last-value baseline. The pooled-or-Naive policy's mean holdout MAE, RMSE, and WAPE are all worse than the Naive baseline, despite lower medians. The evaluation uses a Construction Materials Dehradun Dataset (6,300 self-created rows plus 2,640 generated rows), not real observed demand. Short history and scale differences are likely limitations; the generated extension also limits what the holdout can establish. The results therefore do not support a claim that the current models are reliable real-world forecasts. The UI shows production model selections, untouched holdout metrics and the exact generated-row count in each holdout.

Per-series candidates do not use material/site/project phase, price, or lead time as features. The offline pooled evaluator compares MLR, Random Forest, and XGBoost under raw, log1p, and per-series training-mean target scales. It chooses a transform per model using macro-mean per-series backtest MAE, then only uses a pooled model for an individual series when its backtest MAE strictly beats Naive. The expected challenge is limited per-series history (about 2.9 years weekly) combined with a self-created dataset and deterministic synthetic extension: pooling may help share patterns, but cannot establish real observed demand performance. In these results, pooled selection improved holdout MAE over Naive for 20 of the 30 pooled-selected series and worsened it for 10; the overall macro-mean holdout errors were higher than the Naive baseline, so the pooled model has not demonstrated an overall improvement.
