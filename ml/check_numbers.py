"""Fail when documented forecast WAPE percentages disagree with saved results."""
from pathlib import Path
import re
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    results = pd.read_csv(ROOT / "results" / "model_results.csv")
    holdout = results.loc[results.period.eq("holdout")]
    expected = {}
    selected = holdout.loc[holdout.selected_on_validation.astype(bool)]
    for level, model_rows in selected.groupby("level"):
        volume = model_rows.actual_volume.sum()
        expected[level] = float(model_rows.absolute_error_sum.sum() / volume * 100)
    docs = [ROOT / "README.md", ROOT / "docs" / "PRESENTATION_GUIDE.md"]
    errors = []
    for path in docs:
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?P<value>\d+(?:\.\d+)?)\s*%\s*(?P<level>material-level|site/material-level)\s*WAPE", content, re.I):
            value = float(match.group("value"))
            level = "site_material" if match.group("level").lower().startswith("site/") else "material"
            target = expected.get(level)
            if target is None or round(value, 2) != round(target, 2):
                errors.append(f"{path.relative_to(ROOT)}: {value:.2f}% does not match saved selected {level} holdout WAPE ({target})")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Documented forecast WAPE numbers match results/model_results.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
