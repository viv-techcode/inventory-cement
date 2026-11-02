# Verification Results

Verified on 2026-11-02 (Asia/Kolkata). The original CSV remains unchanged. QA browser forms ran against a SQLite backup, not the retained DB.

## Focused checks

- `python -m pytest tests/test_sample_data_pipeline.py -q` — **1 passed**. Covers deterministic extension, source integrity, deterministic 82–93% unit costs, FIFO margin, generic blank-contact customers, reorder alert tuning, and repeat-load idempotency.
- `python -m pytest tests/test_inventory.py -q` — **3 passed**.
- `python -m scripts.extend_dataset` — recognized the existing 2,640 rows for 2026-01-05–2026-11-02; duplicate file, 0 duplicate rows.
- `python -m scripts.load_operations` — reconciled all 60 pairs and reported 60 openings, 630 receipts, 2,640 sales movements, 30 customers and 60 reorder rules.
- `python -m scripts.train_all_models` — 60/60 pairs, 300 artifacts, 0 issues, 129.63 seconds; 600 total retained forecast artifacts.
- Full `python -m pytest -q` was interrupted at the user's request after it exceeded the available time; no full-suite pass is claimed.

## Data integrity and stock

- Original CSV SHA-256: `828d9354e47661e28b7b668cb80925c5d54f2501caa2b9960aed1e1efaa3f39c`; 6,300 rows × 14 columns.
- Extension: 2,640 rows, through 2026-11-02. Observation DB: 8,940 rows (6,300 historical + 2,640 extension).
- Costed layers: 60 opening counts and 630 receipts; sample sales have complete FIFO COGS and margin.
- Customer directory: 30 generic Indian business names; email/phone blank; no `Sample` names.
- Stock/reorder status: 52 at/above reorder, 8 below, 0 zero/negative. Two lowest weeks-of-cover are 2.17 and 2.26; no near physical stock-out.

## Browser QA and preview

Receipt, Sale, and Adjust were submitted through the real forms on a copied DB. Dashboard totals moved from 1 sale/₹34,753 revenue/₹5,068.62 margin to 2 sales/₹34,833/₹5,080.67. See [`docs/BROWSER_QA.md`](docs/BROWSER_QA.md). The preview remains running at `http://127.0.0.1:8000/` against the QA copy.
