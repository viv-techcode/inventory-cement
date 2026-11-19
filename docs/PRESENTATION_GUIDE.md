# Presentation guide

## Feature map

| Area | What to show |
|---|---|
| Dashboard | Sales, stock value, current alerts and site/material filters |
| Inventory | Current balance, transaction history and reorder status |
| Sales | Record a priced sale and inspect its inventory effect |
| Forecasting | Compare chronological baselines and candidate models; inspect holdout dates and errors |
| Replenishment | Review lead-time demand, safety stock and order suggestion |
| Purchasing | Create an order, move it through approval and receive goods |
| Data & Reports | Review ledger checks and download reports |

## Forecasting result

The saved, repeatable experiment is in `results/model_results.csv`; its protocol, selected models, holdout comparisons and intermittency summary are in `results/model_summary.md`. The figures in those files are the source for any forecast error claim. The experiment compares a site/material series with material totals because summing demand changes the amount of intermittency. A high site-level error is evidence of a data limitation and a model comparison result, not dependable ordering advice. Re-run it with `python -m ml.run_experiment` and verify documentation with `python -m ml.check_numbers`.

## Scope and limitations

This system demonstrates inventory and purchasing workflows, including sales, receipts and stock checks.
Forecasts and reorder suggestions depend on the available history, configured stock rules and stated assumptions.
The data covers a fixed historical period and a limited set of sites and materials.
Aggregate demand can hide differences between individual sites.
Forecast errors describe this holdout and do not guarantee future results.
Users should review stock, lead times and supplier conditions before ordering.

## Viva questions and short answers

1. **Why are site/material errors high?** Many weeks have no sale at a particular site, then demand arrives in bursts. Sparse series are hard to predict and WAPE can rise quickly.
2. **Why compare material totals too?** Aggregation combines activity across sites and can reduce zero-demand weeks; it answers a different, less localized question.
3. **Why use a chronological split?** It mirrors forecasting future periods from earlier history and avoids training on later observations.
4. **How is the model selected?** The script chooses by pooled validation WAPE, then reports the untouched final holdout separately.
5. **What are the baselines?** Last observed value, the average of the last four weeks, and the value from the matching week one year earlier.
6. **What candidate models are included?** Linear Regression and XGBoost, evaluated against those simple baselines.
7. **What does WAPE mean?** Total absolute error divided by total actual demand; it is undefined when the holdout contains no demand.
8. **Can a forecast guarantee a safe reorder quantity?** No. It depends on limited historical demand, lead time, configured rules and stock accuracy.
9. **How does the app prevent negative stock?** A sale or consumption transaction checks the current balance before it posts.
10. **How are duplicate receipts prevented?** A receipt is recorded with a unique idempotency key and reference, and quantities cannot exceed the PO line's remaining amount.
