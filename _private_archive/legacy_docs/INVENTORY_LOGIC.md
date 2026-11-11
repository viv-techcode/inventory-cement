# Inventory risk, suggestions, and level labels

`inventory_app/risk.py` is the shared implementation. `/api/replenishment/calculate`, dashboard summaries, exports, and stored risk views must consume its result; the UI displays that API result without recomputing risk. Default constants and reorder pack assumptions live in `inventory_app/policy_config.py`.

## Formula definitions

All demand and error terms are per week; lead time is converted from days to weeks.

- Lead-time demand: `weekly demand × lead-time weeks`.
- Safety stock: `z × weekly forecast-error sigma × sqrt(lead-time weeks)`. The default service level is 95%, so `z = 1.645`.
- Reorder point: `lead-time demand + safety stock`.
- Days of cover: `on-hand / (weekly demand / 7)`. With zero demand, cover is undefined and returned as null.
- Order-up-to target: `weekly demand × (lead-time weeks + one review week) + safety stock`.
- EOQ cross-check: `sqrt(2 × annual demand × order cost / (unit value × annual holding-rate))`. The final candidate order is the larger of EOQ and the positive order-up-to gap after eligible incoming; then minimum order and pack-size rounding are applied.
- `policy_config.py` sets the default service level to 95%, holding rate to 20% per year, order costs by material class, practical pack sizes, and a 90-day overstock limit.

The interval width relative to forecast demand is shown as confidence: below 0.5 is Narrow; at or above 0.5 is Wide. A ratio of 1.0 or more makes risk at least Medium. The lower bound of forecast demand is not treated as a certainty guarantee.

## Risk precedence

Apply the first matching rule:

1. **HIGH** — missing on-hand, forecast, or lead-time input; negative on-hand; stock below safety stock; or days of cover strictly below lead time.
2. **MEDIUM** — stock is at or below reorder point (including exact equality); cover is at most 1.25× lead time; or the interval is very wide (relative width ≥1.0).
3. **LOW** — otherwise. A fully observed zero-demand, zero-error case is Low with undefined cover.

The independent `overstock` flag is true when days of cover is greater than 90. It does not replace High/Medium/Low.

## Suggestions

- High: **Order now**, with the quantity rounded to the configured pack. The order-by date is today and expected arrival is today + lead time. The reason states cover and lead time where both are known.
- Medium: **Order soon** when cover is within 1.25× lead time; otherwise **Plan order**. The planned date is the latest date before lead-time coverage expires, bounded at today.
- Low: **Hold**, quantity zero.
- Overstock with non-High risk: **Reduce next order**, quantity zero, plus a separate amount by which the next order should be reduced to return under the 90-day limit.
- Missing or invalid stock data: a High indicator is shown, the numeric order quantity is withheld, and the reason asks for a physical count or correction.

## Worked example

Assume weekly demand is 70 bags, rolling error sigma is 12 bags, lead time is 14 days (2 weeks), on-hand is 150 bags, price is ₹443/bag, order cost is ₹500, and eligible incoming is zero. At 95% service, the implementation uses `z = 1.6448536`, so safety stock is `z × 12 × sqrt(2) = 27.91` bags. Lead-time demand is `70 × 2 = 140` bags and reorder point is `167.91` bags. Cover is `150 / (70/7) = 15 days`, slightly above lead time; stock is below reorder point, so risk is Medium. The target including one review week is `70 × 3 + 27.91 = 237.91` bags, leaving an 87.91-bag order-up-to gap. EOQ is `sqrt(2 × 3,640 × 500 / (443 × 0.20)) = 202.69` bags; the larger candidate rounds up to 250 bags at a 50-bag pack size. The expected arrival is the planned order date plus 14 days.

## Demand and price level labels

`inventory_app/levels.py::expanding_level_labels` is the only definition for every Low/Medium/High label. For a value in a site/material series, thresholds use only prior finite values in that same series. Until 12 prior values exist the label is Medium. Thereafter, a value below the prior-history 33rd percentile is Low, above the 67th percentile is High, and between or exactly on thresholds is Medium. `demand_level` uses consumption; `price_level` uses the rebased unit price. Builder, importer, API frame, DB fields, and exports share these labels; the UI only displays them.
