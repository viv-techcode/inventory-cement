# 8-Minute Demo Script

## 0:00–0:45 — Opening
Introduce SiteStock as a local construction-material inventory system. State the problem: stock, receipts, consumption, sales, and reorder decisions need one consistent record.

## 0:45–1:30 — Dashboard
Show current stock, low-stock alerts, sales revenue, and the historical consumption view. Point out the shared High/Medium/Low risk counts and the 90-day overstock flag. Explain that risk uses current ledger stock plus a past-only demand baseline; missing physical counts are High. The operational ledger and historical demand stay separate.

## 1:30–2:40 — Inventory
Select a site and material. Walk through the physical opening-count, receipt, consumption, and adjustment form. Explain the stock equation and why an opening count is required. Show recorded-cost stock value and explain that missing costs remain unavailable.

## 2:40–3:30 — Sales
Show a posted sale, revenue, and gross margin. Explain FIFO cost layers and idempotency. Note that catalogue price references do not replace recorded cost.

## 3:30–4:30 — Forecasting
Select one site/material pair and open its saved evaluation. Compare Naive with candidate models. Explain three pre-holdout rolling-origin folds and the separate chronological holdout. Point to MAE, RMSE, WAPE, and MASE. Show interval radius and observed holdout coverage; explain that coverage is a diagnostic, not a guarantee.

## 4:30–5:45 — Replenishment
Show live stock and reorder configuration. Select a 90%, 95%, or 98% service level. Walk through lead-time demand, z-score safety stock, incoming lines, EOQ/order-up-to quantity, and pack rounding. Explain that stale demand coverage or missing stock blocks a numeric order.

## 5:45–6:30 — Purchasing
Show the supplier form and purchase-order workflow. Explain status changes and that a receipt updates the ledger.

## 6:30–7:15 — Data and reports
Show CSV validation, data-quality summaries, import history, and workbook/CSV exports. Explain that imports are historical observations and do not initialize operational stock.

## 7:15–8:00 — Close
Summarize the holdout policy simulation and its assumed holding/shortage costs. Use PROJECT_REPORT.md, MODEL_RESULTS.md, and POLICY_SIMULATION.md for measured results and limits. Do not claim models beat Naive overall or use simulated suggestions as real purchasing authority.
