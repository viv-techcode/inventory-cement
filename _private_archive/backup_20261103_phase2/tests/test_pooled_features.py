from __future__ import annotations

import numpy as np
import pandas as pd

from inventory_app.pooled_forecasting import (
    build_pooled_frame,
    choose_pooled_or_naive,
    fit_pooled_models,
    inverse_target_transform,
    predict_pooled,
    transform_target,
)


def _history(periods: int = 14) -> pd.DataFrame:
    dates = pd.date_range("2025-01-05", periods=periods, freq="W-SUN")
    return pd.DataFrame({
        "date": dates,
        "project_site_id": "Site A",
        "material": "Cement",
        "consumption_qty": np.arange(1.0, periods + 1.0),
        "project_type": "Residential",
        "project_phase": "Foundation",
        "unit_price_inr": 100.0,
        "supplier_lead_time_days": 7,
    })


def test_pooled_features_are_past_only_for_target_and_later_rows():
    history = _history(8)
    before, _, keys = build_pooled_frame(history)
    changed = history.copy()
    changed.loc[7, "consumption_qty"] = 99999.0
    after, _, _ = build_pooled_frame(changed)

    # Four observations are omitted until lags 1–4 are available.
    assert len(keys) == 4
    assert isinstance(keys[-1], tuple)
    assert isinstance(keys[-1][2], pd.Timestamp)
    pd.testing.assert_series_equal(before.iloc[-1], after.iloc[-1])

    later = _history(9).tail(1)
    future_before, _, future_keys = build_pooled_frame(pd.concat([history, later], ignore_index=True))
    future_after, _, _ = build_pooled_frame(pd.concat([changed, later], ignore_index=True))
    assert future_keys[-1][2] > keys[-1][2]
    assert future_before.iloc[-1]["lag1"] != future_after.iloc[-1]["lag1"]


def test_pooled_target_transforms_round_trip():
    targets = np.array([0.0, 3.0, 12.0])
    np.testing.assert_allclose(inverse_target_transform(transform_target(targets, "raw"), "raw"), targets)
    np.testing.assert_allclose(inverse_target_transform(transform_target(targets, "log1p"), "log1p"), targets)
    scale = 7.5
    np.testing.assert_allclose(
        inverse_target_transform(transform_target(targets, "series_mean", scale), "series_mean", scale), targets
    )
    np.testing.assert_allclose(inverse_target_transform([-1.0], "raw"), [0.0])


def test_log1p_inverse_clips_extreme_predictions_to_training_cap():
    max_training_target = 12.0
    prediction = inverse_target_transform(
        [800.0], "log1p", max_training_target=max_training_target
    )
    cap = max_training_target * 3.0
    assert np.isfinite(prediction).all()
    assert prediction[0] <= cap


def test_pooled_models_handle_unknown_categories():
    history = _history()
    cutoff = history.loc[12, "date"] + pd.Timedelta(days=1)
    models = fit_pooled_models(
        history,
        cutoff=cutoff,
        model_names=("Pooled MLR", "Pooled Random Forest"),
        target_transforms=("raw",),
    )
    future_features, _, _ = build_pooled_frame(history)
    unknown = future_features.tail(1).copy()
    unknown.loc[:, "material"] = "Unseen material"
    unknown.loc[:, "project_site_id"] = "Unseen site"
    unknown.loc[:, "project_type"] = "Unseen project type"
    unknown.loc[:, "project_phase"] = "Unseen phase"

    for model in models.values():
        prediction = predict_pooled(model, unknown)
        assert prediction.shape == (1,)
        assert np.isfinite(prediction).all()
        assert prediction[0] >= 0


def test_pooled_backtest_falls_back_to_naive_unless_strictly_better():
    candidates = {("Pooled MLR", "log1p"): 12.0, ("Pooled Random Forest", "raw"): 10.0}
    assert choose_pooled_or_naive(10.0, candidates) == ("Naive", None)
    assert choose_pooled_or_naive(10.1, candidates) == ("Pooled Random Forest", "raw")
    assert choose_pooled_or_naive(10.0, {("Pooled Random Forest", "raw"): 10.0}) == ("Naive", None)
