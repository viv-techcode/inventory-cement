"""Evaluate pooled weekly candidates and write JSON/Markdown results.

Run with ``python -m scripts.train_pooled`` after the observation table contains
the configured dataset. The script
reads the configured database and writes only docs/pooled_results.json and the
generated pooled-results section of docs/MODEL_RESULTS.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from inventory_app import config
from inventory_app.data_quality import history_to_frame
from inventory_app.database import Database
from inventory_app.pooled_forecasting import evaluate_pooled

BEGIN = "<!-- BEGIN GENERATED POOLED RESULTS -->"
END = "<!-- END GENERATED POOLED RESULTS -->"


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _table_rows(label: str, summary: dict[str, Any]) -> list[str]:
    rows = []
    for metric in ("mae", "rmse", "r2", "wape_pct"):
        values = summary.get(metric, {})
        suffix = "%" if metric == "wape_pct" else ""
        rows.append(
            f"| {label} | {metric.upper().replace('_PCT', '')} | "
            f"{_fmt(values.get('mean'))}{suffix} | {_fmt(values.get('median'))}{suffix} |"
        )
    return rows


def _render_markdown(result: dict[str, Any]) -> str:
    if result.get("status") != "evaluated":
        return (
            "Pooled results have not been generated. Run `python -m scripts.train_pooled` "
            "to evaluate the pooled candidates without using the holdout for selection."
        )
    pooled_count = result["pooled_selected_series"]
    total = result["series_count"]
    if result["pooled_beats_naive_in_most_series"]:
        conclusion = f"Pooled models beat Naive on the selection backtest in most series ({pooled_count}/{total})."
    else:
        conclusion = f"Pooled models do not beat Naive in most series: a pooled model was selected for {pooled_count}/{total}; the rest fall back to Naive."
    lines = [
        "Pooled transform selection uses macro-mean per-series backtest MAE across the three expanding folds. Each series then uses its best pooled model only when that model's backtest MAE is strictly lower than Naive; otherwise the result falls back to Naive. Final holdout metrics below are diagnostics only.",
        "",
        f"**Selection outcome:** {conclusion}",
        "",
        "### Overall before/after holdout metrics",
        "",
        "Mean and median are calculated across the per-series holdout metrics; MAE and RMSE remain in each series' unit.",
        "",
        "| Scenario | Metric | Mean | Median |",
        "|---|---|---:|---:|",
        *_table_rows("Before · Naive", result["overall"]["before_naive"]),
        *_table_rows("After · pooled or Naive fallback", result["overall"]["after_pooled_or_naive"]),
        "",
        "### Before/after holdout metrics by material",
        "",
        "| Material | Scenario | Metric | Mean | Median |",
        "|---|---|---|---:|---:|",
    ]
    for material, data in result["per_material"].items():
        for scenario, key in (("Before · Naive", "before_naive"), ("After · pooled or Naive fallback", "after_pooled_or_naive")):
            for row in _table_rows(scenario, data[key]):
                _, metric, mean, median = row.strip("|").split("|")
                lines.append(f"| {material} | {scenario} |{metric}|{mean}|{median}|")
    lines += [
        "",
        "Transform chosen per model by backtest MAE (holdout excluded):",
        "",
        "| Pooled model | Transform | Macro-mean backtest MAE |",
        "|---|---|---:|",
    ]
    for name, selected in sorted(result["transform_selection"].items()):
        lines.append(f"| {name} | {selected['transform']} | {_fmt(selected['backtest_mae_macro_mean'])} |")
    if result.get("unavailable_candidates"):
        lines += ["", "Unavailable candidates: " + "; ".join(f"{key}: {value}" for key, value in sorted(result["unavailable_candidates"].items()))]
    lines += ["", f"Evaluation window: {result['calendar_periods']} calendar weeks; untouched holdout {result['holdout_start']} through {result['holdout_end']}. See `pooled_results.json` for series-level model choice, fold scores, and metrics."]
    return "\n".join(lines)


def _write_results(result: dict[str, Any], docs_dir: Path) -> None:
    json_path = docs_dir / "pooled_results.json"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    model_results = docs_dir / "MODEL_RESULTS.md"
    content = model_results.read_text(encoding="utf-8")
    generated = _render_markdown(result)
    section = f"{BEGIN}\n{generated}\n{END}"
    if BEGIN in content and END in content:
        before, tail = content.split(BEGIN, 1)
        _, after = tail.split(END, 1)
        content = before + section + after
    else:
        content += f"\n\n## Pooled-model before/after results\n\n{section}\n"
    model_results.write_text(content, encoding="utf-8")


def main() -> int:
    database = Database(config.DATABASE_URL)
    try:
        with database.session() as session:
            history = history_to_frame(session)
    finally:
        database.dispose()
    if history.empty:
        print("No imported observations found; no pooled evaluation was written.", file=sys.stderr)
        return 2
    try:
        result = evaluate_pooled(history)
    except Exception as exc:
        print(f"Pooled evaluation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    result["dataset"] = {"row_count": int(len(history))}
    _write_results(result, Path(__file__).resolve().parents[1] / "docs")
    print(
        f"Wrote pooled results for {result['series_count']} series; pooled selected in "
        f"{result['pooled_selected_series']} series (Naive fallback in "
        f"{result['series_count'] - result['pooled_selected_series']}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
