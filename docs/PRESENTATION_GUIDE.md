# Presentation Guide

## Proposal feature map

| Proposal feature | Application page | Live metrics / Capabilities |
|---|---|---|
| Revenue, margin, stock value and alerts | Dashboard | Company-level revenue ₹13.50 Cr, gross margin ₹1.40 Cr (10.37%), 46 reorder alerts, ₹36.67 L stock value |
| Site and material balances, coverage and stock movement | Inventory | 90 site/material pairs, physical opening balances, real-time balance computation, ex-GST unit cost basis |
| Customer sales, cost and margin | Sales | 7,932 posted customer invoices, top-10 customer concentration (~51.9%), customer discount tiers, weighted-average COGS |
| Weekly holdout, residuals and forward estimates | Forecasting | 90 site/material series evaluated across 5 model families, 16-week holdout, walk-forward folds, empirical coverage |
| Lead-time demand, safety stock and order quantities | Replenishment | Transparent 11-step reorder calculation, historical demand rate, lead-time variance, minimum order & pack constraints |
| Purchase orders, approvals and receipts | Purchasing | 28 purchase orders, 4-stage lifecycle (Draft → Pending approval → Approved → Received), GRN receipt tracking |
| Ledger counts, quality checks and downloadable reports | Data & Reports | 8,490 canonical events, stock roll-forward validation, zero negative balance proof, CSV & Excel workbooks |

## Five-minute walkthrough

1. **Dashboard (Company-wide Overview):**
   - Review top-level KPIs on initial load: company sales revenue (₹13,49,99,624.99 ex-GST across 7,932 sales), recorded gross margin (₹1,39,98,297.34, 10.37%), active pairs (90), initialized stock lines (90), low-stock lines (46), and fully costed stock valuation (₹36,67,330.83).
   - Point out the fixed operational date (`Data through 2 Jul 2026`).
   - Demonstrate optional filtering: select site `ISBT-Transport Nagar, Dehradun` or material `TMT Fe500D 10 mm` to see focused trend lines.

2. **Sales & Margin Analysis:**
   - Navigate to the **Sales** tab. Observe commercial sales volume and margins.
   - Point out March 2025 steel margin compression (2.44% vs standard ~6.0%) caused by the raw material price surge.
   - Test recording an operational sale: select site, material, customer, quantity, and unit price. Confirm stock decreases on the live ledger and revenue/COGS update immediately.

3. **Replenishment Planning:**
   - Open **Replenishment**. Select a site and material (e.g., `Clement Town, Dehradun` / `OPC Cement`).
   - Walk through the transparent 11-step math: live ledger balance, lead-time demand, safety stock reserve (95% service factor), net requirement, and pack-size rounding.
   - Click "Create purchase order from recommendation" to draft an order.

4. **Purchasing & Goods Receipt Flow:**
   - Open **Purchasing**. Explain the mandatory 4-stage procurement workflow:
     Draft → Pending approval → Approved → Received
   - Review PO-0027 (Draft), PO-0025 (Pending approval), PO-0026 (Approved), and PO-0012 (Delayed receipt: received 14 days after expected delivery).
   - Transition the newly drafted order from Draft to Pending approval, then Approved.
   - Receive items against an approved purchase order line with a valid GRN reference; verify that live on-hand stock increases in the inventory ledger.
   - *Purchase Order Structure:* 24 historical master orders organize 440 receipt lines across specialized suppliers (1-6 lines per order), supplemented by 4 forward planning orders (PO-0025 to PO-0028) demonstrating open, approved, draft, and cancelled states.

5. **Demand Forecasting & Holdout Inspection:**
   - Open **Forecasting**. Inspect the chronological model comparison for a selected series.
   - Highlight the 16-week holdout evaluation, expanding-window walk-forward folds, empirical prediction interval coverage (~84%), and residual diagnostics (mean, standard deviation, lag-1 autocorrelation).
   - Discuss intermittent demand: explain why site-level series exhibit lumpy demand while aggregated material-level series yield smooth forecasts with ~45.9% WAPE.

6. **Data Quality & Audit Trail:**
   - Open **Data & Reports**.
   - Review the ledger checks table: 8,490 unique continuous event IDs (`L000001` to `L008490`), single unit per material pass, and stock roll-forward pass with zero negative balances.
   - Demonstrate downloading operational reports and the multi-tab Excel workbook.

## Viva questions & answers

1. **Why compare multiple forecasting model families?**
   Different demand patterns respond differently: naive and seasonal naive serve as transparent, leakage-free reference baselines; multiple linear regression captures trend and seasonality; tree models (Random Forest, XGBoost) capture nonlinear calendar and lagged relationships.

2. **How is information leakage prevented in the forecasting pipeline?**
   Data are split chronologically with a strict 16-week holdout. All rolling and lag features are computed from past observations only. Normalizers and scalers are fit strictly on training windows. Model selection uses pre-holdout rolling-origin validation folds.

3. **How is safety stock calculated?**
   Safety Stock = Z × standard deviation of demand × sqrt(Lead Time), where Z = 1.645 for a 95% cycle service level.

4. **Why use WAPE and MASE instead of MAPE?**
   Intermittent construction demand often has zero sales in a given week. Mean Absolute Percentage Error (MAPE) divides by actual volume, causing division by zero or explosive values. Weighted Absolute Percentage Error (WAPE) scales total absolute error by total actual demand. Mean Absolute Scaled Error (MASE) scales errors against an in-training naive baseline.

5. **How are forecast prediction intervals generated?**
   Intervals are constructed empirically using the standard deviation and quantile spread of historical validation residuals, guaranteeing realistic uncertainty bands rather than theoretical normal assumptions.

6. **Why do site-level series exhibit higher forecast error than material-level totals?**
   Under Syntetos-Boylan classification, 81 of 90 site/material series are "Lumpy" due to intermittent ordering by local contractors. Aggregating to material level combines uncorrelated demand across sites, eliminating intermittency and improving holdout WAPE from >100% to 45.88%.

7. **How does weighted-average costing handle inventory valuation?**
   In accordance with IAS 2, each inbound receipt establishes or adjusts the moving weighted-average acquisition cost per unit. Outbound sales relieve inventory at the prevailing weighted average cost, ensuring exact matching of revenue and Cost of Goods Sold without arbitrary cost imputation.

8. **What does the March 2025 steel margin squeeze demonstrate?**
   It reflects authentic industry market behavior: in March 2025, raw steel ingot and scrap input costs rose, but competitive retail dealer prices could not adjust immediately, squeezing gross margins from ~6.0% down to 2.44%.

9. **How are stock adjustments structured in the ledger?**
   The 28 ledger adjustments represent physical inventory reality (breakage, moisture damage, yard survey tare reconciliations). They have net non-zero impact (-67.10 units), preventing artificial cancelling artifacts.

10. **How does the application ensure idempotency and prevent duplicate records?**
    Every transaction, sale, purchase order, and receipt accepts a unique `idempotency_key`. Submitting the same key twice returns the existing record rather than creating a duplicate or debiting stock twice.

11. **What happens during application reset?**
    `scripts/reset_database.py` drops and recreates SQLite schema tables idempotently from `data/construction_materials_ledger.csv`, reloading 8,490 events, 28 purchase orders, 90 replenishment reviews, and committed forecast metrics without needing to retrain models on boot.

12. **How is cross-site personality reflected in customer sales?**
    ISBT-Transport Nagar caters to heavy infrastructure and commercial projects (median sale ₹20,284; 46.6% steel share); Paltan Bazaar caters to dense retail hardware and finishing (median sale ₹5,224; 32.2% chemical/accessory share); Clement Town and Jakhan represent residential building.

**Data-origin response:** [To be supplied by the project owner.]

