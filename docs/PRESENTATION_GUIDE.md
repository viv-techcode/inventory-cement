# Presentation Guide

## Feature map

| Proposal feature | Application page |
|---|---|
| Revenue, margin, stock value and alerts | Dashboard |
| Site and material balances, coverage and stock movement | Inventory |
| Customer sales, cost and margin | Sales |
| Weekly holdout, residuals and forward estimates | Forecasting |
| Lead-time demand, safety stock and order quantities | Replenishment |
| Purchase orders, approvals and receipts | Purchasing |
| Ledger counts, quality checks and downloadable reports | Data & Reports |

## Five-minute walkthrough

1. Review the dashboard totals and the fixed data-through date.
2. Record a sale on the Sales page. Confirm quantity validation and observe the updated balance, revenue and margin.
3. Open Replenishment, inspect the formula inputs, run the planner and create a purchase order from a recommendation.
4. Approve and receive the order on Purchasing. Confirm that the receipt increases stock and appears in the purchase register.
5. Open Forecasting. Compare holdout actuals and predictions, inspect residual summaries, then show the forward forecast and intervals.
6. Open Data & Reports and show the coverage, event counts, quality checks and downloadable reports.

## Viva questions

1. **Why compare several model families?** Baselines establish a transparent reference, while regularized regression and tree models can use calendar, lag and rolling features.
2. **How is leakage avoided?** Data are split chronologically; each feature uses only observations available before its prediction date; model choices are made using validation periods.
3. **How is safety stock calculated?** It uses the selected service factor, demand variability and square root of lead time, with units converted to the planning period.
4. **Why report WAPE and MASE?** WAPE aggregates absolute error relative to total demand, while MASE compares errors with a simple training-period baseline. Both remain defined when some weeks have zero sales.
5. **How are forecast intervals produced?** They are based on the spread of validation residuals and should be interpreted as empirical ranges, not guaranteed bounds.
6. **Why fit site/material series directly?** The loaded history gives each of the 90 pairs more than two years of weekly observations, so each forecast can stay aligned with the matching site and material Sales total without a second allocation step.
7. **What does the holdout measure?** It measures performance on a final chronological window excluded from fitting and model selection.
8. **What do residual checks show?** Mean bias, error spread and a simple lag-one autocorrelation check can reveal systematic errors and remaining structure.
9. **Why use weighted-average costing?** It assigns a common per-unit cost to interchangeable stock and keeps valuation and gross margin consistent with receipt costs.
10. **How does ABC classification help?** It ranks materials by annualized sales value so review effort can focus on the largest value contributors.
11. **What are the main limitations?** The horizon is short, site histories can be intermittent, and price references do not replace dated supplier invoices.
12. **What would improve the system next?** Add verified transaction history, supplier-specific lead-time distributions, documented tax classification by SKU and longer out-of-time model evaluation.

**Data-origin response:** [To be supplied by the project owner.]

