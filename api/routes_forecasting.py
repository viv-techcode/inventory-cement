"""Forecast source selection, evaluation, and metadata endpoints."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_database, get_session
from api.errors import APIProblem
from api.schemas import ForecastRequest
from api.serializers import forecast_payload
from inventory_app.forecast_sources import ForecastSourceError, resolve_forecast_source, source_eligibility
from inventory_app.data_quality import history_to_frame
from inventory_app.forecasting import (
    MODEL_VERSION,
    ForecastUnavailable,
    assess_demand_source_recency,
    data_hash_for_series,
    evaluate_model_suite,
    load_saved_assessment,
    persist_assessment,
)
from inventory_app.inventory import local_today
from inventory_app.models import ForecastArtifact, Material, ProjectSite
from inventory_app.reports import forecast_metadata_report

router = APIRouter(prefix="/api", tags=["forecasting"])


def _selected_pair(session: Session, site_id: int, material_id: int) -> tuple[ProjectSite, Material]:
    site = session.get(ProjectSite, site_id)
    material = session.get(Material, material_id)
    if site is None or material is None or not site.is_active or not material.is_active:
        raise APIProblem(404, "catalogue_item_not_found", "Select an active site and material.")
    return site, material


@router.get("/forecast-sources")
def forecast_sources(
    site_id: int,
    material_id: int,
    frequency: str = Query(default="weekly", pattern="^(weekly|monthly)$"),
    session: Session = Depends(get_session),
):
    site, material = _selected_pair(session, site_id, material_id)
    result = source_eligibility(session, site=site.identifier, material=material.name, frequency=frequency)
    return {
        **result,
        "site": site.identifier,
        "material": material.name,
        "source_label_if_auto": result["source_label_if_auto"],
        "policy": "Operational sales is selected only after the stated observed-period minimum; no historical CSV rows are merged into it.",
    }


@router.post("/forecasts/evaluate")
def evaluate_forecast(
    body: ForecastRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    site, material = _selected_pair(session, body.site_id, body.material_id)
    try:
        source_frame, source_kind, source_label, source_details = resolve_forecast_source(
            session,
            site=site.identifier,
            material=material.name,
            frequency=body.frequency,
            requested_source=body.source,
        )
    except ForecastSourceError as exc:
        raise APIProblem(
            409,
            "operational_sales_history_insufficient",
            str(exc),
            {
                "observed_periods": exc.observed_periods,
                "required_periods": exc.required_periods,
                "frequency": exc.frequency,
                "source_label_if_auto": "Historical CSV",
            },
        ) from exc

    database = get_database(request)
    params = {
        "site": site.identifier,
        "material": material.name,
        "frequency": body.frequency,
        "horizon_days": body.horizon_days,
        "source_label": source_label,
    }
    try:
        assessment = load_saved_assessment(database, source_frame, **params)
        if assessment is None:
            assessment = evaluate_model_suite(source_frame, **params)
            persist_assessment(database, assessment)
    except ForecastUnavailable as exc:
        raise APIProblem(422, "forecast_unavailable", str(exc), {"source_label": source_label}) from exc
    except ValueError as exc:
        raise APIProblem(422, "forecast_unavailable", str(exc), {"source_label": source_label}) from exc

    recency = assess_demand_source_recency(
        source_frame,
        site=site.identifier,
        material=material.name,
        as_of=local_today(),
    )
    details = {
        **source_details,
        "requested_source": body.source,
        "resolved_source": source_kind,
        "source_reason": source_details.get("source_reason", source_details.get("note")),
    }
    return forecast_payload(
        assessment,
        source_kind=source_kind,
        source_label=source_label,
        source_details=details,
        recency=recency,
    )


@router.get("/forecasts/leaderboard")
def forecast_leaderboard(session: Session = Depends(get_session)):
    """Rank only stored weekly holdout metrics matching the current source hash."""
    history = history_to_frame(session)
    if history.empty:
        return {"frequency": "weekly", "pair_count": 0, "wins": [], "items": [], "stored_metrics_only": True}

    records = session.scalars(
        select(ForecastArtifact).where(
            ForecastArtifact.frequency == "weekly",
            ForecastArtifact.model_version == MODEL_VERSION,
        )
    ).all()
    stored: dict[tuple[str, str, str], dict[str, dict]] = defaultdict(dict)
    for record in records:
        metrics = json.loads(record.metrics_json or "{}")
        stored[(record.site_identifier, record.material_name, record.data_hash)][record.model_name] = {
            "model": record.model_name,
            "status": metrics.get("status"),
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "r2": metrics.get("r2"),
            "wape_pct": metrics.get("wape_pct"),
            "training_observations": record.training_observations,
            "evaluation_observations": record.evaluation_observations,
            "training_start": record.training_start.date().isoformat() if record.training_start else None,
            "training_end": record.training_end.date().isoformat() if record.training_end else None,
            "evaluation_start": record.evaluation_start.date().isoformat() if record.evaluation_start else None,
            "evaluation_end": record.evaluation_end.date().isoformat() if record.evaluation_end else None,
        }

    items = []
    wins: Counter[str] = Counter()
    pairs = sorted({(str(site), str(material)) for site, material in zip(history.project_site_id, history.material)})
    for site, material in pairs:
        try:
            current_hash = data_hash_for_series(
                history, site, material, "weekly", source_label="Historical CSV"
            )
        except ForecastUnavailable:
            continue
        metrics_by_model = stored.get((site, material, current_hash), {})
        eligible = [
            metric for metric in metrics_by_model.values()
            if metric["status"] == "available" and metric["mae"] is not None
        ]
        if not eligible:
            continue
        best = min(eligible, key=lambda metric: (float(metric["mae"]), metric["model"]))
        wins[best["model"]] += 1
        items.append({
            "site": site,
            "material": material,
            "best_model": best["model"],
            "best_mae": float(best["mae"]),
            "unit": str(history.loc[
                (history.project_site_id == site) & (history.material == material), "unit"
            ].iloc[0]),
            "metrics": sorted(eligible, key=lambda metric: (float(metric["mae"]), metric["model"])),
            "training_start": best["training_start"],
            "training_end": best["training_end"],
            "evaluation_start": best["evaluation_start"],
            "evaluation_end": best["evaluation_end"],
        })

    return {
        "frequency": "weekly",
        "source_label": "Historical CSV",
        "model_version": MODEL_VERSION,
        "pair_count": len(items),
        "stored_metrics_only": True,
        "wins": [
            {"model": name, "wins": int(wins.get(name, 0))}
            for name in sorted({metric["model"] for item in items for metric in item["metrics"]})
        ],
        "items": items,
    }


@router.get("/forecasts/metadata")
def forecast_metadata(session: Session = Depends(get_session)):
    frame = forecast_metadata_report(session)
    return {"items": frame.where(frame.notna(), None).to_dict(orient="records"), "total": len(frame)}
