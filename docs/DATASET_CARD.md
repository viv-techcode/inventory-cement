# Data Card

## Coverage

- File: `data/construction_materials_ledger.csv`
- Rows: 8,490 events
- Date range: 2024-04-01 to 2026-07-02
- Sites: six Dehradun locations
- Materials: 15 sellable SKUs
- Event categories: opening balance, sale, purchase receipt, stock adjustment
- Recorded price basis: INR per material unit, ex-GST

## Columns and units

| Column | Meaning and unit |
|---|---|
| event_id | Continuous ledger identifier |
| date | Calendar date |
| site | Dehradun location |
| material | Sellable SKU |
| unit | Unit used by the SKU |
| quantity | Units moved; adjustments may be signed |
| unit_price | INR per unit; sales price or reference value |
| unit_cost | INR per unit acquisition cost |
| document_reference | Invoice, PO, GRN, opening, or adjustment reference |
| counterparty | Customer, supplier, or balance/adjustment description |
| event_type | Opening balance, sale, purchase receipt, or adjustment |

Units: OPC/PPC cement, 50 kg bag; TMT diameters, kg; clay bricks, 1,000 bricks; river sand and M-sand, m³; 10 mm and 20 mm aggregate, m³; binding wire, kg; tile adhesive, 20 kg bag; SBR waterproofing compound, litre.

## Quality checks

The ledger builder checks its exact row count, date bounds, event mix, and nonnegative running stock by site and material. The final acceptance audit also checks sequential IDs, required site names, unit consistency, reproducibility, and cross-page reconciliation. Quality summaries appear in the application Data & Reports page.
