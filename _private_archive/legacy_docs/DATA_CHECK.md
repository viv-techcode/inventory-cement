# Data Check

The active canonical CSV has 8,940 rows, 16 columns, and 60 site/material series. It has no missing values or duplicate natural keys; calculated closing stock is nonnegative and all 8,880 adjacent stock-chain checks pass at 1e-6 tolerance. Only historical unit prices were rebased; measurement quantities were preserved. See `DATASET_AUDIT.md` for the price bands, hash, and validation details.
