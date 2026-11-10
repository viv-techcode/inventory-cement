# Browser QA

Date: 2026-11-03. Target: http://127.0.0.1:8000/.

## Pages
| Page | Result | Notes |
|---|---|---|
| Dashboard | Broken | UI displayed a request error; GET /api/dashboard returned HTTP 500. |
| Inventory | Works | Site/material catalogue, balances, ledger filters, transaction form, cost values, and reorder alerts rendered. No write was submitted. |
| Sales | Works | Sale form, customer list, revenue, FIFO margin, filters, and register rendered. No write was submitted. |
| Forecasting | Broken | Page displayed a request error because its data-quality request returned HTTP 500. |
| Replenishment | Works / no action run | Stock/rule selectors, arithmetic explanation, alert queue, and calculate form rendered. Source freshness prevents current advice; calculate was not submitted. |
| Purchasing | Empty | Supplier and purchase-order sections render; no suppliers or purchase orders are configured in the inspected view. |
| Data & Reports | Broken | Page displayed a request error because its data-quality request returned HTTP 500. |

## API and docs
- /docs: Swagger UI loaded and listed catalogue, dashboard, data, inventory, sales, forecasting, replenishment, reports, purchasing, and health operations.
- /api/health: returned status ok.
- /api/catalog: returned six sites, ten materials, and customers.
- /api/dashboard: HTTP 500.
- /api/data/quality: HTTP 500.
- The inventory page linked a current-inventory CSV export.
- Full endpoint smoke testing is still pending against a restarted app process.

## Inputs, charts, and logs
No mutating form was submitted against the existing database. Input edge cases should be run against an isolated test database through pytest/API tests. Dashboard and forecast charts could not be inspected because their data requests failed. Browser console output and server process logs were not available through the provided terminal/browser bridge.

## Diagnosis
The live page appears to hold an older in-memory model that still expects the removed historical label column. A direct current-code quality-service check over the migrated database succeeds. Restart the app process using the README command, then repeat this checklist; the old process could not be stopped from this environment.
