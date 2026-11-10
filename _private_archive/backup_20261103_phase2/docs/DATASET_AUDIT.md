# Dataset Quality Audit

## Scope and method
Audited the canonical CSV with Python/pandas. Natural key: (project_site_id, material, date). Stock flow was checked as closing = opening_stock_qty + incoming_qty - consumption_qty; adjacent observations compare current opening stock with the prior calculated closing stock. Consumption outliers use Tukey's 1.5×IQR rule within each site/material series. No values were changed during this audit.

## Results
| Check | Result |
|---|---|
| Rows and columns | 8,940 rows × 14 columns |
| Sites, materials, series | 6 sites, 10 materials, 60 series |
| Rows per series | 149 for each series |
| Timestamp range | 2024-01-01 through 2026-11-02 |
| Missing values | 0 across all 14 columns |
| Exact duplicate rows | 0 |
| Duplicate natural keys | 0 |
| Calendar cadence | 7 days between normalized dates within every series |
| Numeric validity | No nonnumeric/missing numeric values; no negative quantities; all unit prices and lead times are positive |
| Calculated closing stock | No negative closing balances |
| Adjacent stock-chain checks | 0 mismatches over 8,880 adjacent comparisons, tolerance 1e-6 |
| Material-unit consistency | Each material uses one unit across all sites |
| Consumption IQR flags | 250 across the 60 series; retained unchanged |

## Interpretation
IQR flags identify values for review, not errors. No external evidence is available to justify changing those measurements. Timestamp clock times vary, while normalized calendar dates are weekly. The WPI field is a month key only. Supplier identities, confirmed lead times, and verified procurement costs are not present.

Audit rerun: python -m scripts.build_dataset validates schema, row count, and duplicate keys; the stock-flow and outlier results above were calculated directly from the file.
