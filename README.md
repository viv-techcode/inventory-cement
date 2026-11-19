# Doon Ridge Materials

Construction-material inventory, purchasing, sales and weekly demand forecasting for six Dehradun locations. The committed ledger covers 1 April 2024 through 2 July 2026.

## How it works

FastAPI serves the REST API and static frontend. SQLAlchemy stores operational records in SQLite. On startup, an empty database is rebuilt from `data/construction_materials_ledger.csv`. Sales and purchase receipts entered in the app are stored in the database. They are not added to the historical training ledger.

The ledger is the canonical event source for opening balances, sales, purchase receipts and adjustments. Inventory value and cost of goods sold use recorded weighted-average acquisition cost. Reorder calculations use configured lead time, safety stock and order constraints.

## Forecasting

Run `python -m ml.run_experiment` to create `results/model_results.csv` and `results/model_summary.md`. The experiment compares naive last value, a four-week moving average, seasonal naive, Linear Regression and XGBoost. It uses a chronological validation period to select a model separately at site/material and material aggregate levels, then scores the final untouched 16 weeks. It reports WAPE, MAE, RMSE and bias. Zero-demand share and average interval between demand weeks are included to make intermittency visible.

On the saved holdout, the selected four-week moving-average baseline has 42.82% material-level WAPE and 87.82% site/material-level WAPE. These are retrospective comparisons on this ledger. Sparse site/material demand can produce large errors, and aggregation changes the forecast target. Results are not reliable ordering advice. The app includes per-series comparisons and a moving-average baseline in model selection.

## Scope and limitations

This system demonstrates inventory and purchasing workflows, including sales, receipts and stock checks.
Forecasts and reorder suggestions depend on the available history, configured stock rules and stated assumptions.
The data covers a fixed historical period and a limited set of sites and materials.
Aggregate demand can hide differences between individual sites.
Forecast errors describe this holdout and do not guarantee future results.
Users should review stock, lead times and supplier conditions before ordering.

## Run locally

Python 3.11 is required.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.reset_database
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. Set `INVENTORY_DB_URL` to choose a different SQLite database. `AS_OF_DATE` defaults to the latest ledger date. To restore the baseline for a repeatable walkthrough, stop the server and run `python -m scripts.reset_database`.

Run the experiment and number check with:

```powershell
python -m ml.run_experiment
python -m ml.check_numbers
```

The main requirements file includes XGBoost so the documented experiment can run immediately after setup. The app still has built-in baselines and scikit-learn models if the optional tree model is unavailable at runtime.

Run the automated checks with `python -m pytest -q`. Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the complete sale-to-receipt walkthrough. See [docs/PRESENTATION_GUIDE.md](docs/PRESENTATION_GUIDE.md) for the feature map and viva questions.
