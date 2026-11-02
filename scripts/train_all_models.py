"""Evaluate and persist weekly forecast artifacts for each observed site/material pair.

Run from the repository root with ``python -m scripts.train_all_models`` after
loading the source CSV and any explicitly tagged sample extension. The script
trains on the imported observation table, including each row's source tag in
its provenance, and does not create observations or operational ledger entries.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from inventory_app import config
from inventory_app.data_quality import history_to_frame
from inventory_app.database import Database, initialize_database
from inventory_app.forecasting import available_models, evaluate_model_suite, persist_assessment
from inventory_app.ingestion import ensure_primary_dataset_import


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
                source_label="Historical CSV",
            )
            persist_assessment(db, assessment)
            successful_pairs += 1
            available = [row for row in assessment["metrics"] if row["status"] == "available"]
            unavailable = [row for row in assessment["metrics"] if row["status"] != "available"]
            trained_models += len(available)
            best = min(available, key=lambda row: row["mae"])
            detail = f"best={best['model']} MAE={best['mae']:.3f} {assessment['unit']}"
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
    raise SystemExit(main())
