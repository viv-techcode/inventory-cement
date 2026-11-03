from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app
from sqlalchemy import select

from inventory_app.models import Material, ProjectSite


def test_forecast_api_uses_naive_fallback_when_offline_artifacts_are_missing(seeded_db, tmp_path, monkeypatch):
    database, _ = seeded_db
    monkeypatch.setenv("INVENTORY_ARTIFACTS_DIR", str(tmp_path / "models"))
    app = create_app(database_url=database.url, auto_import_source=False)
    with TestClient(app) as client:
        with database.session() as session:
            site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == "Jakhan, Dehradun"))
            material = session.scalar(select(Material).where(Material.name == "Cement"))
            site_id, material_id = site.id, material.id
        sources = client.get(f"/api/forecast-sources?site_id={site_id}&material_id={material_id}&frequency=weekly")
        assert sources.status_code == 200
        assert sources.json()["source_label_if_auto"] == "Construction Materials Dehradun Dataset"
        response = client.post("/api/forecasts/evaluate", json={
            "site_id": site_id,
            "material_id": material_id,
            "frequency": "weekly",
            "horizon_days": 30,
            "source": "auto",
        })
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["source_label"] == "Construction Materials Dehradun Dataset"
        assert result["source_kind"] == "historical_csv"
        assert result["source_details"]["source_reason"] == "The evaluation uses historical observations."
        models = {row["model"] for row in result["metrics"]}
        assert models == {"Naive"}
        assert any("offline-trained model suite" in warning for warning in result["warnings"])
        assert result["best_model"] in result["forecasts"]
        assert result["forecasts"][result["best_model"]]
        assert result["prediction_interval"]["level_pct"] == 90
        assert "lower" in result["forecasts"][result["best_model"]][0]
        assert "upper" in result["forecasts"][result["best_model"]][0]
        assert result["holdouts"][result["best_model"]]
        assert result["feature_importance"] == []
        assert result["freshness"]["is_current"] is False
        metadata = client.get("/api/forecasts/metadata")
        assert metadata.status_code == 200, metadata.text
        assert metadata.json()["total"] >= 4
        leaderboard = client.get("/api/forecasts/leaderboard")
        assert leaderboard.status_code == 200, leaderboard.text
        board = leaderboard.json()
        assert board["stored_metrics_only"] is True
        assert board["pair_count"] == 1
        assert board["items"][0]["best_model"] == result["best_model"]
        assert sum(row["wins"] for row in board["wins"]) == 1
