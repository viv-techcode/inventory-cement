# Viva Questions and Answers

1. **What problem does SiteStock address?**  
   It records material stock movements and connects balances with sales, replenishment, purchasing, and demand analysis.

2. **What did you do to the dataset prices?**  
   I rebased only historical unit prices to dated Dehradun dealer-to-retail reference estimates, with explicit unit conversions, site factors, seasonal factors, and small deterministic variation. The original measured quantities and stock chain were preserved. Prices are indicative, not invoices; details are in the price-source note.

3. **How many observations are there?**  
   8,940 rows across 60 site/material pairs, 149 observations per pair.

4. **What is one series?**  
   One material at one project-site identifier, ordered by date.

5. **What does consumption_qty measure?**  
   Quantity consumed during the weekly observation period, in that material's unit.

6. **What is opening_stock_qty?**  
   The stock at the start of the observation period, in that material's unit.

7. **How do you check stock flow?**  
   Calculated closing stock is opening plus incoming minus consumption; it should match the next observation's opening stock.

8. **Were any values changed during the audit?**  
   Unit prices were rebased as requested. Demand, opening stock, incoming, consumption, dates, units, and identity fields were retained; all stock-flow checks still pass. The 250 IQR flags remain because a statistical flag alone is not evidence of a bad measurement.

9. **What is the natural key?**  
   Date, project_site_id, and material together identify one observation.

10. **Why is wpi_reference_month not an inflation value?**  
   It stores only a YYYY-MM month key; no index number is present.

11. **What is the prediction target?**  
   Weekly aggregated consumption quantity for one site/material pair.

12. **Why use a time split?**  
   Forecasts are for future periods, so training on later periods would not represent deployment.

13. **What is data leakage?**  
   Using information that would not be available at the forecast origin, such as future targets or transformations fit on the test period.

14. **How do you prevent lag leakage?**  
   Each lag and rolling feature is computed from observations strictly before the period being predicted.

15. **How do you select a model?**  
   Mean MAE across three expanding-window rolling origins before the final holdout.

16. **What is the final holdout for?**  
   It provides a separate chronological diagnostic after model selection; it is not used to choose the model.

17. **Why include Naive?**  
   It is a transparent baseline that predicts the last observed value and prevents a complicated model from looking good without comparison.

18. **What is Seasonal Naive?**  
   It predicts from the value one seasonal cycle earlier; for weekly data the cycle is 52 periods.

19. **Do ML models clearly beat Naive?**  
   No. Naive was selected for 39 of 60 pairs under the validation rule, and aggregate model results do not support a broad improvement claim.

20. **Why might ML not beat Naive?**  
   Each series has limited history, patterns may not persist, and the available features may not explain short-term demand changes.

21. **What does MAE mean?**  
   The average absolute forecast error in the material's quantity unit.

22. **What does RMSE emphasize?**  
   It squares errors before averaging, so large misses have more influence.

23. **What is WAPE?**  
   Sum of absolute errors divided by sum of absolute actual demand, expressed as a percentage.

24. **Why not pool MAE across materials?**  
   The series use incompatible units such as kilograms, bags, pieces, and cubic metres.

25. **How is feature importance computed?**  
   The API exposes Random Forest tree impurity importance for lag 1–4, rolling mean, and rolling standard deviation; it describes model association, not causation.

26. **How is the displayed prediction interval formed?**  
   It uses the 90th percentile of absolute rolling-origin errors before the final holdout and applies a symmetric band clipped at zero.

27. **Does the interval guarantee 90% future coverage?**  
   No. It is an empirical calibration aid; future coverage is not guaranteed.

28. **What is MASE?**  
   Mean absolute error divided by the training-period seasonal-naive error scale. Values below one indicate lower error than that scale on the scored period; MASE is dimensionless.

29. **How is safety stock computed?**  
   `z × forecast-error sigma × √lead-time weeks`. The chosen service level (90%, 95%, or 98%) sets z.

30. **How is reorder demand calculated?**  
   Forecast weekly demand is multiplied by lead weeks, safety stock is added to form the reorder point, and the order-up-to gap accounts for on-hand stock and eligible incoming. EOQ is a separate candidate; minimum quantity and pack rounding follow.

31. **What happens if stock is unknown?**  
   The system withholds a numeric stock-aware recommendation and requests a physical count.

32. **Why can incoming quantity be excluded?**  
   It must match the material unit, have an eligible status, have an expected date, and arrive within the lead-time window.

33. **How does an order multiple work?**  
   A positive net quantity is rounded upward to the next configured multiple after applying the minimum quantity.

34. **What is a maximum-stock conflict?**  
   The recommended post-order balance would exceed the configured maximum, so the system flags the conflict instead of silently capping.

35. **How are sales margins computed?**  
   Revenue minus FIFO cost of goods sold, only when a complete recorded cost basis exists.

36. **Why are some margins unavailable?**  
   One or more remaining cost layers may lack a recorded unit cost; the application does not invent cost from a reference price.

37. **What is idempotency?**  
   Repeating the same request key does not create a duplicate transaction.

38. **What protects against duplicate observations?**  
   Unique natural-key constraints and duplicate checks on site/material/date.

39. **How do foreign keys help?**  
   They ensure transactions and sales reference existing sites, materials, customers, and linked records.

40. **What is the difference between history and the operational ledger?**  
   History supports quality and forecasting; only explicit ledger transactions define current operational stock.

41. **Why does the app block stale recommendations?**  
   Old demand observations cannot support a current replenishment quantity without a fresh source.

42. **How do you back up SQLite?**  
   Use SQLite's online backup API or a consistent database backup before schema/data changes; copying a live WAL database file alone may be incomplete.

43. **Is migration rerunnable?**  
   The initialization and migration logic checks current columns/schema version and is designed to be idempotent.

44. **What are the main dataset limitations?**  
   The series are short, key supplier and project variables are absent, and the month field is not an external index.

45. **How should the policy simulation be interpreted?**  
   As a retrospective holdout replay across 60 series. At 20% holding cost and 2× unit-value shortage penalty, the selected-model policy averaged 92.59% fill and ₹588,380 total cost per series. The rates and rebased unit prices are assumptions, so this is a sensitivity study, not observed savings.

46. **What is future work?**  
   Collect verified site-level demand, supplier, receipt, price, carrying-cost, and shortage-cost records, then re-evaluate models and inventory policies.

47. **What should the user do before acting on an order suggestion?**  
   Verify the physical stock, supplier lead time, eligible pipeline, unit, and configured order constraints.

48. **Why use a database as well as CSV?**  
   The CSV is historical analysis input; SQLite stores operational transactions and validated imports with constraints and transaction boundaries.

49. **How is API validation handled?**  
   Pydantic request schemas and service-level checks return structured 4xx errors for invalid values and missing catalogue items.

