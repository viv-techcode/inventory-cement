# SiteStock — Construction Materials Operations

SiteStock is an offline-first construction-material operations workspace. Its bundled source is the **Construction Materials Dehradun Dataset**: self-created Dehradun construction-materials data (6,300 rows) plus a deterministic generated extension (2,640 rows), 8,940 rows total. It is not real observed demand. Row provenance is recorded in `data_origin`.

Historical observations remain separate from the live operational ledger. Dataset stock fields never initialize current inventory; source prices are not operational acquisition costs. FIFO costing uses recorded transaction costs only, and unknown costs/margins remain unavailable.

## Start

From the repository root, with Python 3.11 or newer. XGBoost is optional.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Optional XGBoost model:
python -m pip install -r requirements-optional-ml.txt
# Rebuild the merged CSV from verified archived inputs:
python -m scripts.merge_dataset
# Optional tagged sample operations:
python -m scripts.load_operations
# Persist per-series forecast assessments:
python -m scripts.train_all_models
# Optional pooled forecasting experiment:
python -m scripts.train_pooled
# Start the local app:
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Startup initializes the configured database and imports the single merged CSV if its file hash is not already present. The merged CSV contains 8,940 rows and is rebuilt from `data/archive/pre_merge/`; the original source files and generator are preserved there with a hash manifest. DB-importing and training commands can change the database or artifacts. Back up `data/inventory.db` before using them against an existing database. The merge command itself only writes the merged CSV.

There is no npm install, frontend build, CDN, remote font, or runtime network dependency. Plotly.js is bundled locally; the browser uses same-origin relative API paths.

## Dataset

- Display name: **Construction Materials Dehradun Dataset**
- Active file: `data/construction_materials_dehradun_dataset.csv`
- 8,940 rows: `original_self_created` 6,300; `generated_extension` 2,640
- 6 sites × 10 materials = 60 series, 149 weekly rows per series
- Calendar coverage: 2024-01-01 through 2026-11-02
- The final 30 weeks per series are generated: 1,800/1,800 holdout rows (100%). Forecast scores are diagnostics on generated rows, not real-future accuracy.
- Original source fields are retained in order; `data_origin` is appended. It is optional when importing older-format CSVs.
- Archive manifest and detailed findings: [`docs/DATASET_AUDIT.md`](docs/DATASET_AUDIT.md); data card: [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md).

The 14 source fields describe date, site and project, material/unit, consumption and stock quantities, INR unit price, supplier lead time, and WPI reference month. The WPI field is a month key, not an index value. No supplier identities or purchasing thresholds are represented.

## Seven pages

- **Dashboard** — operational ledger balances, recorded-cost stock valuation, sales/revenue and reorder alerts, with historical demand separate.
- **Inventory** — opening counts, receipts, consumption and signed adjustments; balances, FIFO valuation, filters and catalogue administration.
- **Sales** — customers, quantity/date/unit sale price, stock deduction, revenue, and margin when FIFO costs are recorded.
- **Forecasting** — per-series Naive, Seasonal Naive, MLR, Random Forest and optional XGBoost. Model selection uses pre-holdout rolling-origin MAE; the UI reports the exact generated-row count in each holdout.
- **Replenishment** — live ledger stock, reorder settings, freshness checks and step-by-step calculation. Missing physical stock, lead time or current demand withholds numeric advice.
- **Purchasing** — suppliers, draft purchase orders, approvals and receipts.
- **Data & Reports** — source quality, CSV validation/import, rejection audit, and separate operational and observation exports.

## Forecast sources and methodology

The API uses either the Construction Materials Dehradun Dataset or operator-originated operational sales; it does not mix them. Auto selects operational sales only after at least 26 observed weekly or 18 observed monthly periods. Sample ledger sales are excluded from that gate.

- Weekly/monthly aggregation does not zero-fill missing periods or invent daily demand.
- Three expanding-window rolling-origin folds before the final chronological holdout select models using MAE only.
- Past-only lag 1–4 and trailing-four-period features; MAE, RMSE, R² when defined, and zero-safe WAPE.
- The Asia/Kolkata seven-day freshness gate and 90-day weekly horizon guard remain active for current replenishment.

## Limitations

The data is self-created and partly generated, not real observed demand. The last 30 weeks (1,800 rows) in the model holdout are generated. Existing results show negative median R² across candidates and Naive selected for 39 of 60 series, so the current evidence does not establish useful real-world forecast accuracy. Supplier identity, verified price provenance, and reorder policies are also absent. See [`docs/MODEL_RESULTS.md`](docs/MODEL_RESULTS.md).

## Project layout

```text
api/                         FastAPI app and routers
frontend/                    Static interface and local Plotly.js
inventory_app/               Services, DB models, migrations and forecasting
scripts/                      Merge, operations loader and model training
data/                         One active merged CSV, archive, and SQLite DB
tests/                         Integrity, import, forecast and application checks
docs/                          Audit, data card, profile, model results and QA notes
```

## Verification commands

```powershell
python -m compileall -q api inventory_app scripts tests
node --check frontend/app.js
python -m scripts.merge_dataset
```

The merge command verifies archived source values, counts and duplicate keys. Other checks are not claimed as run unless recorded separately. The project's provided rules prohibit running pytest or uvicorn in this environment.
