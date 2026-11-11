# Replenishment Policy Simulation

## Design

This is a retrospective replay of the same final 30-week chronological holdout used by forecasting, across all 60 site/material series. Model selection is fixed before the holdout using rolling-origin MAE. Policies compared are:

- **Selected model:** the already selected series forecast drives the rolling reorder point and order-up-to target.
- **Naive:** the holdout Naive forecast drives the same policy formulas.
- **Fixed reorder point:** a constant reorder point and target use only the training-period trailing 52-week mean and one-step-difference standard deviation.

All policies begin with the same train-only one-review-cycle target stock. Orders are reviewed weekly, placed in configured material-unit packs, and arrive after the material's configured lead time. Each replay is independent; it does not use the live stock ledger, create transactions, or affect the model holdout.

Costs use scenario assumptions from `inventory_app/policy_config.py`: order costs by material class, annual holding rates of 15%, 20%, or 30% of reference unit value, and shortage penalties of 1.5×, 2×, or 3× reference unit value. These rates are sensitivity assumptions; the dataset contains no verified carrying cost or shortage penalty. Unit prices are rebased indicative references, not audited procurement costs.

Service level is fulfilled demand divided by total observed demand. A stockout week has any positive unmet demand. Average stock quantity is converted to holding cost at the reference value and annual rate. Total policy cost adds holding, shortage, and fixed per-order costs.

## Default scenario

At 20% annual holding cost and a 2× unit-value shortage penalty, macro means across the 60 series were:

| Policy | Service level | Stockout weeks | Orders | Total cost per series (INR) |
|---|---:|---:|---:|---:|
| Selected model | 92.59% | 4.87 | 15.87 | ₹588,380 |
| Naive | 91.24% | 5.87 | 16.43 | ₹656,508 |
| Fixed reorder point | 92.83% | 4.22 | 14.13 | ₹634,388 |

This scenario suggests the selected-model policy lowered simulated cost relative to the two baselines, while the fixed rule had slightly higher fill and fewer stockout weeks. It is a result under the stated synthetic data and cost assumptions, not a procurement recommendation.

## Full sensitivity output

`policy_simulation_summary.json` has macro results for every policy/rate combination; `policy_simulation.csv` contains each of the 1,620 series/scenario rows, including holdout dates, costs, fill, stockouts, orders, prices and order-cost assumptions. Regenerate after training with `python -m scripts.simulate_inventory_policies`.
