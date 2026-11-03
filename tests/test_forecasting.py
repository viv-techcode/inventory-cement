from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from inventory_app.data_quality import history_to_frame
from inventory_app.forecasting import (
    ForecastUnavailable,
    _calculate_metrics,
    assess_demand_source_recency,
    evaluate_model_suite,
    feature_row,
    load_saved_assessment,
    persist_assessment,
    prepare_series,
)
from inventory_app.pooled_forecasting import build_pooled_frame, inverse_target_transform


def _history(db):
    with db.session() as session:
        return history_to_frame(session)


@pytest.mark.slow
def test_weekly_evaluation_is_chronological_and_has_baselines(seeded_db):
    db, _ = seeded_db
    history = _history(db)
    result = evaluate_model_suite(history, site="Jakhan, Dehradun", material="Cement", frequency="weekly", horizon_days=30)
    names = {row["model"] for row in result["metrics"]}
    assert {"Naive", "Seasonal Naive", "Multiple Linear Regression", "Random Forest"}.issubset(names)
    holdout = result["holdout_predictions"]["Multiple Linear Regression"]
    assert {"date", "actual", "predicted"}.issubset(holdout.columns)
    assert holdout["actual"].notna().sum() >= 3
    assert result["calendar_periods"] == 149
    assert result["source_observations"] == 149
    assert result["evaluation_start"] > result["training_start"]
    for row in result["metrics"]:
        if row["status"] == "available":
            assert row["training_end"] < row["test_start"]
            assert row["evaluation_observations"] > 0
            assert row["mae"] >= 0 and row["rmse"] >= 0
    assert len(result["forecasts"]["Naive"]) == 5
    chosen = result["forecasts"][result["best_model"]]
    assert {"lower", "upper"}.issubset(chosen.columns)
    assert (chosen["lower"] <= chosen["forecast"]).all()
    assert (chosen["upper"] >= chosen["forecast"]).all()
    assert result["prediction_interval"]["level_pct"] == 90
    assert result["forecasts"]["Naive"].iloc[0]["date"].strftime("%Y-%m-%d") == "2026-01-05"


def test_current_replenishment_recency_uses_latest_valid_selected_observation():
    history = pd.DataFrame(
        {
            "project_site_id": ["Site A", "Site A", "Site A", "Site B"],
            "material": ["Cement", "Cement", "Cement", "Cement"],
            "date": ["2026-10-01", "2026-10-20", "2026-10-26", "2026-10-27"],
            "consumption_qty": [4.0, 5.0, np.nan, 100.0],
        }
    )
    fresh = assess_demand_source_recency(
        history, site="Site A", material="Cement", as_of=date(2026, 10, 27)
    )
    assert fresh["latest_observation_date"] == date(2026, 10, 20)
    assert fresh["age_days"] == 7
    assert fresh["is_current"] is True

    stale = assess_demand_source_recency(
        history, site="Site A", material="Cement", as_of=date(2026, 11, 5)
    )
    assert stale["age_days"] == 16
    assert stale["is_current"] is False

    future_dated = assess_demand_source_recency(
        history, site="Site A", material="Cement", as_of=date(2026, 10, 19)
    )
    assert future_dated["age_days"] == -1
    assert future_dated["is_current"] is False


def test_past_only_feature_and_zero_safe_metrics():
    values = np.arange(1.0, 20.0)
    feature_before = feature_row(values[:8])
    future_changed = values.copy()
    future_changed[8:] = 100000
    feature_after = feature_row(future_changed[:8])
    np.testing.assert_array_equal(feature_before, feature_after)

    metrics = _calculate_metrics(np.array([0.0, 0.0, 0.0]), np.array([1.0, -1.0, 0.0]))
    assert metrics["mae"] == pytest.approx(2 / 3)
    assert metrics["rmse"] == pytest.approx((2 / 3) ** 0.5)
    assert metrics["wape_pct"] is None
    assert metrics["r2"] is None


def test_pooled_features_use_only_observations_before_target():
    dates = pd.date_range("2025-01-05", periods=9, freq="W-SUN")
    history = pd.DataFrame({"date": dates[:8], "project_site_id": "Site A", "material": "Cement", "consumption_qty": np.arange(1., 9.),
                            "project_type": "Residential", "project_phase": "Foundation", "unit_price_inr": 100., "supplier_lead_time_days": 7})
    before, _, keys = build_pooled_frame(history)
    changed = history.copy()
    changed.loc[7, "consumption_qty"] = 99999
    after, _, _ = build_pooled_frame(changed)

    # Four initial observations are skipped to form lag 1–4. The final feature
    # row predicts the last observation, so changing that target cannot change
    # its own past-only inputs.
    target_key = keys[-1]
    assert target_key[:2] == ("Site A", "Cement")
    assert isinstance(target_key[2], pd.Timestamp)
    pd.testing.assert_series_equal(before.iloc[-1], after.iloc[-1])

    # A future target after the changed observation must see it as lag 1.
    later = pd.DataFrame({"date": [dates[8]], "project_site_id": ["Site A"], "material": ["Cement"],
                          "consumption_qty": [9.], "project_type": ["Residential"], "project_phase": ["Foundation"],
                          "unit_price_inr": [100.], "supplier_lead_time_days": [7]})
    later_before, _, later_keys = build_pooled_frame(pd.concat([history, later], ignore_index=True))
    later_after, _, _ = build_pooled_frame(pd.concat([changed, later], ignore_index=True))
    assert later_keys[-1][2] > target_key[2]
    assert not np.array_equal(later_before.iloc[-1].to_numpy(), later_after.iloc[-1].to_numpy())


def test_pooled_inverse_target_transforms():
    np.testing.assert_allclose(inverse_target_transform(np.log1p([0., 12.]), "log1p"), [0., 12.])
    np.testing.assert_allclose(inverse_target_transform([1., 2.], "series_mean", scale=25.), [25., 50.])


def test_pooled_selection_falls_back_to_naive():
    from inventory_app.forecasting import _select_best_model
    metrics = [{"model": "Naive", "status": "available", "selection_mae": 3.},
               {"model": "Pooled Random Forest", "status": "available", "selection_mae": 4.}]
    assert _select_best_model(metrics)[0] == "Naive"


def test_monthly_aggregation_and_sparse_series_handling(seeded_db):
    db, _ = seeded_db
    history = _history(db)
    series = prepare_series(history, "Jakhan, Dehradun", "Cement", "monthly")
    assert len(series.periods) == 24
    assert np.isfinite(series.values).sum() == 24
    assert series.unit == "50-kg bags"

    sparse = history.loc[(history["project_site_id"] == "Jakhan, Dehradun") & (history["material"] == "Cement")].head(10)
    with pytest.raises(ForecastUnavailable, match="at least 26"):
        prepare_series(sparse, "Jakhan, Dehradun", "Cement", "weekly")


@pytest.mark.slow
def test_model_artifact_save_reload_and_invalidation(seeded_db, tmp_path):
    db, _ = seeded_db
    history = _history(db)
    result = evaluate_model_suite(history, site="Jakhan, Dehradun", material="Cement", frequency="weekly", horizon_days=30)
    persist_assessment(db, result, artifacts_dir=tmp_path / "models")
    assert list((tmp_path / "models").glob("*.joblib"))
    loaded = load_saved_assessment(db, history, site="Jakhan, Dehradun", material="Cement", frequency="weekly", horizon_days=60)
    assert loaded is not None
    assert loaded["cache_hit"] is True
    assert loaded["horizon_days"] == 60
    assert len(loaded["forecasts"][loaded["best_model"]]) == 9
    assert {"lower", "upper"}.issubset(loaded["forecasts"][loaded["best_model"]].columns)
    assert not loaded["holdout_predictions"][loaded["best_model"]].empty

    changed = history.copy()
    series_index = changed.loc[(changed["project_site_id"] == "Jakhan, Dehradun") & (changed["material"] == "Cement")].index[-1]
    changed.loc[series_index, "consumption_qty"] += 1
    invalidated = load_saved_assessment(db, changed, site="Jakhan, Dehradun", material="Cement", frequency="weekly", horizon_days=30)
    assert invalidated is None
