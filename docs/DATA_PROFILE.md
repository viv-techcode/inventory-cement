# Dataset Profile

## Original source — unchanged

- Source file: `data/Dehradun_Inventory_Dataset_Random_Times_Real_Places.csv`
- SHA-256: `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`
- Data rows: 6,300; fields: 14
- Site/material series: 6 sites × 10 materials = 60 pairs
- Rows per pair: 105 to 105; median 105
- Observation coverage: 2024-01-01 through 2025-12-29
- Source timestamp text uses `YYYY-MM-DD HH:MM:SS`; time-of-day is present on 6,300/6,300 rows. Observed clock-time range: 05:00:04–22:59:57.
- Calendar-date gaps per pair are 7 days on all 6,240 intervals; actual timestamp gaps (including time-of-day) range 6.252–7.743 days, with median 7.002 days. A total of 3,101 gaps are 6–7 days and 3,139 are over 7 and up to 8 days. Repeated observation dates within a pair: 0.
- Adjacent stock-flow checks: 6,240 comparisons; maximum absolute residual 7.27595761418e-12; residuals over 0.01: 0. Minimum recorded opening quantity: 0.97; minimum row closing estimate: 0.97.
- `wpi_reference_month` matches the calendar month of `date` on 6,300/6,300 rows; format is `YYYY-MM`. It is a month key, not a WPI index value.
- Units: AAC Blocks=pieces, Binding Wire=kg, Bricks=pieces, Cement=50-kg bags, Coarse Aggregate=m3, PVC Pipes=pieces, Ready-Mix Concrete=m3, River Sand=m3, TMT Steel=kg, Tiles=m2.

## Phase order by site

The table gives first observed date of each phase change in source order.

| Site | Phase progression |
|---|---|
| Clement Town, Dehradun | 2024-01-01 Foundation → 2024-07-01 Structure → 2024-12-30 Finishing → 2025-06-30 MEP → 2025-12-29 Foundation |
| GMS Road, Dehradun | 2024-01-01 Foundation → 2024-07-01 Structure → 2024-12-30 Finishing → 2025-06-30 MEP → 2025-12-29 Foundation |
| ISBT–Transport Nagar, Dehradun | 2024-01-01 Foundation → 2024-07-01 Structure → 2024-12-30 Finishing → 2025-06-30 MEP → 2025-12-29 Foundation |
| Jakhan, Dehradun | 2024-01-01 Foundation → 2024-07-01 Structure → 2024-12-30 Finishing → 2025-06-30 MEP → 2025-12-29 Foundation |
| Paltan Bazaar, Dehradun | 2024-01-01 Foundation → 2024-07-01 Structure → 2024-12-30 Finishing → 2025-06-30 MEP → 2025-12-29 Foundation |
| Sahastradhara Road, Dehradun | 2024-01-01 Foundation → 2024-07-01 Structure → 2024-12-30 Finishing → 2025-06-30 MEP → 2025-12-29 Foundation |

Phase row counts are equal across sites: Foundation 270, Structure 260, Finishing 260, and MEP 260 rows per site.

## Consumption statistics by site/material

Statistics use the 105 original weekly observations per pair. Standard deviation is sample SD; trend is ordinary least-squares quantity change per observed week; CV = SD / mean. ACF is Pearson autocorrelation at lags 1–4. Seasonal amplitude = (largest minus smallest month-of-year mean) / overall weekly mean; peak and trough are calendar months.

|Site|Material|Unit|n|Mean/wk|SD/wk|Min|Max|CV|Trend/wk|ACF1|ACF2|ACF3|ACF4|Season amp|Peak mo.|Low mo.|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|Clement Town, Dehradun|AAC Blocks|pieces|105|675.93|561.00|79.00|2188.00|0.830|4.301|0.922|0.898|0.860|0.837|0.640|3|9|
|Clement Town, Dehradun|Binding Wire|kg|105|55.79|44.68|5.50|153.65|0.801|-1.082|0.903|0.875|0.823|0.803|0.576|11|6|
|Clement Town, Dehradun|Bricks|pieces|105|3811.90|2670.24|591.00|8870.00|0.701|-9.268|0.935|0.894|0.852|0.810|0.367|2|8|
|Clement Town, Dehradun|Cement|50-kg bags|105|389.06|171.64|136.00|817.00|0.441|-4.514|0.848|0.839|0.830|0.750|0.443|4|9|
|Clement Town, Dehradun|Coarse Aggregate|m3|105|92.73|56.13|20.51|226.94|0.605|-1.550|0.869|0.841|0.836|0.830|0.642|1|9|
|Clement Town, Dehradun|PVC Pipes|pieces|105|57.38|58.12|9.00|205.00|1.013|1.559|0.931|0.901|0.864|0.845|1.464|11|1|
|Clement Town, Dehradun|Ready-Mix Concrete|m3|105|41.45|31.19|3.81|92.35|0.752|-0.888|0.919|0.908|0.893|0.862|0.610|4|9|
|Clement Town, Dehradun|River Sand|m3|105|73.70|37.13|17.58|154.52|0.504|-1.015|0.875|0.854|0.831|0.808|0.865|4|9|
|Clement Town, Dehradun|TMT Steel|kg|105|1377.44|1036.13|176.19|3775.33|0.752|-26.035|0.897|0.873|0.832|0.808|0.577|11|6|
|Clement Town, Dehradun|Tiles|m2|105|88.10|125.74|2.80|359.77|1.427|1.242|0.937|0.884|0.836|0.805|1.669|2|7|
|GMS Road, Dehradun|AAC Blocks|pieces|105|530.33|444.64|61.00|1459.00|0.838|3.537|0.953|0.913|0.879|0.860|0.744|3|9|
|GMS Road, Dehradun|Binding Wire|kg|105|42.33|34.22|4.82|122.54|0.808|-0.824|0.899|0.879|0.828|0.810|0.612|7|6|
|GMS Road, Dehradun|Bricks|pieces|105|2997.46|2118.99|432.00|7456.00|0.707|-7.513|0.918|0.897|0.867|0.818|0.404|12|6|
|GMS Road, Dehradun|Cement|50-kg bags|105|300.42|126.25|116.00|543.00|0.420|-3.443|0.864|0.865|0.850|0.794|0.359|1|8|
|GMS Road, Dehradun|Coarse Aggregate|m3|105|71.70|42.85|15.12|155.17|0.598|-1.223|0.926|0.901|0.880|0.858|0.501|1|9|
|GMS Road, Dehradun|PVC Pipes|pieces|105|46.40|46.65|6.00|158.00|1.005|1.261|0.916|0.892|0.865|0.844|1.436|11|1|
|GMS Road, Dehradun|Ready-Mix Concrete|m3|105|31.35|23.66|2.76|72.05|0.755|-0.680|0.920|0.900|0.888|0.857|0.730|1|9|
|GMS Road, Dehradun|River Sand|m3|105|56.66|28.26|12.41|130.30|0.499|-0.743|0.854|0.810|0.793|0.790|0.728|4|9|
|GMS Road, Dehradun|TMT Steel|kg|105|1067.41|792.81|139.80|2628.09|0.743|-19.834|0.908|0.894|0.866|0.812|0.481|11|6|
|GMS Road, Dehradun|Tiles|m2|105|69.83|101.18|1.78|327.33|1.449|0.968|0.947|0.890|0.856|0.811|1.886|3|9|
|ISBT–Transport Nagar, Dehradun|AAC Blocks|pieces|105|652.09|549.71|83.00|1960.00|0.843|4.421|0.938|0.892|0.877|0.852|0.712|3|8|
|ISBT–Transport Nagar, Dehradun|Binding Wire|kg|105|52.84|42.49|5.07|179.21|0.804|-0.994|0.878|0.858|0.852|0.775|0.548|12|6|
|ISBT–Transport Nagar, Dehradun|Bricks|pieces|105|3677.72|2625.62|632.00|9045.00|0.714|-10.349|0.907|0.872|0.858|0.827|0.486|11|6|
|ISBT–Transport Nagar, Dehradun|Cement|50-kg bags|105|369.12|164.27|134.00|726.00|0.445|-4.157|0.848|0.824|0.816|0.764|0.452|4|9|
|ISBT–Transport Nagar, Dehradun|Coarse Aggregate|m3|105|88.93|54.12|18.45|215.05|0.609|-1.540|0.901|0.892|0.880|0.834|0.651|4|8|
|ISBT–Transport Nagar, Dehradun|PVC Pipes|pieces|105|57.00|57.63|8.00|216.00|1.011|1.547|0.875|0.881|0.840|0.854|1.286|11|1|
|ISBT–Transport Nagar, Dehradun|Ready-Mix Concrete|m3|105|40.85|31.10|3.70|106.04|0.761|-0.873|0.898|0.877|0.841|0.823|0.589|5|8|
|ISBT–Transport Nagar, Dehradun|River Sand|m3|105|69.77|34.21|17.19|137.43|0.490|-0.915|0.859|0.828|0.813|0.803|0.851|4|9|
|ISBT–Transport Nagar, Dehradun|TMT Steel|kg|105|1343.14|999.57|181.50|3183.50|0.744|-24.763|0.908|0.864|0.836|0.797|0.483|12|6|
|ISBT–Transport Nagar, Dehradun|Tiles|m2|105|84.72|121.18|2.96|408.45|1.430|1.192|0.913|0.857|0.822|0.812|1.626|3|7|
|Jakhan, Dehradun|AAC Blocks|pieces|105|728.54|604.86|84.00|2032.00|0.830|5.015|0.934|0.892|0.869|0.840|0.674|5|8|
|Jakhan, Dehradun|Binding Wire|kg|105|62.91|52.36|6.03|183.73|0.832|-1.210|0.896|0.865|0.829|0.777|0.702|12|6|
|Jakhan, Dehradun|Bricks|pieces|105|4244.51|3002.85|651.00|9925.00|0.707|-10.231|0.927|0.887|0.864|0.818|0.407|11|6|
|Jakhan, Dehradun|Cement|50-kg bags|105|411.06|169.75|152.00|788.00|0.413|-4.318|0.876|0.813|0.760|0.699|0.505|5|9|
|Jakhan, Dehradun|Coarse Aggregate|m3|105|105.61|66.53|17.69|261.42|0.630|-1.842|0.874|0.882|0.829|0.849|0.677|5|8|
|Jakhan, Dehradun|PVC Pipes|pieces|105|63.51|63.32|7.00|244.00|0.997|1.696|0.866|0.877|0.868|0.857|1.289|10|5|
|Jakhan, Dehradun|Ready-Mix Concrete|m3|105|47.97|36.50|3.36|122.38|0.761|-1.047|0.906|0.907|0.878|0.841|0.717|4|9|
|Jakhan, Dehradun|River Sand|m3|105|78.82|39.00|19.61|178.44|0.495|-1.064|0.852|0.869|0.834|0.853|0.794|4|8|
|Jakhan, Dehradun|TMT Steel|kg|105|1509.63|1146.33|205.05|3837.22|0.759|-27.069|0.911|0.862|0.832|0.793|0.556|11|6|
|Jakhan, Dehradun|Tiles|m2|105|98.96|142.09|2.97|446.72|1.436|1.412|0.933|0.900|0.838|0.812|2.009|3|9|
|Paltan Bazaar, Dehradun|AAC Blocks|pieces|105|708.98|624.14|86.00|2380.00|0.880|5.087|0.923|0.908|0.868|0.835|0.830|3|8|
|Paltan Bazaar, Dehradun|Binding Wire|kg|105|56.28|45.23|5.05|154.15|0.804|-1.084|0.876|0.853|0.815|0.785|0.555|12|6|
|Paltan Bazaar, Dehradun|Bricks|pieces|105|4022.99|2876.08|623.00|9783.00|0.715|-11.386|0.913|0.875|0.853|0.802|0.494|11|6|
|Paltan Bazaar, Dehradun|Cement|50-kg bags|105|389.53|171.19|143.00|693.00|0.439|-4.641|0.853|0.823|0.812|0.770|0.443|1|9|
|Paltan Bazaar, Dehradun|Coarse Aggregate|m3|105|99.38|61.16|18.70|228.01|0.615|-1.736|0.905|0.858|0.849|0.837|0.667|4|9|
|Paltan Bazaar, Dehradun|PVC Pipes|pieces|105|60.57|60.85|8.00|224.00|1.005|1.641|0.904|0.903|0.880|0.850|1.295|10|4|
|Paltan Bazaar, Dehradun|Ready-Mix Concrete|m3|105|43.97|34.12|3.87|106.94|0.776|-0.946|0.890|0.870|0.862|0.817|0.605|4|8|
|Paltan Bazaar, Dehradun|River Sand|m3|105|75.17|35.38|20.80|145.55|0.471|-0.975|0.860|0.853|0.822|0.819|0.748|4|9|
|Paltan Bazaar, Dehradun|TMT Steel|kg|105|1409.20|1052.47|191.34|4151.88|0.747|-26.384|0.912|0.857|0.829|0.784|0.503|10|6|
|Paltan Bazaar, Dehradun|Tiles|m2|105|90.69|128.18|2.47|377.87|1.413|1.283|0.961|0.913|0.864|0.819|1.805|3|7|
|Sahastradhara Road, Dehradun|AAC Blocks|pieces|105|809.51|666.98|102.00|2398.00|0.824|5.078|0.921|0.895|0.886|0.847|0.715|3|8|
|Sahastradhara Road, Dehradun|Binding Wire|kg|105|63.06|50.33|6.52|154.60|0.798|-1.242|0.905|0.877|0.856|0.822|0.391|7|6|
|Sahastradhara Road, Dehradun|Bricks|pieces|105|4643.75|3335.90|744.00|11234.00|0.718|-11.399|0.913|0.869|0.843|0.797|0.300|11|9|
|Sahastradhara Road, Dehradun|Cement|50-kg bags|105|457.50|194.54|162.00|844.00|0.425|-5.175|0.860|0.855|0.831|0.785|0.298|1|6|
|Sahastradhara Road, Dehradun|Coarse Aggregate|m3|105|111.14|68.12|20.21|248.58|0.613|-1.895|0.882|0.850|0.828|0.808|0.586|1|8|
|Sahastradhara Road, Dehradun|PVC Pipes|pieces|105|70.47|72.06|11.00|238.00|1.023|1.930|0.922|0.886|0.879|0.856|1.311|11|1|
|Sahastradhara Road, Dehradun|Ready-Mix Concrete|m3|105|49.04|36.65|4.62|111.95|0.747|-1.046|0.925|0.905|0.884|0.860|0.612|4|6|
|Sahastradhara Road, Dehradun|River Sand|m3|105|86.52|40.81|18.07|162.17|0.472|-1.163|0.886|0.868|0.864|0.840|0.670|2|9|
|Sahastradhara Road, Dehradun|TMT Steel|kg|105|1599.83|1202.20|241.07|4642.91|0.751|-28.722|0.868|0.818|0.784|0.780|0.504|12|6|
|Sahastradhara Road, Dehradun|Tiles|m2|105|102.22|143.45|3.65|433.28|1.403|1.449|0.953|0.912|0.866|0.828|1.841|3|9|

## Price, lead-time and receipt diagnostics by site/material

Price levels are INR per recorded unit; early and late levels are means of the first and last 13 weekly rows. Price trend is the fitted linear change in INR per observed week. Stock cover is opening stock divided by that week's consumption; receipt/no-receipt values are medians within those weeks and are descriptive, not a documented reorder rule. Batch statistics use rows with `incoming_qty > 0`.

|Site|Material|Price early|Price late|Price trend/wk|Lead min|Lead median|Lead mean|Lead max|Receipt weeks|Batch mean|Batch median|Cover at receipt|Cover no receipt|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|Clement Town, Dehradun|AAC Blocks|65.90|66.21|0.0155|7|7.0|7.00|7|34|1987.76|1423.00|4.44|6.78|
|Clement Town, Dehradun|Binding Wire|78.86|79.12|0.0167|5|5.0|5.00|5|33|170.93|155.64|0.95|3.04|
|Clement Town, Dehradun|Bricks|9.09|9.18|0.0017|6|6.0|6.00|6|33|12140.64|10965.00|3.31|10.47|
|Clement Town, Dehradun|Cement|383.89|387.57|0.0879|4|4.0|4.00|4|31|1144.29|869.00|2.14|4.68|
|Clement Town, Dehradun|Coarse Aggregate|1353.69|1386.17|0.3902|4|4.0|4.00|4|35|272.84|244.75|5.03|7.33|
|Clement Town, Dehradun|PVC Pipes|224.05|223.18|0.0371|8|8.0|8.00|8|28|198.36|103.50|2.75|17.89|
|Clement Town, Dehradun|Ready-Mix Concrete|5265.21|5348.00|1.1806|2|2.0|2.00|2|35|124.44|110.42|3.12|4.65|
|Clement Town, Dehradun|River Sand|1527.61|1529.10|0.3585|5|5.0|5.00|5|32|234.38|231.75|3.00|4.90|
|Clement Town, Dehradun|TMT Steel|62.71|63.73|0.0141|7|7.0|7.00|7|33|4148.86|3655.42|2.26|9.53|
|Clement Town, Dehradun|Tiles|560.08|563.99|0.1047|10|10.0|10.00|10|26|328.47|66.16|29.88|46.70|
|GMS Road, Dehradun|AAC Blocks|65.99|66.87|0.0140|7|7.0|7.00|7|30|1728.27|1313.50|1.58|4.28|
|GMS Road, Dehradun|Binding Wire|79.56|79.57|0.0109|5|5.0|5.00|5|34|124.27|135.79|2.20|4.32|
|GMS Road, Dehradun|Bricks|9.09|9.15|0.0025|6|6.0|6.00|6|32|9290.47|10265.50|2.11|5.36|
|GMS Road, Dehradun|Cement|383.85|389.46|0.0899|4|4.0|4.00|4|34|834.29|798.00|1.33|3.41|
|GMS Road, Dehradun|Coarse Aggregate|1373.01|1389.30|0.2971|4|4.0|4.00|4|31|232.96|228.06|3.08|15.08|
|GMS Road, Dehradun|PVC Pipes|222.72|225.62|0.0425|8|8.0|8.0|8|28|157.71|68.00|6.78|17.26|
|GMS Road, Dehradun|Ready-Mix Concrete|5285.43|5305.41|1.1723|2|2.0|2.00|2|34|99.99|74.23|3.77|14.20|
|GMS Road, Dehradun|River Sand|1509.13|1543.88|0.3821|5|5.0|5.00|5|34|178.75|173.00|13.13|19.14|
|GMS Road, Dehradun|TMT Steel|62.74|63.40|0.0121|7|7.0|7.00|7|32|3276.30|2116.64|2.58|4.62|
|GMS Road, Dehradun|Tiles|553.79|565.15|0.1041|10|10.0|10.00|10|35|187.24|55.61|2.49|51.67|
|ISBT–Transport Nagar, Dehradun|AAC Blocks|66.12|67.08|0.0153|7|7.0|7.00|7|32|2084.59|1824.00|3.25|6.05|
|ISBT–Transport Nagar, Dehradun|Binding Wire|79.09|79.93|0.0175|5|5.0|5.00|5|32|173.66|152.19|3.35|5.30|
|ISBT–Transport Nagar, Dehradun|Bricks|9.11|9.18|0.0021|6|6.0|6.00|6|34|10885.29|9048.00|2.52|4.73|
|ISBT–Transport Nagar, Dehradun|Cement|382.99|388.51|0.0721|4|4.0|4.00|4|38|982.00|872.00|0.99|3.03|
|ISBT–Transport Nagar, Dehradun|Coarse Aggregate|1376.76|1382.80|0.1922|4|4.0|4.00|4|35|257.86|241.37|2.15|4.19|
|ISBT–Transport Nagar, Dehradun|PVC Pipes|223.52|225.50|0.0663|8|8.0|8.00|8|35|173.34|91.00|9.37|19.14|
|ISBT–Transport Nagar, Dehradun|Ready-Mix Concrete|5228.34|5313.69|1.2802|2|2.0|2.00|2|36|120.08|103.77|2.69|5.12|
|ISBT–Transport Nagar, Dehradun|River Sand|1536.44|1521.85|0.1384|5|5.0|5.00|5|38|186.72|194.04|0.84|2.52|
|ISBT–Transport Nagar, Dehradun|TMT Steel|62.32|63.51|0.0183|7|7.0|7.00|7|31|4233.46|4685.02|4.52|11.14|
|ISBT–Transport Nagar, Dehradun|Tiles|559.06|568.01|0.1565|10|10.0|10.00|10|31|326.22|68.43|52.13|67.79|
|Jakhan, Dehradun|AAC Blocks|66.01|66.30|0.0076|7|7.0|7.00|7|35|2130.63|1452.00|6.64|9.74|
|Jakhan, Dehradun|Binding Wire|79.42|79.84|0.0169|5|5.0|5.00|5|34|194.62|195.78|1.48|3.74|
|Jakhan, Dehradun|Bricks|9.18|9.15|0.0012|6|6.0|6.0|6|37|11687.81|6179.00|2.38|3.79|
|Jakhan, Dehradun|Cement|384.37|389.29|0.0875|4|4.0|4.00|4|36|1120.47|898.00|1.50|3.89|
|Jakhan, Dehradun|Coarse Aggregate|1367.52|1381.81|0.2524|4|4.0|4.00|4|35|307.46|259.98|1.24|3.78|
|Jakhan, Dehradun|PVC Pipes|222.07|226.87|0.0381|8|8.0|8.00|8|32|187.72|87.50|2.73|15.01|
|Jakhan, Dehradun|Ready-Mix Concrete|5321.06|5339.24|0.7750|2|2.0|2.00|2|38|131.73|118.60|1.36|2.93|
|Jakhan, Dehradun|River Sand|1509.93|1539.80|0.4258|5|5.0|5.00|5|35|235.67|223.44|1.18|3.15|
|Jakhan, Dehradun|TMT Steel|62.74|63.44|0.0123|7|7.0|7.00|7|36|4304.06|2460.69|0.97|2.67|
|Jakhan, Dehradun|Tiles|560.31|562.99|0.0640|10|10.0|10.0|10|25|378.70|100.85|2.23|37.29|
|Paltan Bazaar, Dehradun|AAC Blocks|65.88|66.29|0.0116|7|7.0|7.00|7|30|2480.97|2198.00|6.39|14.49|
|Paltan Bazaar, Dehradun|Binding Wire|79.03|79.79|0.0180|5|5.0|5.00|5|33|190.81|205.50|5.20|29.54|
|Paltan Bazaar, Dehradun|Bricks|9.16|9.29|0.0024|6|6.0|6.0|6|33|12329.36|9500.00|2.88|5.13|
|Paltan Bazaar, Dehradun|Cement|385.34|388.58|0.0818|4|4.0|4.0|4|35|1055.23|973.00|1.01|3.49|
|Paltan Bazaar, Dehradun|Coarse Aggregate|1372.32|1381.67|0.2403|4|4.00|4.00|4|36|278.33|225.62|1.37|3.09|
|Paltan Bazaar, Dehradun|PVC Pipes|224.92|223.66|0.0155|8|8.0|8.0|8|29|186.76|92.00|15.92|25.16|
|Paltan Bazaar, Dehradun|Ready-Mix Concrete|5238.41|5277.76|0.8333|2|2.0|2.0|2|34|128.54|116.09|1.18|3.98|
|Paltan Bazaar, Dehradun|River Sand|1528.19|1527.04|0.2233|5|5.0|5.0|5|35|219.96|205.61|1.40|3.07|
|Paltan Bazaar, Dehradun|TMT Steel|63.07|63.31|0.0111|7|7.0|7.0|7|27|5001.06|4734.40|6.94|11.48|
|Paltan Bazaar, Dehradun|Tiles|549.51|556.99|0.1464|10|10.0|10.0|10|28|302.58|60.67|15.82|38.01|
|Sahastradhara Road, Dehradun|AAC Blocks|65.70|66.53|0.0124|7|7.0|7.0|7|31|2747.94|2473.00|4.06|15.18|
|Sahastradhara Road, Dehradun|Binding Wire|79.19|79.99|0.0171|5|5.0|5.0|5|35|195.64|149.90|4.30|14.55|
|Sahastradhara Road, Dehradun|Bricks|9.03|9.21|0.0020|6|6.0|6.0|6|35|13393.63|13931.00|1.17|3.35|
|Sahastradhara Road, Dehradun|Cement|384.74|390.07|0.0885|4|4.0|4.0|4|32|1405.34|1369.50|7.77|10.40|
|Sahastradhara Road, Dehradun|Coarse Aggregate|1376.24|1385.50|0.3002|4|4.0|4.0|4|33|341.29|268.33|2.21|4.23|
|Sahastradhara Road, Dehradun|PVC Pipes|223.25|224.35|0.0647|8|8.0|8.0|8|30|233.43|102.00|1.17|13.35|

## Aggregate diagnostics (original CSV only)

|Metric|Median across pairs|Min|Max|
|---|---:|---:|---:|
|mean weekly demand|313.930|31.348|4,643.752|
|demand CV|0.752|0.413|1.449|
|acf1|0.914|0.848|0.961|
|acf2|0.877|0.810|0.913|
|acf3|0.851|0.760|0.893|
|acf4|0.818|0.699|0.862|
|seasonality|0.641|0.298|2.009|
|price_slope|0.064|0.001|1.280|
|lead_mean|5.500|2.000|10.000|
|batch_mean|305.021|99.989|13393.629|
|cover_receipt|2.709|0.840|52.134|
|cover_no_receipt|5.708|2.525|67.789|

Across all rows, supplier lead time: mean 5.80 days, median 5.5, range 2–10 days. Incoming quantity is positive on 1,967/6,300 rows (31.22%).

## External price plausibility check (read-only)

For each site/material pair, the CSV anchor below is the median `unit_price_inr` over its last 13 observations; the summary is the median of the six site-level medians. It was compared with opened Dehradun market references, including a page updated 2026-10-24; source dates and grades are not aligned with the 2025 CSV cutoff. This is a broad plausibility check, not a price update, procurement quote, or instruction to change the source.

| CSV material | CSV unit | Last-13 median across site medians | Opened local reference | Comparison |
|---|---|---:|---|---|
| Cement | 50-kg bags | ₹389.32/bag | ₹385–428 PPC; ₹407–449 OPC 43; ₹428–471 OPC 53 per 50-kg bag | Close to PPC low end; grade is not present in the CSV. |
| TMT Steel | kg | ₹63.48/kg | ₹62–68/kg for Fe500D | Within the listed band. |
| Bricks | pieces | ₹9.16/piece | ₹7–10 per red-clay piece | Within the listed band; the CSV does not identify brick grade. |
| AAC Blocks | pieces | ₹66.48/piece | ₹74–111 per 600×200×200-mm block; other sizes/listings differ | About 10% below the lower edge of that size-specific range, inside a ±15% comparison band; CSV block dimensions are unspecified. |
| Tiles | m² | ₹563.23/m² (≈₹52.33/sq.ft) | Dehradun references span ceramic wall tiles ₹26–57/sq.ft and vitrified floor tiles ₹62–112/sq.ft; local listings vary by model | Within the ceramic-wall range, below the vitrified-floor range. The CSV does not identify tile type/grade, so no single-grade conclusion is justified. |
| River Sand | m³ | ₹1,523.61/m³ | Opened local reference quotes per tonne and per 100 CFT | Not directly comparable without a verified density/moisture and delivery basis. |
| Coarse Aggregate | m³ | ₹1,383.61/m³ | Opened local reference quotes per tonne by size | Not directly comparable without a verified bulk-density/size and delivery basis. |

Sources opened: [InfraLens Dehradun material-price page](https://infralens.in/prices/dehradun) (updated 2026-10-24); [InfraLens cement](https://infralens.in/prices/cement/dehradun) and [sand/aggregates](https://infralens.in/prices/aggregates/dehradun) pages (updated 2026-10-24); [IndiaMART Dehradun TMT listings](https://dir.indiamart.com/dehradun/tmt-bars.html); [IndiaMART Dehradun brick listings](https://dir.indiamart.com/dehradun/bricks.html); [IndiaMART Dehradun AAC listings](https://dir.indiamart.com/dehradun/autoclaved-aerated-concrete-block.html); and [TileFinders Dehradun tile listings](https://tilesfinders.com/dehradun/tile-store). A separately opened [TodayPriceRates Dehradun page](https://property.todaypricerates.com/construction-building-materials-rate-in-Dehradun) showed inconsistent cement figures between its table and explanatory text; it was not used as the cement point reference.

These read-only price comparisons did not alter the source CSV or ledger. The original-only diagnostic tables above describe only the 6,300 original source rows, not the separately tagged extension or operational ledger.

## Deterministic extension and operational sample ledger

The original CSV remains the 14-column, 6,300-row source described above. A separate `data/Dehradun_Inventory_Dataset_Sample_Extension.csv` contains 2,640 additional weekly rows: 44 for each of the same 60 pairs, dated 2026-01-05 through 2026-11-02. Every row is tagged `sample_extension`; the generator is deterministic, checks weekly continuity, limits unit-price movement to ±15% of the recent anchor, and reconciles nonnegative opening + incoming − consumption quantities.

The retained observation table contains 8,940 rows: 6,300 `historical_csv` and 2,640 `sample_extension`. The operations loader created 60 tagged sample opening counts, 630 sample receipts, 2,640 sample sales and linked consumption movements, 30 generic Indian business names with blank email/phone, and 60 tagged reorder rules. Every weekly sample close reconciles to the extension. Opening and receipt costs use deterministic 82–93% fractions of the corresponding week's extension unit price; these synthetic inputs provide FIFO stock value, COGS and gross margin. The current reorder snapshot has 52 pairs at/above their reorder point, 8 below, and 0 zero/negative balances. The two lowest weeks-of-cover are approximately 2.17 and 2.26; no pair is at physical stock-out.
