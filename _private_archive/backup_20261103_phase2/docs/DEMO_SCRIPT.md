# 8-Minute Demo Script

## 0:00–0:45 — Opening
Introduce SiteStock as a local construction-material inventory system. State the problem: stock, receipts, consumption, sales, and reorder decisions need one consistent record.

## 0:45–1:30 — Dashboard
Show current stock, low-stock alerts, sales revenue, and the historical consumption view. Explain that the operational ledger and historical demand are stored and displayed separately. Point out the unit and INR labels.

## 1:30–2:40 — Inventory
Select a site and material. Walk through the physical opening-count, receipt, consumption, and adjustment form. Explain the stock equation and why an opening count is required. Show recorded-cost stock value and explain that missing costs remain unavailable.

## 2:40–3:30 — Sales
Show a posted sale, revenue, and gross margin. Explain FIFO cost layers and idempotency. Note that catalogue price references do not replace recorded cost.

## 3:30–4:30 — Forecasting
Select one site/material pair and request an evaluation. Compare Naive with candidate models. Explain the expanding-window validation and untouched chronological holdout. Point to MAE, RMSE, and WAPE in the material's unit. Show the selected model's pre-holdout calibrated range and feature importance.

## 4:30–5:45 — Replenishment
Show live stock and reorder configuration. Walk through lead-time demand, safety stock, incoming lines, and order constraints. Explain that stale demand coverage or missing stock blocks a numeric order.

## 5:45–6:30 — Purchasing
Show the supplier form and purchase-order workflow. Explain status changes and that a receipt updates the ledger.

## 6:30–7:15 — Data and reports
Show CSV validation, data-quality summaries, import history, and workbook/CSV exports. Explain that imports are historical observations and do not initialize operational stock.

## 7:15–8:00 — Close
Summarize what the application demonstrates and its limits. Use PROJECT_REPORT.md and MODEL_RESULTS.md for the measured results. Do not claim the model beats Naive overall or use the demonstration as a real purchasing authority.
