# Presentation Outline

1. **Title and team** — SiteStock: construction-material inventory and demand forecasting.
2. **Problem and objectives** — stock records, unit-aware movements, replenishment, and comparison against baselines.
3. **Scope** — local application, six site identifiers, ten materials, weekly series.
4. **Dataset and assumptions** — schema, coverage, construction method; point to the data card.
5. **Quality audit** — missing values, duplicate natural keys, stock-chain checks, retained IQR flags.
6. **Architecture** — browser UI, FastAPI, services, SQLite, CSV input and exports.
7. **Database and workflow** — entities, ledger, idempotency, constraints.
8. **Forecasting method** — target, past-only features, rolling-origin selection, chronological holdout.
9. **Results** — per-series fallback and honest MAE/RMSE/WAPE tables; point out that Naive was selected in 39/60 series.
10. **Inventory logic and UI** — lead-time demand, safety stock, stock checks, order constraints, examples.
11. **Limitations and future work** — coverage, costs, suppliers, external drivers, collection of verified operational data.
12. **Conclusion and demo** — what works, what the evidence supports, and next steps.
