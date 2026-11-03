# Presentation Outline

1. **Title and team** — SiteStock: construction-material inventory and demand forecasting.
2. **Problem and objectives** — stock records, unit-aware movements, replenishment, and comparison against baselines.
3. **Scope** — local application, six site identifiers, ten materials, weekly series.
4. **Dataset and assumptions** — 8,940 rows/60 series, 16 columns; explain rebased indicative prices, unit conversions, and source uncertainty.
5. **Quality audit** — missing values, duplicate natural keys, preserved quantities/stock chain, past-only demand/price labels, and retained IQR flags.
6. **Architecture** — browser UI, FastAPI, services, SQLite, CSV input and exports.
7. **Database and workflow** — entities, ledger, idempotency, constraints.
8. **Forecasting method** — target, past-only features, rolling-origin selection, chronological holdout.
9. **Results** — MAE/RMSE/WAPE/MASE and empirical interval coverage; point out Naive was selected in 39/60 series.
10. **Inventory logic and UI** — shared High/Medium/Low rules, 90/95/98% service levels, z-score safety stock, overstock and pack-rounded order suggestions.
11. **Policy simulation** — selected-model, Naive and fixed reorder point under 15/20/30% carrying rates and 1.5/2/3× shortage costs; distinguish assumed costs from records.
12. **Limitations and future work** — simulated observations, estimated reference prices, assumed costs/lead times, and need for verified operational data.
13. **Conclusion and demo** — what works, what the evidence supports, and next steps.
