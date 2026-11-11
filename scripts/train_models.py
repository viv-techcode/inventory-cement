"""Evaluate and persist weekly forecast artifacts for each observed site/material pair.

Run from the repository root with ``python -m scripts.train_models`` after the
canonical dataset has been imported. Training does not alter observations or
create operational ledger entries.
"""
from __future__ import annotations

import sys
import time
import json
import argparse
from pathlib import Path

from inventory_app import config
from inventory_app.data_quality import history_to_frame
from inventory_app.database import Database, initialize_database
from inventory_app.forecasting import available_models, evaluate_model_suite, load_saved_assessment, persist_assessment
from scripts.load_operations import ensure_baseline_planner_history, ensure_ledger_baseline
from inventory_app.models import ForecastArtifact
from inventory_app.forecasting import MODEL_VERSION
from sqlalchemy import select


def refresh_metrics_only() -> int:
    """Enrich the latest per-series file from saved current-version DB metrics."""
    path = config.PROJECT_ROOT / "docs" / "model_metrics.json"
    if not path.exists():
        print("No docs/model_metrics.json exists to refresh.", file=sys.stderr)
        return 2
    document = json.loads(path.read_text(encoding="utf-8"))
    current_hash = __import__("hashlib").sha256(config.SOURCE_CSV.read_bytes()).hexdigest()
    if document.get("dataset_sha256") != current_hash:
        print("Metrics file is for a different dataset hash; run the complete offline training command.", file=sys.stderr)
        return 2
    db = Database(config.DATABASE_URL)
    with db.session() as session:
        records = session.scalars(select(ForecastArtifact).where(
            ForecastArtifact.model_version == MODEL_VERSION,
            ForecastArtifact.frequency == "weekly",
        )).all()
        metric_map = {(row.site_identifier, row.material_name, row.model_name): json.loads(row.metrics_json or "{}") for row in records}
        history = history_to_frame(session)
    for row in document.get("series_metrics", []):
        meta = metric_map.get((row["site"], row["material"], row["model"]), {})
        for key in ("interval_radius", "forecast_error_sigma", "prediction_interval_coverage_pct"):
            row[key] = meta.get(key)
    with db.session() as session:
        records = session.scalars(select(ForecastArtifact).where(
            ForecastArtifact.model_version == MODEL_VERSION,
            ForecastArtifact.frequency == "weekly",
            ForecastArtifact.artifact_path.is_not(None),
        )).all()
    series_rows = document.get("series_metrics", [])
    detail_map = {}
    pairs = sorted({(row["site"], row["material"]) for row in series_rows})
    for site, material in pairs:
        assessment = load_saved_assessment(db, history, site=site, material=material,
                                           frequency="weekly", horizon_days=90,
                                           source_label="Doon Ridge Materials Ledger")
        if assessment is None:
            continue
        for model_name, frame in assessment["holdout_predictions"].items():
            predictions = [{"date": d.date().isoformat(), "actual": float(actual),
                            "predicted": float(predicted), "residual": float(actual-predicted)}
                           for d, actual, predicted in zip(frame["date"], frame["actual"], frame["predicted"])]
            residuals = [item["residual"] for item in predictions]
            mean = sum(residuals) / len(residuals) if residuals else None
            std = (sum((value-mean)**2 for value in residuals) / len(residuals))**0.5 if residuals and mean is not None else None
            left, right = residuals[:-1], residuals[1:]
            denom = sum((value-mean)**2 for value in residuals) if mean is not None else 0
            acf1 = sum((a-mean)*(b-mean) for a,b in zip(left,right))/denom if denom else None
            future = assessment["forecasts"].get(model_name)
            future_rows = [] if future is None else [
                {"date": d.date().isoformat(), "forecast": float(value),
                 "lower": float(future.iloc[i]["lower"]) if "lower" in future else None,
                 "upper": float(future.iloc[i]["upper"]) if "upper" in future else None}
                for i, (d, value) in enumerate(zip(future["date"], future["forecast"]))
            ]
            payload = assessment["payloads"].get(model_name, {})
            estimator = payload.get("estimator")
            importances = getattr(estimator, "feature_importances_", None)
            feature_names = ["lag_1", "lag_2", "lag_3", "lag_4", "rolling_mean_4", "rolling_std_4"]
            importance_rows = ([{"feature": name, "importance": float(value)} for name, value in zip(feature_names, importances)]
                               if importances is not None else [])
            detail_map[(site, material, model_name)] = {
                "holdout_predictions": predictions, "future_predictions": future_rows,
                "residual_summary": {"mean": mean, "standard_deviation": std, "lag_1_autocorrelation": acf1},
                "feature_importance": importance_rows,
            }
    for row in series_rows:
        row.update(detail_map.get((row["site"], row["material"], row["model"]), {
            "holdout_predictions": [], "future_predictions": [], "feature_importance": [],
        }))
    db.dispose()
    for model_name, summary in document.get("model_summaries", {}).items():
        selected_rows = [row for row in document["series_metrics"] if row["model"] == model_name and row["selected_model"] == model_name and row.get("prediction_interval_coverage_pct") is not None]
        summary["selected_model_mean_interval_coverage_pct"] = (
            sum(row["prediction_interval_coverage_pct"] for row in selected_rows) / len(selected_rows)
            if selected_rows else None
        )
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Metrics refreshed from {len(records)} saved model records.")
    return 0


def main() -> int:
    started = time.perf_counter()
    db = Database(config.DATABASE_URL)
    initialize_database(db)
    ensure_ledger_baseline(db, config.SOURCE_CSV)
    ensure_baseline_planner_history(db, config.SOURCE_CSV)
    with db.session() as session:
        history = history_to_frame(session)
    if history.empty:
        print("No imported observations found; no models were trained.", file=sys.stderr, flush=True)
        db.dispose()
        return 2

    pairs = sorted({(str(site), str(material)) for site, material in zip(history.project_site_id, history.material)})
    models, optional_note = available_models()
    print(
        f"Training {len(models)} model(s) for {len(pairs)} observed weekly site/material series; "
        f"source rows={len(history):,}, models={', '.join(models)}.",
        flush=True,
    )
    if optional_note:
        print(optional_note, file=sys.stderr, flush=True)

    failures: list[str] = []
    metric_rows: list[dict] = []
    trained_models = 0
    successful_pairs = 0
    for index, (site, material) in enumerate(pairs, start=1):
        pair_started = time.perf_counter()
        try:
            assessment = evaluate_model_suite(
                history,
                site=site,
                material=material,
                frequency="weekly",
                horizon_days=30,
                model_names=models,
                source_label="Doon Ridge Materials Ledger",
            )
            persist_assessment(db, assessment)
            for metric in assessment["metrics"]:
                metric_rows.append({
                    "site": site,
                    "material": material,
                    "unit": assessment["unit"],
                    "selected_model": assessment["best_model"],
                    **metric,
                    "interval_radius": metric.get("interval_radius"),
                    "forecast_error_sigma": metric.get("forecast_error_sigma"),
                    "prediction_interval_coverage_pct": metric.get("prediction_interval_coverage_pct"),
                })
            successful_pairs += 1
            available = [row for row in assessment["metrics"] if row["status"] == "available"]
            unavailable = [row for row in assessment["metrics"] if row["status"] != "available"]
            trained_models += len(available)
            best = next(row for row in available if row["model"] == assessment["best_model"])
            detail = f"best={best['model']} rolling-origin MAE={best['selection_mae']:.3f} {assessment['unit']}"
            if unavailable:
                detail += " unavailable=" + ",".join(row["model"] for row in unavailable)
                failures.append(f"{site} / {material}: " + "; ".join(f"{r['model']}: {r['message']}" for r in unavailable))
            print(
                f"[{index:02d}/{len(pairs):02d}] {site} / {material}: {detail}; "
                f"pair={time.perf_counter()-pair_started:.2f}s; total={time.perf_counter()-started:.1f}s",
                flush=True,
            )
        except Exception as exc:
            failures.append(f"{site} / {material}: {type(exc).__name__}: {exc}")
            print(f"[{index:02d}/{len(pairs):02d}] {site} / {material}: FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    db.dispose()

    summaries = {}
    for model_name in models:
        rows = [row for row in metric_rows if row["model"] == model_name and row["status"] == "available"]
        summaries[model_name] = {
            "series_count": len({(row["site"], row["material"]) for row in rows}),
            "mean_mae": sum(row["mae"] for row in rows) / len(rows) if rows else None,
            "mean_rmse": sum(row["rmse"] for row in rows) / len(rows) if rows else None,
            "mean_wape_pct": sum(row["wape_pct"] for row in rows if row["wape_pct"] is not None) / max(1, sum(row["wape_pct"] is not None for row in rows)) if rows else None,
            "mean_mase": sum(row["mase"] for row in rows if row.get("mase") is not None) / max(1, sum(row.get("mase") is not None for row in rows)) if rows else None,
            "selected_model_mean_interval_coverage_pct": (
                sum(row["prediction_interval_coverage_pct"] for row in rows if row["model"] == row["selected_model"] and row.get("prediction_interval_coverage_pct") is not None)
                / max(1, sum(row["model"] == row["selected_model"] and row.get("prediction_interval_coverage_pct") is not None for row in rows))
                if rows else None
            ),
        }
    metrics_path = config.PROJECT_ROOT / "docs" / "model_metrics.json"
    metrics_path.write_text(json.dumps({
        "model_version": "1.4",
        "dataset_sha256": __import__("hashlib").sha256(config.SOURCE_CSV.read_bytes()).hexdigest(),
        "series_count": len(pairs),
        "model_summaries": summaries,
        "series_metrics": metric_rows,
    }, indent=2, sort_keys=True), encoding="utf-8")
    elapsed = time.perf_counter() - started
    print(
        f"Finished in {elapsed:.2f}s: {successful_pairs}/{len(pairs)} pair(s), "
        f"{trained_models} model artifact(s), {len(failures)} issue(s).",
        flush=True,
    )
    if failures:
        print("Issues:\n- " + "\n- ".join(failures), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-only", action="store_true", help="Refresh stored coverage metadata without refitting models")
    args = parser.parse_args()
    raise SystemExit(refresh_metrics_only() if args.metrics_only else main())



