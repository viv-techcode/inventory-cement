# Brainstorming Log

## Task 2: Step 1.5 Forecasting Sparsity & Model Granularity

### Options Considered
1. **Direct site/material level (90 series) exclusively:**
   - *Pros:* Direct correspondence between each series and individual site stock.
   - *Cons:* 81 of 90 series are classified as Lumpy under Syntetos-Boylan (mean zero weeks ~50%, mean ADI 2.14, CV^2 0.88). Median holdout WAPE exceeds 100%, and ML models beat Naive on fewer than half of the series.
2. **Material-level forecasting (15 series) with proportional top-down site allocation:**
   - *Pros:* Material-level series aggregate volume to smooth/erratic patterns (0 lumpy series, zero weeks <6%, CV < 0.9). Models achieve median holdout WAPE of 45.88% (Ridge) vs 55.63% (Naive), clearly beating the baseline.
   - *Cons:* Requires allocating predicted material demand across the 6 sites based on historical site sales share.
3. **Hybrid presentation with material-level accuracy as primary and direct series as operational:**
   - *Pros:* Completely honest about intermittent site demand characteristics while providing high-accuracy material totals for procurement and inventory planning.
   - *Cons:* Must clearly explain the distinction in UI and documentation.

### Decision
Option 3 (Hybrid with Top-Down / Material-level accuracy surfaced prominently).
- Direct series are preserved for site-specific replenishment calculations, but material-level metrics and top-down distribution are reported as the primary ML benchmark.

---

## Task 3: Step 2A Dataset Generator Realism (`scripts/build_ledger.py`)

### Problem & Objectives
The original generator had several unrealistic artifacts:
1. Exact zero-variance margins across customers (all sold at exact `anchor * trend / (1 - margin)`).
2. All 28 adjustments formed 14 cancelling pairs (`+qty` followed by `-qty` next day) netting zero.
3. Uniform supplier assignments (any supplier supplied any material, e.g. cement maker supplying bricks).
4. Equal customer revenue distribution (random draw across 30 customers, no top-10 concentration).
5. No March 2025 steel margin squeeze.
6. Uniform inventory turns and days of cover across fast and slow movers.
7. Uniform site sales distribution with no distinct site mix personality (ISBT bulk vs Paltan retail).
8. No distinct stock-out weeks or delayed purchase orders.

### Options Considered
1. **Ad-hoc manual adjustments in CSV:**
   - *Pros:* Quick fixes to specific numbers.
   - *Cons:* Violates reproducibility rule; builder script would not match CSV; fragile.
2. **Stochastic simulation without deterministic seeds:**
   - *Pros:* Natural variability.
   - *Cons:* Not reproducible across runs; violates hard constraint.
3. **Structured deterministic generator revision in `scripts/build_ledger.py`:**
   - *Pros:* Fully reproducible from fixed seed (`SEED = 20260702`), strictly respects hard constraints (8,490 rows, date range 2024-04-01 to 2026-07-02, 6 sites, 15 SKUs, zero negative stock, ex-GST INR), embeds genuine domain dynamics (customer tiers, site specializations, supplier matrices, realistic turns).
   - *Cons:* Requires careful constraint solving to keep exact row count and nonnegative stock.

### Decision & Implementation Plan
Option 3: Revise `scripts/build_ledger.py` deterministically:
- Customer tiers: assign customer weights (Pareto 80/20 power law so top 10 represent ~50% revenue), volume discount tiers (1-4%), and dealer margin variations.
- Steel squeeze (March 2025): elevated raw material input costs compressing gross margins to 2-4%.
- Specialized suppliers: assign each supplier only appropriate categories (Cement to Uttarakhand Cement, Steel to North Plains Steel, Aggregates to Doon Valley Aggregates & Ganga Valley Minerals, Bricks/Tiles to Shivalik Building Products & Himalayan Construction Supplies).
- Meaningful adjustments: non-zero net adjustments (breakage, spillage, count reconciliation) with proper business justification.
- Site personalities: ISBT has heavy commercial bulk (TMT steel, cement bags, bulk aggregates); Paltan Bazaar has retail hardware/finishing (binding wire, tile adhesive, waterproofing); Clement Town & Jakhan residential.
- Inventory velocity: fast movers (cement, steel) turn 12-18x/yr; slow movers (chemicals, wire) turn 4-7x/yr.
- Supplier delay: at least 1 PO received 7+ days late; at least 3 stock-out weeks.
