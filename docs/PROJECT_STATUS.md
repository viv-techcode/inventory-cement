# Project Status

The current code and generated analysis outputs are summarized in `PROJECT_REPORT.md`, `MODEL_RESULTS.md`, `POLICY_SIMULATION.md`, and `READINESS_SCORECARD.md`.

- Dataset: 8,940 rows, 60 series, 16 columns; hash `4b60db1190bce14bbe057c7772fcb00a7024365f18e623e2d406018fd90faee4`.
- Prices: rebased to documented indicative Dehradun references; demand/stock quantities and stock-chain calculations preserved.
- Database: schema v6, SQLite integrity OK, no foreign-key violations.
- Forecasts: 60/60 series trained; 300 model artifacts; rolling-origin selection, MASE and interval coverage persisted.
- Inventory: shared risk logic in API and dashboard; 15 focused dataset/risk/ingestion tests pass. Dashboard direct route check covers 60 pairs.
- Policy replay: 1,620 output scenarios across 60 series and three policies.
- Outstanding: full pytest and live browser/API check against a restarted current app. Full pytest timed out after 180 seconds. Port 8000 serves an older process; TestClient startup hangs and port 8001 bind is denied in this environment.
