# Progress

Updated 2026-11-02 (Asia/Kolkata). The original source CSV is preserved byte-for-byte.

This progress note is an archived implementation snapshot. Its preview-server status is not current; recent verification attempts and limitations are in [`TEST_RESULTS.md`](../TEST_RESULTS.md).

## Completed

- Schema v3 migration is additive. The database contains 8,940 observations: 6,300 `historical_csv` and 2,640 `sample_extension` rows through 2026-11-02.
- The idempotent operations loader contains 60 openings, 630 receipts, 2,640 sales/consumption movements, 30 generic Indian business customers, and 60 reorder rules. All operational sample rows are tagged `sample_ledger` in the DB.
- Deterministic opening/receipt costs are 82–93% of that week's extension unit price. FIFO inventory value, COGS, and gross margin are available for sample operations.
- Loader rerun reported the same totals and reconciled all 60 pairs; extension rerun recognized the existing 2,640 rows and inserted no duplicate file.
- Reorder snapshot: 52 at/above point, 8 below, 0 at/under zero. No balance is negative. Two lowest weeks-of-cover are about 2.17 and 2.26, so there are no physical near-stock-outs.
- Forecasting now explains WAPE as the headline error and R² against the holdout average; best model and WAPE are surfaced above the metric table.
- Retrained five models across 60 extended series: 300 new artifacts, 0 issues, 129.63 seconds; prior 300 artifacts remain (600 total).
- Browser form QA on `data/browser_qa_copy.db`: receipt, sale, and adjustment posted through the UI. Dashboard moved from 1 sale/₹34,753 revenue/₹5,068.62 margin to 2/₹34,833/₹5,080.67 after the sale. QA records are isolated from the retained database.
- `tests/test_sample_data_pipeline.py`: 1 passed. `tests/test_inventory.py`: 3 passed. A full pytest run was stopped at the user's request to free time before completion.
- Preview server remains running on 127.0.0.1:8000 against the QA copy.

## Limitations

- The requested approximate 6–10 below-reorder count and nonnegative stock condition are met. Existing generated closing balances leave two lowest pairs with over two weeks of cover; the loader does not invent physical stock reductions just to label them near stock-out.
- Full pytest suite was not completed in this fast pass.
