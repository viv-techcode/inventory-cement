"""Chronological, leakage-aware demand forecasting for weekly and monthly series."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from inventory_app.config import get_artifacts_dir
from inventory_app.database import Database
from inventory_app.models import ForecastArtifact, Material, ProjectSite, utc_now
from inventory_app.pooled_forecasting import build_pooled_frame as pooled_feature_frame, inverse_target_transform

MODEL_VERSION = "1.4"
FEATURE_CONFIG = {"lags": [1, 2, 3, 4], "rolling_window": 4, "features_use_past_only": True}
POOLED_MODEL_VERSION = "2.0-global"
BASE_MODELS = ("Naive", "Seasonal Naive", "Multiple Linear Regression", "Random Forest")
# The supplied series are observed about every 6–7 days; allow at most one
# expected weekly interval before current lead-time demand is considered stale.
MAX_REPLENISHMENT_SOURCE_AGE_DAYS = 7
MAX_WEEKLY_FORECAST_HORIZON_DAYS = 90


class ForecastUnavailable(ValueError):
    pass


def assess_demand_source_recency(
    history: pd.DataFrame,
    *,
    site: str,
    material: str,
    as_of: date,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    """Assess whether this weekly series is recent enough for current replenishment.

    Historical forecasts remain useful as retrospective diagnostics, but a forecast
    anchored far behind today's date must not be used for a current stock decision.
    """
    age_limit = MAX_REPLENISHMENT_SOURCE_AGE_DAYS if max_age_days is None else int(max_age_days)
    if age_limit < 0:
        raise ValueError("Maximum source age cannot be negative.")
    required = {"project_site_id", "material", "date", "consumption_qty"}
    if history.empty or not required.issubset(history.columns):
        return {
            "latest_observation_date": None,
            "as_of": as_of,
            "age_days": None,
            "max_age_days": age_limit,
            "is_current": False,
        }
    subset = history.loc[
        (history["project_site_id"] == site) & (history["material"] == material),
        ["date", "consumption_qty"],
    ]
    if subset.empty:
        return {
            "latest_observation_date": None,
            "as_of": as_of,
            "age_days": None,
            "max_age_days": age_limit,
            "is_current": False,
        }
    dates = pd.to_datetime(subset["date"], errors="coerce")
    quantities = pd.to_numeric(subset["consumption_qty"], errors="coerce")
    valid = dates.notna() & quantities.notna() & np.isfinite(quantities.astype(float))
    valid_dates = dates.loc[valid]
    if valid_dates.empty:
        return {
            "latest_observation_date": None,
            "as_of": as_of,
            "age_days": None,
            "max_age_days": age_limit,
            "is_current": False,
        }
    latest = valid_dates.max().date()
    age_days = (as_of - latest).days
    return {
        "latest_observation_date": latest,
        "as_of": as_of,
        "age_days": age_days,
        "max_age_days": age_limit,
        "is_current": 0 <= age_days <= age_limit,
    }


@dataclass
class PreparedSeries:
    site: str
    material: str
    unit: str
    frequency: str
    source_label: str
    periods: pd.PeriodIndex
    dates: pd.DatetimeIndex
    values: np.ndarray
    source_observations: int
    warnings: list[str]
    data_hash: str


def available_models() -> tuple[list[str], str | None]:
    names = list(BASE_MODELS)
    try:
        import xgboost  # noqa: F401
        names.append("XGBoost")
        note = None
    except Exception as exc:  # optional dependency / native library may be unavailable
        note = f"XGBoost is unavailable ({type(exc).__name__}); the supported baselines and scikit-learn models remain available."
    return names, note


def prepare_series(
    history: pd.DataFrame,
    site: str,
    material: str,
    frequency: str,
    *,
    source_label: str = "Construction Materials Dehradun Dataset",
) -> PreparedSeries:
    """Aggregate observations to calendar weeks/months, preserving missing periods as NaN."""
    if frequency not in {"weekly", "monthly"}:
        raise ForecastUnavailable("Forecasting supports weekly and monthly frequency only; daily data is not observed at this source's cadence.")
    if history.empty:
        raise ForecastUnavailable("No historical observations are loaded.")
    subset = history.loc[
        (history["project_site_id"] == site) & (history["material"] == material),
        ["date", "consumption_qty", "unit"],
    ].copy()
    if subset.empty:
        raise ForecastUnavailable("No observations exist for the selected site/material pair.")
    units = subset["unit"].dropna().astype(str).unique()
    if len(units) != 1:
        raise ForecastUnavailable("The selected historical series has inconsistent units and cannot be forecast safely.")
    subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
    subset["consumption_qty"] = pd.to_numeric(subset["consumption_qty"], errors="coerce")
    invalid_dates = int(subset["date"].isna().sum())
    invalid_values = int((~np.isfinite(subset["consumption_qty"].astype(float))).sum())
    subset = subset.dropna(subset=["date", "consumption_qty"]).sort_values("date")
    if (subset["consumption_qty"] < 0).any():
        raise ForecastUnavailable("Negative historical consumption values are present; correct the source before training.")
    if frequency == "weekly":
        subset["period"] = subset["date"].dt.to_period("W-SUN")
        freq = "W-SUN"
        season = 52
    else:
        subset["period"] = subset["date"].dt.to_period("M")
        freq = "M"
        season = 12
    aggregated = subset.groupby("period")["consumption_qty"].sum().sort_index()
    if aggregated.empty:
        raise ForecastUnavailable("There are no usable dated consumption observations.")
    full_periods = pd.period_range(aggregated.index.min(), aggregated.index.max(), freq=freq)
    values = aggregated.reindex(full_periods).astype(float).to_numpy()
    missing_periods = int(np.isnan(values).sum())
    observed_count = int(np.isfinite(values).sum())
    minimum = 18 if frequency == "monthly" else 26
    if len(full_periods) < minimum or observed_count < minimum:
        raise ForecastUnavailable(
            f"Only {observed_count} {frequency} observations are usable; at least {minimum} are required for a chronological holdout and lag-based models."
        )
    split = max(12 if frequency == "monthly" else 18, int(math.floor(len(full_periods) * 0.8)))
    if split >= len(full_periods) - 2:
        split = len(full_periods) - max(4, int(math.ceil(len(full_periods) * 0.2)))
    test_count = int(np.isfinite(values[split:]).sum())
    if test_count < 3:
        raise ForecastUnavailable("The chronological test period has fewer than three observed target periods; evaluation would be too weak.")
    warnings: list[str] = []
    if invalid_dates or invalid_values:
        warnings.append(f"{invalid_dates} invalid date(s) and {invalid_values} invalid consumption value(s) were excluded from this series and should be reviewed in Data Management.")
    if missing_periods:
        warnings.append(f"{missing_periods} calendar {frequency} period(s) have no source observation. They remain missing (not zero-filled); lag models skip affected training windows and missing test targets are not scored.")
    if observed_count < 40 and frequency == "weekly":
        warnings.append("A short weekly series increases forecast uncertainty; compare against the naive baseline.")
    period_dates = pd.DatetimeIndex(full_periods.start_time)
    key_payload = {
        "site": site,
        "material": material,
        "frequency": frequency,
        "source_label": source_label,
        "periods": [str(p) for p in full_periods],
        "values": [None if not np.isfinite(v) else round(float(v), 8) for v in values],
        "model_version": MODEL_VERSION,
        "features": FEATURE_CONFIG,
    }
    digest = hashlib.sha256(json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PreparedSeries(
        site=site,
        material=material,
        unit=str(units[0]),
        frequency=frequency,
        source_label=source_label,
        periods=full_periods,
        dates=period_dates,
        values=values,
        source_observations=int(len(subset)),
        warnings=warnings,
        data_hash=digest,
    )


def feature_row(past_values: np.ndarray | list[float], *, window: int = 4) -> np.ndarray | None:
    """Build lag/rolling features using only the observations strictly before prediction time."""
    values = np.asarray(past_values, dtype=float)
    if len(values) < window:
        return None
    tail = values[-window:]
    if not np.isfinite(tail).all():
        return None
    lags = tail[::-1]
    return np.concatenate([lags, np.array([tail.mean(), tail.std(ddof=0)], dtype=float)])


def training_matrix(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    for index in range(4, len(values)):
        features = feature_row(values[:index])
        target = values[index]
        if features is not None and np.isfinite(target):
            x_rows.append(features)
            y_rows.append(float(target))
    if not x_rows:
        return np.empty((0, 6), dtype=float), np.empty((0,), dtype=float)
    return np.vstack(x_rows), np.asarray(y_rows, dtype=float)


def _create_estimator(name: str):
    if name == "Multiple Linear Regression":
        return make_pipeline(StandardScaler(), LinearRegression())
    if name == "Random Forest":
        return RandomForestRegressor(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=1,
        )
    if name == "XGBoost":
        from xgboost import XGBRegressor
        return XGBRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=2.0,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=1,
            verbosity=0,
        )
    raise ValueError(f"No fitted estimator is defined for {name}.")


def _last_valid(values: list[float] | np.ndarray, default: float = 0.0) -> float:
    for value in reversed(values):
        if np.isfinite(value):
            return float(value)
    return default


def _predict_next(name: str, context: list[float], estimator: Any, seasonal_period: int) -> float:
    fallback = _last_valid(context)
    if name == "Naive":
        return max(0.0, fallback)
    if name == "Seasonal Naive":
        candidate = len(context) - seasonal_period
        if candidate >= 0 and np.isfinite(context[candidate]):
            return max(0.0, float(context[candidate]))
        return max(0.0, fallback)
    features = feature_row(context)
    if features is None or estimator is None:
        return max(0.0, fallback)
    value = float(estimator.predict(features.reshape(1, -1))[0])
    return max(0.0, value)


def _recursive_predict(name: str, initial_values: np.ndarray, estimator: Any, steps: int, season: int) -> np.ndarray:
    context = [float(v) for v in initial_values]
    predictions: list[float] = []
    for _ in range(steps):
        prediction = _predict_next(name, context, estimator, season)
        predictions.append(prediction)
        context.append(prediction)
    return np.asarray(predictions, dtype=float)


def _fit_full_estimator(name: str, values: np.ndarray):
    if name in {"Naive", "Seasonal Naive"}:
        return None
    x_all, y_all = training_matrix(values)
    if len(y_all) < 8:
        raise ForecastUnavailable(f"Only {len(y_all)} valid lagged training rows are available; at least 8 are required.")
    estimator = _create_estimator(name)
    estimator.fit(x_all, y_all)
    return estimator


def _chronological_split(series: PreparedSeries) -> tuple[int, int]:
    n = len(series.values)
    split = int(math.floor(n * 0.8))
    minimum_train = 12 if series.frequency == "monthly" else 18
    split = max(minimum_train, split)
    if split >= n - 2:
        split = n - max(4, int(math.ceil(n * 0.2)))
    return split, n


def _calculate_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    *,
    training_values: np.ndarray | None = None,
    seasonal_period: int = 1,
) -> dict[str, float | int | None]:
    mask = np.isfinite(actual) & np.isfinite(predicted)
    y_true = actual[mask]
    y_pred = predicted[mask]
    if not len(y_true):
        raise ForecastUnavailable("No observed target periods overlap the evaluation window.")
    errors = y_pred - y_true
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    r2 = float(r2_score(y_true, y_pred)) if len(y_true) >= 2 and float(np.var(y_true)) > 1e-12 else None
    denominator = float(np.abs(y_true).sum())
    wape = float(np.abs(errors).sum() / denominator * 100) if denominator > 1e-12 else None
    mase = None
    if training_values is not None and len(training_values) > seasonal_period > 0:
        past = np.asarray(training_values, dtype=float)
        naive_differences = np.abs(past[seasonal_period:] - past[:-seasonal_period])
        naive_differences = naive_differences[np.isfinite(naive_differences)]
        scale = float(np.mean(naive_differences)) if len(naive_differences) else 0.0
        if scale > 1e-12:
            mase = mae / scale
    return {"mae": mae, "rmse": rmse, "r2": r2, "wape_pct": wape, "mase": mase, "evaluation_observations": int(len(y_true))}


def _rolling_backtest_errors(name: str, values: np.ndarray, season: int) -> list[float]:
    """Collect absolute errors from three expanding origins before the final holdout."""
    n = len(values)
    first_origin = max(18, int(math.floor(n * 0.55)))
    final_origin = max(first_origin + 3, int(math.floor(n * 0.80)))
    origins = np.linspace(first_origin, final_origin, num=4, dtype=int)[:-1]
    errors: list[float] = []
    for origin, next_origin in zip(origins, [*origins[1:], final_origin]):
        if next_origin <= origin:
            continue
        train = values[:origin]
        try:
            estimator = _fit_full_estimator(name, train)
            predicted = _recursive_predict(name, train, estimator, next_origin - origin, season)
            actual = values[origin:next_origin]
            mask = np.isfinite(actual) & np.isfinite(predicted)
            errors.extend(np.abs(predicted[mask] - actual[mask]).tolist())
        except Exception:
            continue
    if not errors:
        raise ForecastUnavailable("No usable rolling-origin backtest windows were available.")
    return errors


def _rolling_backtest_mae(name: str, values: np.ndarray, season: int) -> float:
    """Mean absolute error across the same pre-holdout rolling origins."""
    return float(np.mean(_rolling_backtest_errors(name, values, season)))


def _select_best_model(metrics: list[dict[str, Any]]) -> tuple[str, str | None]:
    eligible = [row for row in metrics if row["status"] == "available" and row.get("selection_mae") is not None]
    if not eligible:
        raise ForecastUnavailable("No model has a usable rolling-origin selection score.")
    best = min(eligible, key=lambda row: (row["selection_mae"], row["model"]))
    naive = next((row for row in eligible if row["model"] == "Naive"), None)
    ml_names = {"Multiple Linear Regression", "Random Forest", "XGBoost", "Pooled MLR", "Pooled Random Forest", "Pooled XGBoost"}
    if best["model"] in ml_names and naive and best["selection_mae"] >= naive["selection_mae"]:
        return "Naive", "ML did not beat Naive on the pre-holdout rolling-origin MAE; Naive selected for this series."
    return best["model"], None


def forecast_periods_for_horizon(horizon_days: int, frequency: str) -> int:
    if horizon_days <= 0:
        raise ValueError("Forecast horizon must be greater than zero days.")
    if frequency == "weekly":
        return max(1, int(math.ceil(horizon_days / 7)))
    if frequency == "monthly":
        return max(1, int(math.ceil(horizon_days / 30.4375)))
    raise ValueError("Unsupported forecast frequency.")


def future_dates(series: PreparedSeries, steps: int) -> pd.DatetimeIndex:
    next_period = series.periods[-1] + 1
    periods = pd.period_range(next_period, periods=steps, freq=series.periods.freq)
    return pd.DatetimeIndex(periods.start_time)


def evaluate_model_suite(
    history: pd.DataFrame,
    *,
    site: str,
    material: str,
    frequency: str,
    horizon_days: int = 30,
    model_names: list[str] | None = None,
    source_label: str = "Construction Materials Dehradun Dataset",
) -> dict[str, Any]:
    """Select by pre-holdout rolling-origin MAE; score separately on the final holdout."""
    series = prepare_series(history, site, material, frequency, source_label=source_label)
    split, _ = _chronological_split(series)
    values = series.values
    train_values = values[:split]
    actual_test = values[split:]
    season = 52 if frequency == "weekly" else 12
    total_horizon = forecast_periods_for_horizon(horizon_days, frequency)
    if model_names is None:
        names, optional_note = available_models()
    else:
        names = list(dict.fromkeys(name for name in model_names if name in {*BASE_MODELS, "XGBoost"}))
        optional_note = None
        if "XGBoost" in names:
            try:
                import xgboost  # noqa: F401
            except Exception as exc:
                names.remove("XGBoost")
                optional_note = f"XGBoost is unavailable ({type(exc).__name__}); the remaining requested models are used."
    if optional_note:
        series.warnings.append(optional_note)

    metrics: list[dict[str, Any]] = []
    future_frames: dict[str, pd.DataFrame] = {}
    payloads: dict[str, dict[str, Any]] = {}
    holdout_frames: dict[str, pd.DataFrame] = {}
    for name in names:
        failure: str | None = None
        if name == "Seasonal Naive" and int(np.isfinite(train_values).sum()) < season:
            failure = f"Seasonal period is {season}; only {int(np.isfinite(train_values).sum())} training observations are available."
        estimator = None
        try:
            if failure:
                raise ForecastUnavailable(failure)
            estimator = _fit_full_estimator(name, train_values)
            holdout = _recursive_predict(name, train_values, estimator, len(actual_test), season)
            evaluated = _calculate_metrics(actual_test, holdout, training_values=train_values, seasonal_period=season)
            selection_mae = _rolling_backtest_mae(name, values[:split], season)
            if name in {"Multiple Linear Regression", "Random Forest", "XGBoost"}:
                final_estimator = _fit_full_estimator(name, values)
            else:
                final_estimator = None
            forecast_values = _recursive_predict(name, values, final_estimator, total_horizon, season)
            dates = future_dates(series, total_horizon)
            forecast = pd.DataFrame({"date": dates, "forecast": forecast_values})
            future_frames[name] = forecast
            holdout_dates = series.dates[split:]
            holdout_frames[name] = pd.DataFrame({"date": holdout_dates, "actual": actual_test, "predicted": holdout})
            metrics.append(
                {
                    "model": name,
                    "status": "available",
                    **evaluated,
                    "selection_mae": selection_mae,
                    "training_observations": int(np.isfinite(train_values).sum()),
                    "test_start": series.dates[split].date().isoformat(),
                    "test_end": series.dates[-1].date().isoformat(),
                    "training_start": series.dates[0].date().isoformat(),
                    "training_end": series.dates[split - 1].date().isoformat(),
                    "message": "",
                }
            )
            payloads[name] = {
                "model": name,
                "estimator": final_estimator,
                "frequency": frequency,
                "seasonal_period": season,
                "values": values.astype(float),
                "periods": [str(p) for p in series.periods],
                "dates": [d.isoformat() for d in series.dates],
                "feature_config": FEATURE_CONFIG,
                "model_version": MODEL_VERSION,
            }
        except Exception as exc:
            message = str(exc) or type(exc).__name__
            metrics.append(
                {
                    "model": name,
                    "status": "unavailable",
                    "mae": None,
                    "rmse": None,
                    "r2": None,
                    "wape_pct": None,
                    "selection_mae": None,
                    "evaluation_observations": int(np.isfinite(actual_test).sum()),
                    "training_observations": int(np.isfinite(train_values).sum()),
                    "test_start": series.dates[split].date().isoformat(),
                    "test_end": series.dates[-1].date().isoformat(),
                    "training_start": series.dates[0].date().isoformat(),
                    "training_end": series.dates[split - 1].date().isoformat(),
                    "message": message,
                }
            )
    successful = [row for row in metrics if row["status"] == "available"]
    if not successful:
        raise ForecastUnavailable("No forecasting algorithm could be evaluated. " + " | ".join(row["message"] for row in metrics))
    best_model, fallback_note = _select_best_model(metrics)
    if fallback_note:
        series.warnings.append(fallback_note)
    calibration_errors = _rolling_backtest_errors(best_model, values[:split], season)
    interval_radius = float(np.quantile(calibration_errors, 0.90, method="higher"))
    error_sigma = float(np.sqrt(np.mean(np.square(calibration_errors))))
    selected_metric = next(row for row in metrics if row["model"] == best_model)
    selected_metric["interval_radius"] = interval_radius
    selected_metric["forecast_error_sigma"] = error_sigma
    selected_forecast = future_frames[best_model]
    selected_forecast["lower"] = (selected_forecast["forecast"] - interval_radius).clip(lower=0)
    selected_forecast["upper"] = selected_forecast["forecast"] + interval_radius
    selected_holdout = holdout_frames[best_model]
    holdout_valid = selected_holdout["actual"].notna() & selected_holdout["predicted"].notna()
    observed_holdout = selected_holdout.loc[holdout_valid]
    covered = (
        (observed_holdout["actual"] >= (observed_holdout["predicted"] - interval_radius).clip(lower=0))
        & (observed_holdout["actual"] <= observed_holdout["predicted"] + interval_radius)
    )
    interval_coverage_pct = float(covered.mean() * 100.0) if len(covered) else None
    selected_metric["prediction_interval_coverage_pct"] = interval_coverage_pct
    return {
        "site": site,
        "material": material,
        "unit": series.unit,
        "frequency": frequency,
        "source_label": series.source_label,
        "horizon_days": horizon_days,
        "horizon_periods": total_horizon,
        "data_hash": series.data_hash,
        "source_observations": series.source_observations,
        "calendar_periods": int(len(series.periods)),
        "training_start": series.dates[0].date().isoformat(),
        "training_end": series.dates[-1].date().isoformat(),
        "evaluation_start": series.dates[split].date().isoformat(),
        "evaluation_end": series.dates[-1].date().isoformat(),
        "split_index": split,
        "seasonal_period": season,
        "warnings": list(dict.fromkeys(series.warnings)),
        "metrics": metrics,
        "best_model": best_model,
        "prediction_interval": {
            "level_pct": 90,
            "radius": interval_radius,
            "calibration": "pre-holdout rolling-origin absolute errors",
            "holdout_coverage_pct": interval_coverage_pct,
        },
        "forecasts": future_frames,
        "holdout_predictions": holdout_frames,
        "payloads": payloads,
        "series": series,
        "cache_hit": False,
    }


def _scope_key(site: str, material: str, frequency: str, model_name: str, data_hash: str) -> str:
    source = "|".join([site, material, frequency, model_name, MODEL_VERSION, data_hash])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def persist_assessment(db: Database, assessment: dict[str, Any], *, artifacts_dir: str | Path | None = None) -> None:
    """Atomically persist fitted estimators and evaluation metadata for every candidate."""
    directory = Path(artifacts_dir) if artifacts_dir else get_artifacts_dir()
    directory.mkdir(parents=True, exist_ok=True)
    series: PreparedSeries = assessment["series"]
    metrics_by_name = {row["model"]: row for row in assessment["metrics"]}
    with db.session() as session:
        site_obj = session.scalar(select(ProjectSite).where(ProjectSite.identifier == assessment["site"]))
        material_obj = session.scalar(select(Material).where(Material.name == assessment["material"]))
        if site_obj is None or material_obj is None:
            raise ValueError("Cannot persist a forecast for a site/material that is not in the catalog.")
        for model_name, metric in metrics_by_name.items():
            key = _scope_key(assessment["site"], assessment["material"], assessment["frequency"], model_name, assessment["data_hash"])
            path: Path | None = None
            if metric["status"] == "available":
                payload = assessment["payloads"][model_name]
                holdout_frame = assessment.get("holdout_predictions", {}).get(model_name, pd.DataFrame())
                payload = {
                    **payload,
                    "evaluation_metrics": {k: v for k, v in metric.items() if k != "message"},
                    "holdout_predictions": holdout_frame.copy(),
                    "data_hash": assessment["data_hash"],
                    "site": assessment["site"],
                    "material": assessment["material"],
                    "source_label": assessment.get("source_label", series.source_label),
                }
                path = directory / f"{key}.joblib"
                temp_path = path.with_suffix(".tmp")
                joblib.dump(payload, temp_path)
                temp_path.replace(path)
            artifact = session.scalar(select(ForecastArtifact).where(ForecastArtifact.scope_key == key))
            details = {
                "status": metric["status"],
                "mae": metric["mae"],
                "selection_mae": metric.get("selection_mae"),
                "rmse": metric["rmse"],
                "r2": metric["r2"],
                "wape_pct": metric["wape_pct"],
                "mase": metric.get("mase"),
                "interval_radius": metric.get("interval_radius"),
                "forecast_error_sigma": metric.get("forecast_error_sigma"),
                "prediction_interval_coverage_pct": metric.get("prediction_interval_coverage_pct"),
                "message": metric["message"],
            }
            if artifact is None:
                artifact = ForecastArtifact(
                    scope_key=key,
                    site_identifier=assessment["site"],
                    material_name=assessment["material"],
                    frequency=assessment["frequency"],
                    model_name=model_name,
                    model_version=MODEL_VERSION,
                    data_hash=assessment["data_hash"],
                    training_start=datetime.fromisoformat(metric["training_start"]),
                    training_end=datetime.fromisoformat(metric["training_end"]),
                    training_observations=metric["training_observations"],
                    evaluation_observations=metric["evaluation_observations"],
                    evaluation_start=datetime.fromisoformat(metric["test_start"]),
                    evaluation_end=datetime.fromisoformat(metric["test_end"]),
                    metrics_json=json.dumps(details, sort_keys=True),
                    feature_config_json=json.dumps({**FEATURE_CONFIG, "source_label": series.source_label}, sort_keys=True),
                    artifact_path=str(path) if path else None,
                    notes=metric["message"] or "",
                )
                session.add(artifact)
            else:
                artifact.metrics_json = json.dumps(details, sort_keys=True)
                artifact.artifact_path = str(path) if path else None
                artifact.notes = metric["message"] or ""
                artifact.trained_at = utc_now()
        session.commit()


def load_saved_assessment(
    db: Database,
    history: pd.DataFrame,
    *,
    site: str,
    material: str,
    frequency: str,
    horizon_days: int,
    source_label: str = "Construction Materials Dehradun Dataset",
) -> dict[str, Any] | None:
    """Load a compatible model suite after restart without retraining."""
    try:
        series = prepare_series(history, site, material, frequency, source_label=source_label)
    except ForecastUnavailable:
        return None
    optional_note = None
    with db.session() as session:
        records = session.scalars(
            select(ForecastArtifact).where(
                ForecastArtifact.site_identifier == site,
                ForecastArtifact.material_name == material,
                ForecastArtifact.frequency == frequency,
                ForecastArtifact.data_hash == series.data_hash,
                ForecastArtifact.model_version == MODEL_VERSION,
            )
        ).all()
    by_name = {record.model_name: record for record in records}
    names = [name for name in (*BASE_MODELS, "XGBoost") if name in by_name]
    if not all(name in by_name for name in BASE_MODELS):
        return None
    steps = forecast_periods_for_horizon(horizon_days, frequency)
    metrics: list[dict[str, Any]] = []
    forecasts: dict[str, pd.DataFrame] = {}
    payloads: dict[str, dict[str, Any]] = {}
    holdout_frames: dict[str, pd.DataFrame] = {}
    for name in names:
        record = by_name[name]
        meta = json.loads(record.metrics_json or "{}")
        status = meta.get("status", "unavailable")
        if status == "available" and (meta.get("selection_mae") is None or meta.get("mase") is None):
            return None
        row = {
            "model": name,
            "status": status,
            "mae": meta.get("mae"),
            "selection_mae": meta.get("selection_mae"),
            "rmse": meta.get("rmse"),
            "r2": meta.get("r2"),
            "wape_pct": meta.get("wape_pct"),
            "mase": meta.get("mase"),
            "interval_radius": meta.get("interval_radius"),
            "forecast_error_sigma": meta.get("forecast_error_sigma"),
            "prediction_interval_coverage_pct": meta.get("prediction_interval_coverage_pct"),
            "evaluation_observations": record.evaluation_observations,
            "training_observations": record.training_observations,
            "test_start": record.evaluation_start.date().isoformat() if record.evaluation_start else None,
            "test_end": record.evaluation_end.date().isoformat() if record.evaluation_end else None,
            "training_start": record.training_start.date().isoformat(),
            "training_end": record.training_end.date().isoformat(),
            "message": meta.get("message", ""),
        }
        metrics.append(row)
        if status != "available" or not record.artifact_path or not Path(record.artifact_path).exists():
            continue
        payload = joblib.load(record.artifact_path)
        if payload.get("data_hash") != series.data_hash or payload.get("model_version") != MODEL_VERSION:
            return None
        payloads[name] = payload
        stored_holdout = payload.get("holdout_predictions")
        if stored_holdout is None:
            return None
        holdout_frame = stored_holdout.copy() if isinstance(stored_holdout, pd.DataFrame) else pd.DataFrame(stored_holdout)
        if holdout_frame.empty or not {"date", "actual", "predicted"}.issubset(holdout_frame.columns):
            return None
        holdout_frame["date"] = pd.to_datetime(holdout_frame["date"], errors="coerce")
        holdout_frames[name] = holdout_frame
        future_values = _recursive_predict(name, series.values, payload.get("estimator"), steps, payload["seasonal_period"])
        dates = future_dates(series, steps)
        forecasts[name] = pd.DataFrame({"date": dates, "forecast": future_values})
    successful = [row for row in metrics if row["status"] == "available"]
    if not successful or any(row["model"] not in forecasts for row in successful):
        return None
    best_model, fallback_note = _select_best_model(metrics)
    if optional_note:
        series.warnings.append(optional_note)
    if fallback_note:
        series.warnings.append(fallback_note)
    selected_metric = next(row for row in metrics if row["model"] == best_model)
    interval_radius = selected_metric.get("interval_radius")
    if interval_radius is None:
        return None
    forecasts[best_model]["lower"] = (forecasts[best_model]["forecast"] - float(interval_radius)).clip(lower=0)
    forecasts[best_model]["upper"] = forecasts[best_model]["forecast"] + float(interval_radius)
    return {
        "site": site,
        "material": material,
        "unit": series.unit,
        "frequency": frequency,
        "source_label": series.source_label,
        "horizon_days": horizon_days,
        "prediction_interval": {
            "level_pct": 90,
            "radius": float(interval_radius),
            "calibration": "pre-holdout rolling-origin absolute errors",
            "holdout_coverage_pct": selected_metric.get("prediction_interval_coverage_pct"),
        },
        "horizon_periods": steps,
        "data_hash": series.data_hash,
        "source_observations": series.source_observations,
        "calendar_periods": len(series.periods),
        "training_start": series.dates[0].date().isoformat(),
        "training_end": series.dates[-1].date().isoformat(),
        "evaluation_start": metrics[0]["test_start"],
        "evaluation_end": metrics[0]["test_end"],
        "split_index": None,
        "seasonal_period": 52 if frequency == "weekly" else 12,
        "warnings": list(dict.fromkeys(series.warnings)),
        "metrics": metrics,
        "best_model": best_model,
        "forecasts": forecasts,
        "holdout_predictions": holdout_frames,
        "payloads": payloads,
        "series": series,
        "cache_hit": True,
    }


def data_hash_for_series(
    history: pd.DataFrame,
    site: str,
    material: str,
    frequency: str,
    *,
    source_label: str = "Construction Materials Dehradun Dataset",
) -> str:
    return prepare_series(history, site, material, frequency, source_label=source_label).data_hash


def load_or_naive_assessment(
    db: Database,
    history: pd.DataFrame,
    *,
    site: str,
    material: str,
    frequency: str,
    horizon_days: int,
    source_label: str = "Construction Materials Dehradun Dataset",
) -> dict[str, Any]:
    """Load an offline-trained suite or produce a lightweight Naive fallback.

    Request handlers must not fit the tree or regression models. Those candidates
    are trained by ``scripts.train_all`` and loaded from persisted artifacts.
    """
    saved = load_saved_assessment(
        db,
        history,
        site=site,
        material=material,
        frequency=frequency,
        horizon_days=horizon_days,
        source_label=source_label,
    )
    if saved is not None:
        return saved
    assessment = evaluate_model_suite(
        history,
        site=site,
        material=material,
        frequency=frequency,
        horizon_days=horizon_days,
        model_names=["Naive"],
        source_label=source_label,
    )
    assessment["warnings"] = list(assessment["warnings"]) + [
        "No compatible offline-trained model suite is available; the Naive baseline is used. Run python -m scripts.train_all to train candidate models."
    ]
    return assessment
