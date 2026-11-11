# Indicative price sources and rebasing

## Reference date and source quality

The price base is a Dehradun dealer-to-retail snapshot dated 12 August 2026, with material-wise midpoints and ranges from [InfraLens Dehradun construction prices](https://www.infralens.in/prices/dehradun) and its [Dehradun steel rate page](https://www.infralens.in/prices/steel/dehradun). The displayed rates are indicative dealer-to-retail estimates, not official rates or confirmed quotations. The page reports those August anchors and ranges; a later generic Dehradun list had conflicting units and materially different cement/steel levels, so it was not treated as a like-for-like update.

The [BusinessToday cement market report, 29 September 2026](https://www.businesstoday.in/amp/markets/stocks/story/cement-prices-rise-rs-7-per-bag-in-september-more-hikes-expected-in-october-report-558517-2026-09-29) reports a ₹7 per bag September increase and expected ₹5–20 October hikes. For the dataset anchor, the brief's stated August-base increase of ₹10–25 is used, with central adjustment +₹15 per 50-kg bag.

The [Business Standard steel report, 2 October 2026](https://www.business-standard.com/markets/stock-market-news/steel-sector-eyes-stronger-quarters-as-demand-and-realisations-improve-126100200992_1.html) reports domestic rebar up 10% month-on-month in August and still rising in September. [SMM's 23 October 2026 market review](https://news.metal.com/newscontent/104176205-smm-analysis-india-rebar-market-august%E2%80%93september-rally-loses-momentum-in-october) reports a strong August–September rally followed by weaker October momentum. Those national/regional series do not identify the same Dehradun dealer-to-retail product basis; the brief's narrower +3–6% band is therefore used for the Dehradun benchmark, central +4%.

The [Uttarakhand PWD SOR portal](https://mis.pwduk.in/pwd/sor) is the official schedule-of-rates reference for future cross-checking. PWD schedule rates are government estimate benchmarks; they are not substituted for dealer-to-retail prices here.

## Product mapping and November 2026 anchors

`inventory_app/price_config.py` is the single configuration for the following mapping. August midpoint is converted to the dataset unit, then the November category adjustment and site factor are applied. The configured reference ranges are source ranges or explicit envelopes; the builder separately validates the complete historical price curve inside a broad 0.82–1.18 envelope of each adjusted latest-week site/material anchor.

| Dataset material | Reference mapping | August anchor | November adjustment | Dehradun latest-week target before site factor |
|---|---|---:|---:|---:|
| AAC Blocks | 600×200×200 mm AAC block, piece | ₹82/piece | +1% | ₹82.82/piece |
| Binding Wire | 18-gauge binding wire | ₹62/kg | +4% | ₹64.48/kg |
| Bricks | red-clay brick, piece | ₹9/piece | +1% | ₹9.09/piece |
| Cement | OPC 43, 50-kg bag | ₹428/bag | +₹15 | ₹443/bag |
| Coarse Aggregate | 20-mm aggregate, tonne converted at 1.5 t/m³ | ₹1,289/t | +1.5% | ₹1,962.50/m³ |
| PVC Pipes | 4-in PVC SWR, ₹348/m converted to a 3-m piece | ₹348/m | +1% | ₹1,054.44/piece |
| Ready-Mix Concrete | M20 | ₹5,211/m³ | +1.5% | ₹5,289.17/m³ |
| River Sand | river sand, tonne converted at 1.6 t/m³ | ₹2,478/t | +1.5% | ₹4,024.27/m³ |
| TMT Steel | 12-mm Fe500D | ₹63/kg | +4% | ₹65.52/kg |
| Tiles | vitrified 2×2, ₹87/sqft converted at 10.7639104167 sqft/m² | ₹87/sqft | +1% | ₹945.82/m² |

The source categories do not exactly match every unspecified dataset specification. In particular, cement grade, block dimensions, concrete grade, pipe diameter/length, tile finish, bulk density, and the aggregate grading are not recorded in the original columns. The table's choices are documented scenario mappings. Bulk density and standard pipe length are material assumptions, so these unit-converted targets are less certain than the directly matched bag/kg/piece anchors.

## Site and earlier-week assumptions

- All six site identifiers are in Dehradun, Uttarakhand. The five urban sites use a site factor of 1.00.
- `Sahastradhara Road, Dehradun` uses 1.06 on the configured heavy-material set as a haulage allowance. This is an adjustable assumption, not a site quotation. Unknown sites default to 1.00.
- Earlier annual drift assumptions: cement 5%, steel 4%, bulk materials 3.5%, blocks 3%, finishes/plumbing 3%.
- Seasonal factor: 0.99 in June–September; 1.01 in October–March; 1.00 in April–May.
- A stable SHA-256 keyed noise term is bounded to ±0.4%; seed `20261103` is fixed in configuration. The factor is normalized to equal 1.0 on the latest observation date, so each latest price equals its configured November target.
- `scripts/build_dataset.py` applies the same price function to all rows. It modifies `unit_price_inr` and recomputes `price_level`; it preserves date, demand, receipts, opening stock, lead time, and all other recorded cells.

## Limitations

Rates are indicative dealer-to-retail estimates. GST, delivery, brand premium, order size, contractor discounts, and supplier-specific terms may differ. Validate against current local dealer quotations and the Uttarakhand PWD SOR before procurement or tender pricing. No official bill-of-quantity or supplier quote is represented as a market observation.
