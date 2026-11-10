"""Experimental pooled forecasting helpers; not connected to the production API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

CATEGORICAL_FEATURES = ("material", "project_site_id", "project_type", "project_phase")
NUMERIC_FEATURES = (
    "week_of_year", "month", "lag1", "lag2", "lag3", "lag4",
    "rolling_mean_4", "rolling_std_4", "unit_price_inr", "supplier_lead_time_days",
)
FEATURE_COLUMNS = (*CATEGORICAL_FEATURES, *NUMERIC_FEATURES)
TARGET_TRANSFORMS = ("raw", "log1p", "series_mean")
POOLED_MODELS = ("Pooled MLR", "Pooled Random Forest", "Pooled XGBoost")
SeriesKey = tuple[str, str]


def build_pooled_frame(
    history: pd.DataFrame,
    *,
    cutoff: pd.Timestamp | str | None = None,
) -> tuple[pd.DataFrame, np.ndarray, list[tuple[str, str, pd.Timestamp]]]:
    """Return per-series weekly lag rows and targets, using only earlier periods.

    Four initial periods are skipped for lag construction. Missing calendar weeks
    stay missing, which breaks lag windows rather than bridging a gap.
    """
    required = {"date", "project_site_id", "material", "consumption_qty"}
    if not required.issubset(history.columns):
        missing = ", ".join(sorted(required - set(history.columns)))
        raise ValueError(f"Pooled forecast source lacks required columns: {missing}.")
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["consumption_qty"] = pd.to_numeric(frame["consumption_qty"], errors="coerce")
    frame = frame.dropna(subset=["date", "consumption_qty"])
    boundary = pd.Timestamp(cutoff) if cutoff is not None else None
    rows: list[dict[str, Any]] = []
    targets: list[float] = []
    keys: list[tuple[str, str, pd.Timestamp]] = []

    metadata = [column for column in ("project_type", "project_phase", "unit_price_inr", "supplier_lead_time_days") if column in frame]
    for (site, material), group in frame.groupby(["project_site_id", "material"], sort=True):
        group = group.sort_values("date").copy()
        group["period"] = group["date"].dt.to_period("W-SUN")
        agg = group.groupby("period").agg(
            consumption_qty=("consumption_qty", "sum"),
            **{column: (column, "last") for column in metadata},
        )
        if agg.empty:
            continue
        periods = pd.period_range(agg.index.min(), agg.index.max(), freq="W-SUN")
        agg = agg.reindex(periods)
        values = agg["consumption_qty"].to_numpy(dtype=float)

        for index in range(4, len(agg)):
            period = periods[index]
            # A target week is trainable only after that week is complete before
            # the chronological boundary.
            period_end = period.end_time.normalize()
            if boundary is not None and period_end >= boundary.normalize():
                continue
            past = values[index - 4:index]
            target = values[index]
            if not np.isfinite(past).all() or not np.isfinite(target):
                continue
            week_start = period.start_time
            row: dict[str, Any] = {
                "material": str(material),
                "project_site_id": str(site),
                "week_of_year": int(week_start.isocalendar().week),
                "month": int(week_start.month),
                "lag1": float(past[-1]), "lag2": float(past[-2]),
                "lag3": float(past[-3]), "lag4": float(past[-4]),
                "rolling_mean_4": float(past.mean()),
                "rolling_std_4": float(past.std(ddof=0)),
            }
            for column in ("project_type", "project_phase"):
                value = agg.iloc[index][column] if column in agg else None
                row[column] = str(value) if pd.notna(value) else "unknown"
            for column in ("unit_price_inr", "supplier_lead_time_days"):
                value = agg.iloc[index][column] if column in agg else 0.0
                row[column] = float(value) if pd.notna(value) else 0.0
            rows.append(row)
            targets.append(float(target))
            keys.append((str(site), str(material), week_start))

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS), np.asarray(targets, dtype=float), keys


def transform_target(target: Iterable[float] | np.ndarray, transform: str, scale: float | np.ndarray = 1.0) -> np.ndarray:
    """Apply raw, log1p, or training-mean scaling to nonnegative targets."""
    values = np.asarray(target, dtype=float)
    if transform == "raw":
        return values.copy()
    if transform == "log1p":
        return np.log1p(np.maximum(values, 0.0))
    if transform == "series_mean":
        divisor = np.asarray(scale, dtype=float)
        divisor = np.where(divisor > 0, divisor, 1.0)
        return values / divisor
    raise ValueError(f"Unknown target transform: {transform}")


def inverse_target_transform(
    prediction: Iterable[float] | np.ndarray,
    transform: str,
    scale: float | np.ndarray = 1.0,
    *,
    max_training_target: float | None = None,
    fallback: float | np.ndarray = 0.0,
) -> np.ndarray:
    """Invert a target transform and clip resulting demand predictions at zero."""
    values = np.asarray(prediction, dtype=float)
    if transform == "log1p":
        if max_training_target is not None:
            values = np.clip(values, 0.0, np.log1p(max(0.0, float(max_training_target)) * 3.0))
        with np.errstate(over="ignore", invalid="ignore"):
            values = np.expm1(values)
    elif transform == "series_mean":
        values = values * np.asarray(scale, dtype=float)
    elif transform != "raw":
        raise ValueError(f"Unknown target transform: {transform}")
    values = np.maximum(values, 0.0)
    return np.where(np.isfinite(values), values, np.maximum(np.asarray(fallback, dtype=float), 0.0))


def _preprocessor(model_name: str) -> ColumnTransformer:
    if model_name == "Pooled MLR":
        return ColumnTransformer([
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(CATEGORICAL_FEATURES)),
            ("numeric", StandardScaler(), list(NUMERIC_FEATURES)),
        ])
    return ColumnTransformer([
        ("categorical", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), list(CATEGORICAL_FEATURES)),
        ("numeric", "passthrough", list(NUMERIC_FEATURES)),
    ])


def _estimator(model_name: str):
    if model_name == "Pooled MLR":
        return LinearRegression()
    if model_name == "Pooled Random Forest":
        return RandomForestRegressor(n_estimators=250, max_depth=8, min_samples_leaf=2, random_state=42, n_jobs=1)
    if model_name == "Pooled XGBoost":
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise ImportError("Pooled XGBoost requires the optional xgboost dependency.") from exc
        return XGBRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.04, subsample=0.85,
            colsample_bytree=0.85, reg_lambda=2.0, objective="reg:squarederror",
            random_state=42, n_jobs=1, verbosity=0,
        )
    raise ValueError(f"Unknown pooled model: {model_name}")


@dataclass
class PooledModel:
    name: str
    target_transform: str
    estimator: Any
    training_means: dict[SeriesKey, float]
    global_training_mean: float
    last_training_values: dict[SeriesKey, float]
    max_training_target: float
    nonfinite_replacements: int = 0


def fit_pooled_models(
    history: pd.DataFrame,
    *,
    cutoff: pd.Timestamp | str,
    model_names: Iterable[str] = POOLED_MODELS,
    target_transforms: Iterable[str] = TARGET_TRANSFORMS,
) -> dict[tuple[str, str], PooledModel]:
    """Fit pooled candidates on targets strictly before a chronological cutoff."""
    features, targets, keys = build_pooled_frame(history, cutoff=cutoff)
    if len(targets) < 2:
        raise ValueError("At least two valid pooled training rows are required.")
    grouped: dict[SeriesKey, list[float]] = {}
    for key, target in zip(keys, targets):
        grouped.setdefault(key[:2], []).append(float(target))
    means = {series: float(np.mean(values)) for series, values in grouped.items()}
    last_values = {key: float(target) for key, target in zip(keys, targets)}
    row_scales = np.asarray([means[key[:2]] for key in keys], dtype=float)

    fitted: dict[tuple[str, str], PooledModel] = {}
    for transform in target_transforms:
        if transform not in TARGET_TRANSFORMS:
            raise ValueError(f"Unknown target transform: {transform}")
        y_train = transform_target(targets, transform, row_scales)
        for name in model_names:
            estimator = make_pipeline(_preprocessor(name), _estimator(name))
            estimator.fit(features, y_train)
            fitted[(name, transform)] = PooledModel(
                name=name,
                target_transform=transform,
                estimator=estimator,
                training_means=means,
                global_training_mean=float(np.mean(targets)),
                last_training_values=last_values,
                max_training_target=float(np.max(targets)),
            )
    return fitted


def predict_pooled(model: PooledModel, features: pd.DataFrame) -> np.ndarray:
    """Predict from pooled feature rows, ignoring unseen one-hot categories safely."""
    missing = set(FEATURE_COLUMNS) - set(features.columns)
    if missing:
        raise ValueError(f"Pooled prediction features are missing columns: {', '.join(sorted(missing))}.")
    raw = model.estimator.predict(features.loc[:, FEATURE_COLUMNS])
    fallback = np.asarray([
        model.last_training_values.get((str(row.project_site_id), str(row.material)), model.global_training_mean)
        for row in features.itertuples(index=False)
    ], dtype=float)
    model.nonfinite_replacements += int(np.count_nonzero(~np.isfinite(raw)))
    if model.target_transform == "series_mean":
        scales = np.asarray([
            model.training_means.get((str(row.project_site_id), str(row.material)), model.global_training_mean)
            for row in features.itertuples(index=False)
        ], dtype=float)
    else:
        scales = 1.0
    result = inverse_target_transform(
        raw, model.target_transform, scales,
        max_training_target=model.max_training_target,
        fallback=fallback,
    )
    return result


def choose_pooled_or_naive(naive_mae: float, pooled_maes: dict[tuple[str, str], float]) -> tuple[str, str | None]:
    """Choose the best pooled candidate only when it strictly beats Naive."""
    if not np.isfinite(naive_mae):
        return "Naive", None
    available = [(key, value) for key, value in pooled_maes.items() if np.isfinite(value)]
    if not available:
        return "Naive", None
    (model_name, transform), pooled_mae = min(available, key=lambda item: (item[1], item[0]))
    if pooled_mae < naive_mae:
        return model_name, transform
    return "Naive", None


def _series_panels(history: pd.DataFrame):
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["consumption_qty"] = pd.to_numeric(frame["consumption_qty"], errors="coerce")
    frame = frame.dropna(subset=["date", "consumption_qty"])
    frame["period"] = frame["date"].dt.to_period("W-SUN")
    metadata = [column for column in ("project_type", "project_phase", "unit_price_inr", "supplier_lead_time_days") if column in frame]
    panels = {}
    for (site, material), group in frame.groupby(["project_site_id", "material"], sort=True):
        agg = group.groupby("period").agg(
            consumption_qty=("consumption_qty", "sum"),
            **{column: (column, "last") for column in metadata},
        )
        panels[(str(site), str(material))] = agg
    if not panels:
        raise ValueError("No usable weekly site/material series are available for pooled evaluation.")
    all_periods = pd.period_range(
        min(panel.index.min() for panel in panels.values()),
        max(panel.index.max() for panel in panels.values()),
        freq="W-SUN",
    )
    for key, panel in list(panels.items()):
        panels[key] = panel.reindex(all_periods)
    return panels, all_periods


def _feature_at(key: SeriesKey, panel: pd.DataFrame, periods: pd.PeriodIndex, index: int, context: list[float]):
    if index < 4 or len(context) < 4:
        return None
    past = np.asarray(context[-4:], dtype=float)
    if not np.isfinite(past).all():
        return None
    week_start = periods[index].start_time
    meta = panel.iloc[index]
    row: dict[str, Any] = {
        "material": key[1], "project_site_id": key[0],
        "week_of_year": int(week_start.isocalendar().week), "month": int(week_start.month),
        "lag1": float(past[-1]), "lag2": float(past[-2]), "lag3": float(past[-3]), "lag4": float(past[-4]),
        "rolling_mean_4": float(past.mean()), "rolling_std_4": float(past.std(ddof=0)),
    }
    for column in ("project_type", "project_phase"):
        value = meta[column] if column in meta else None
        row[column] = str(value) if pd.notna(value) else "unknown"
    for column in ("unit_price_inr", "supplier_lead_time_days"):
        value = meta[column] if column in meta else 0.0
        row[column] = float(value) if pd.notna(value) else 0.0
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def _last_finite(values: list[float], default: float = 0.0) -> float:
    for value in reversed(values):
        if np.isfinite(value):
            return float(value)
    return default


def _walk_series(key, panel, periods, start, end, model=None):
    actual = panel["consumption_qty"].to_numpy(dtype=float)
    context = [float(value) for value in actual[:start]]
    predicted, observed = [], []
    for index in range(start, end):
        features = _feature_at(key, panel, periods, index, context)
        if model is None or features is None:
            value = _last_finite(context)
        else:
            value = float(predict_pooled(model, features)[0])
        predicted.append(value)
        observed.append(float(actual[index]))
        context.append(value)
    return np.asarray(observed), np.asarray(predicted)


def _metric_summary(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int | None]:
    mask = np.isfinite(actual) & np.isfinite(predicted)
    y, p = actual[mask], predicted[mask]
    if not len(y):
        return {"mae": None, "rmse": None, "r2": None, "wape_pct": None, "observations": 0}
    error = p - y
    total = float(np.abs(y).sum())
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "r2": float(r2_score(y, p)) if len(y) > 1 and float(np.var(y)) > 1e-12 else None,
        "wape_pct": float(np.abs(error).sum() / total * 100.0) if total > 1e-12 else None,
        "observations": int(len(y)),
    }


def _macro_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for metric in ("mae", "rmse", "r2", "wape_pct", "backtest_mae"):
        values = [float(row[metric]) for row in rows if row.get(metric) is not None and np.isfinite(row[metric])]
        result[metric] = {
            "mean": float(np.mean(values)) if values else None,
            "median": float(np.median(values)) if values else None,
            "series_count": len(values),
        }
    return result


def evaluate_pooled(
    history: pd.DataFrame,
    *,
    model_names: Iterable[str] = POOLED_MODELS,
    target_transforms: Iterable[str] = TARGET_TRANSFORMS,
) -> dict[str, Any]:
    """Evaluate pooled candidates on three rolling folds and an untouched holdout.

    The transform is selected separately for each model using the macro-mean
    per-series backtest MAE. Per series, the best selected pooled model is used
    only when its backtest MAE is strictly lower than the Naive baseline.
    """
    model_names = tuple(model_names)
    target_transforms = tuple(target_transforms)
    if not model_names or not target_transforms:
        raise ValueError("At least one pooled model and target transform must be selected.")
    unknown_models = set(model_names) - set(POOLED_MODELS)
    unknown_transforms = set(target_transforms) - set(TARGET_TRANSFORMS)
    if unknown_models or unknown_transforms:
        raise ValueError(f"Unknown pooled candidates: {sorted(unknown_models | unknown_transforms)}")
    panels, periods = _series_panels(history)
    n_periods = len(periods)
    split = max(18, int(np.floor(n_periods * 0.8)))
    if split >= n_periods - 2:
        split = n_periods - max(4, int(np.ceil(n_periods * 0.2)))
    first_origin = max(18, int(np.floor(split * 0.55)))
    final_origin = max(first_origin + 3, int(np.floor(split * 0.80)))
    origins = np.linspace(first_origin, final_origin, num=4, dtype=int)[:-1]
    folds = [(int(origin), int(next_origin)) for origin, next_origin in zip(origins, [*origins[1:], final_origin]) if next_origin > origin]
    if len(folds) != 3 or split >= n_periods:
        raise ValueError("Pooled evaluation requires enough weekly history for three rolling folds and a final holdout.")

    candidates = [(str(name), str(transform)) for name in model_names for transform in target_transforms]
    candidate_errors: dict[tuple[str, str], dict[SeriesKey, list[float]]] = {candidate: {} for candidate in candidates}
    naive_errors: dict[SeriesKey, list[float]] = {key: [] for key in panels}
    failures: dict[str, str] = {}
    for fold_index, (origin, fold_end) in enumerate(folds):
        cutoff = periods[origin].start_time
        for name, transform in candidates:
            try:
                model = fit_pooled_models(
                    history, cutoff=cutoff, model_names=(name,), target_transforms=(transform,),
                )[(name, transform)]
            except (ImportError, ValueError) as exc:
                failures[name] = f"{type(exc).__name__}: {exc}"
                continue
            for key, panel in panels.items():
                actual, predicted = _walk_series(key, panel, periods, origin, fold_end, model)
                mask = np.isfinite(actual)
                candidate_errors[(name, transform)].setdefault(key, []).extend(np.abs(predicted[mask] - actual[mask]).tolist())
        for key, panel in panels.items():
            actual, predicted = _walk_series(key, panel, periods, origin, fold_end)
            mask = np.isfinite(actual)
            naive_errors[key].extend(np.abs(predicted[mask] - actual[mask]).tolist())

    transform_selection = {}
    for name in dict.fromkeys(name for name, _ in candidates):
        transform_scores = {}
        for candidate_name, transform in candidates:
            if candidate_name != name:
                continue
            per_series = [float(np.mean(errors)) for errors in candidate_errors[(candidate_name, transform)].values() if errors]
            transform_scores[transform] = float(np.mean(per_series)) if per_series else None
        valid = [(transform, score) for transform, score in transform_scores.items() if score is not None]
        if valid:
            selected_transform, selected_score = min(valid, key=lambda item: (item[1], item[0]))
            transform_selection[name] = {"transform": selected_transform, "backtest_mae_macro_mean": selected_score, "scores_by_transform": transform_scores}

    selected_candidates = {
        (name, details["transform"])
        for name, details in transform_selection.items()
    }
    final_models = {}
    holdout_errors: dict[tuple[str, str], dict[SeriesKey, tuple[np.ndarray, np.ndarray]]] = {}
    cutoff = periods[split].start_time
    for name, transform in sorted(selected_candidates):
        try:
            final_models[(name, transform)] = fit_pooled_models(
                history, cutoff=cutoff, model_names=(name,), target_transforms=(transform,),
            )[(name, transform)]
        except (ImportError, ValueError) as exc:
            failures[name] = f"{type(exc).__name__}: {exc}"
            continue
        series_holdouts = {}
        for key, panel in panels.items():
            series_holdouts[key] = _walk_series(key, panel, periods, split, n_periods, final_models[(name, transform)])
        holdout_errors[(name, transform)] = series_holdouts

    series_results = []
    for key, panel in panels.items():
        naive_actual, naive_pred = _walk_series(key, panel, periods, split, n_periods)
        naive_holdout = _metric_summary(naive_actual, naive_pred)
        naive_backtest = float(np.mean(naive_errors[key])) if naive_errors[key] else None
        candidate_maes = {}
        for candidate in selected_candidates:
            errors = candidate_errors[candidate].get(key, [])
            if errors and candidate in holdout_errors:
                candidate_maes[candidate] = float(np.mean(errors))
        selected_model, selected_transform = choose_pooled_or_naive(
            naive_backtest if naive_backtest is not None else float("nan"), candidate_maes
        )
        if selected_model == "Naive":
            after_metrics = naive_holdout
            selected_backtest = naive_backtest
        else:
            actual, predicted = holdout_errors[(selected_model, selected_transform)][key]
            after_metrics = _metric_summary(actual, predicted)
            selected_backtest = candidate_maes[(selected_model, selected_transform)]
        series_results.append({
            "site": key[0], "material": key[1],
            "selected_model": selected_model, "selected_transform": selected_transform,
            "fallback_to_naive": selected_model == "Naive",
            "selection_reason": (
                "No pooled candidate strictly beat Naive on backtest MAE; used Naive."
                if selected_model == "Naive"
                else "Selected pooled candidate with the lowest eligible backtest MAE, which was strictly below Naive."
            ),
            "naive_backtest_mae": naive_backtest,
            "selected_backtest_mae": selected_backtest,
            "before": naive_holdout, "after": after_metrics,
        })

    before_rows = [{**row["before"], "backtest_mae": row["naive_backtest_mae"]} for row in series_results]
    after_rows = [{**row["after"], "backtest_mae": row["selected_backtest_mae"]} for row in series_results]
    materials = sorted({row["material"] for row in series_results})
    per_material = {}
    for material in materials:
        pairs = [row for row in series_results if row["material"] == material]
        per_material[material] = {
            "before_naive": _macro_summary([{**row["before"], "backtest_mae": row["naive_backtest_mae"]} for row in pairs]),
            "after_pooled_or_naive": _macro_summary([{**row["after"], "backtest_mae": row["selected_backtest_mae"]} for row in pairs]),
            "series_count": len(pairs),
        }
    pooled_count = sum(not row["fallback_to_naive"] for row in series_results)
    return {
        "status": "evaluated",
        "method": "3 expanding-window rolling-origin folds before untouched final 20% holdout; selection only by backtest MAE",
        "calendar_periods": n_periods,
        "holdout_start": str(periods[split].start_time.date()),
        "holdout_end": str(periods[-1].end_time.date()),
        "folds": [{"origin_index": start, "end_index_exclusive": end} for start, end in folds],
        "transform_selection": transform_selection,
        "unavailable_candidates": failures,
        "overall": {"before_naive": _macro_summary(before_rows), "after_pooled_or_naive": _macro_summary(after_rows)},
        "per_material": per_material,
        "series": series_results,
        "pooled_selected_series": pooled_count,
        "series_count": len(series_results),
        "pooled_beats_naive_in_most_series": pooled_count > len(series_results) / 2,
    }
