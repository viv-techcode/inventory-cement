# Doon Ridge Materials

Construction-material inventory, purchasing, sales and weekly demand forecasting for six Dehradun locations. The baseline ledger covers 1 April 2024 through 2 July 2026.

## Architecture

FastAPI serves the REST API and static frontend. SQLAlchemy stores the loaded ledger events and operational records in SQLite. On an empty database, startup reconstructs the baseline from `data/construction_materials_ledger.csv` and deterministic loader logic. App-entered sales and receipts are stored in the database and excluded from model training.

## Data model

The committed ledger is the only active CSV. It records opening balances, sales, purchase receipts and stock adjustments with continuous event IDs, units, prices, costs and document references. Database tables hold material and site masters, customers, suppliers, purchase orders, receipt details, reorder parameters, derived weekly observations and post-load entries. No database file is committed.

## Forecasting

Weekly quantity is the target. Model evaluation uses chronological training and holdout periods, past-only features, expanding-window validation and MAE, RMSE, WAPE and MASE. Committed model metrics and aligned holdout/future predictions are in `docs/model_metrics.json`; the deployed app serves those outputs without fitting models at startup. Forecasts are fit directly for each of the 90 site/material weekly series, each with more than two years of weekly periods. Three expanding-window folds select the model; the final 16 weeks remain untouched for holdout reporting. See `docs/PLAN.md` for the accepted design and current completion state.

## Inventory calculations

- Reorder point = expected demand during supplier lead time + safety stock.
- Safety stock = z × weekly demand standard deviation × √(lead time in weeks).
- Inventory value and cost of goods sold use recorded weighted-average acquisition cost.
- ABC class is based on cumulative annualized sales value.
- Prices in the ledger are INR per unit, ex-GST; tax presentation uses the invoice date and SKU classification.

## Run locally

Python 3.11.11 is the pinned runtime.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.reset_database
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/`. Set `INVENTORY_DB_URL` to choose another SQLite path. `AS_OF_DATE` defaults to `2026-07-02`.

## Render

The service is defined in `render.yaml`. Use the free plan for a baseline that rebuilds from committed code and ledger. App-entered records reset when the service sleeps, restarts or deploys. Persistent storage requires changing to an eligible paid service plan and enabling the disk configuration documented in `docs/RENDER_DEPLOYMENT.md`.

## Known data limitations

- **Intermittent site-level demand:** Due to localized purchase frequency by regional trade contractors, 81 of the 90 site/material weekly series exhibit intermittent (lumpy) demand where site-level holdout WAPE exceeds 100%. Aggregating demand to material level resolves this sparsity and achieves a 45.88% holdout WAPE.
- **Master procurement structure:** The 440 receipt lines represent periodic call-off deliveries structured under 24 site/supplier master procurement agreements (1–6 SKU lines per order), alongside 4 planning orders illustrating the procurement approval lifecycle.
- **Reference-based pricing:** Baseline prices are benchmarked to CPWD regional schedules and published Dehradun market references. Operating margins align with commercial targets (cement ~7%, steel ~6%, masonry/aggregates ~14%, chemicals/accessories ~26%) with natural dealer variance and a documented March 2025 steel margin squeeze.
- **Ex-GST transaction ledger:** All ledger transactions are recorded ex-GST; tax presentation demonstrates statutory rate changes (such as the September 2025 cement GST rate adjustment) without full statutory GST tax invoice accounting.

## Project documents

- `docs/DATASET_CARD.md`: ledger coverage, columns and quality checks.
- `docs/PRESENTATION_GUIDE.md`: feature mapping, walkthrough and viva prompts.
- `docs/PLAN.md`: architecture, forecasting and acceptance checklist.
- `docs/DECISIONS.md`: design decisions and consulted sources.
- `docs/VERIFICATION_LOG.md`: commands and observed results.
- `docs/PRICE_REFERENCES.md`: material price ranges and reference URLs.
