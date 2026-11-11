# Browser and API QA

Date: 2026-11-03. Target currently at `http://127.0.0.1:8000/`.

## Observed state

The browser shows the earlier process still bound to port 8000. Its `/api/health` body is `{"status":"ok","service":"construction-materials-operations"}` and has no schema/table/dataset checks. `/api/diagnostics` returns 404; `/api/dashboard` returns HTTP 500 and the UI reports an internal error. This response differs from the current source implementation. The legacy schema-4 ORM's `source_tag` query against the current DB reproduces `no such column: source_tag`, supporting the stale-process/schema-mismatch diagnosis.

Current app code was attempted on port 8001. `Start-Process ... uvicorn ... --port 8001` started a process, but a request to localhost returned a socket permission error before it could be reached. A `FastAPI TestClient` smoke test also stalls at initialization even for a trivial FastAPI app. Full `pytest -q` timed out after 180 seconds without output. A broader database/calculation set produced 43 passes and one stale schema assertion; after correcting its expected column count/date, the affected test passed separately. Fifteen focused dataset/risk/ingestion tests pass.

The current dashboard route was invoked directly against the active schema-v6 database and returned all 60 active risk pairs, risk counts, and the prioritized 30-row display list. This validates route logic but not the HTTP/browser stack.

## Outstanding browser check

After restarting the current application in a normal local shell, verify `/api/health`, `/api/diagnostics`, `/api/dashboard`, `/api/data/quality`, Forecasting, Dashboard risk labels, Replenishment service-level input, and the saved metrics table. No write action was submitted during browser inspection.
