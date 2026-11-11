"""Evaluate and persist weekly forecast artifacts for each observed site/material pair.

Run from the repository root with ``python -m scripts.train_all`` after the
canonical dataset has been imported. Training does not alter observations or
create operational ledger entries.
"""
from __future__ import annotations

import sys
import time
import json
import shutil
import argparse
from pathlib import Path

from inventory_app import config
from inventory_app.data_quality import history_to_frame
from inventory_app.database import Database, initialize_database
from inventory_app.forecasting import available_models, evaluate_model_suite, persist_assessment
from inventory_app.ingestion import ensure_primary_dataset_import
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
    db.dispose()
    for row in document.get("series_metrics", []):
        meta = metric_map.get((row["site"], row["material"], row["model"]), {})
        for key in ("interval_radius", "forecast_error_sigma", "prediction_interval_coverage_pct"):
            row[key] = meta.get(key)
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
    ensure_primary_dataset_import(db, str(config.SOURCE_CSV))
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
                source_label="Construction Materials Dehradun Dataset",
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
    referenced = set()
    # Reopen read-only at the service layer to reconcile files against DB references.
    cleanup_db = Database(config.DATABASE_URL)
    with cleanup_db.session() as session:
        stale_rows = session.scalars(select(ForecastArtifact).where(ForecastArtifact.artifact_path.is_not(None))).all()
        for row in stale_rows:
            if not Path(row.artifact_path).exists():
                session.delete(row)
        session.commit()
        referenced = {Path(path).resolve() for path in session.scalars(
            select(ForecastArtifact.artifact_path).where(ForecastArtifact.artifact_path.is_not(None))
        ).all()}
    orphaned = 0
    archive = config.PROJECT_ROOT / "_private_archive" / "retired_model_artifacts"
    for artifact_file in config.get_artifacts_dir().glob("*.joblib"):
        if artifact_file.resolve() not in referenced:
            archive.mkdir(parents=True, exist_ok=True)
            destination = archive / artifact_file.name
            if destination.exists():
                destination = archive / f"{artifact_file.stem}-{int(time.time())}{artifact_file.suffix}"
            shutil.move(str(artifact_file), str(destination))
            orphaned += 1
    cleanup_db.dispose()
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
        f"{trained_models} model artifact(s), {orphaned} unreferenced file(s) retired, {len(failures)} issue(s).",
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
