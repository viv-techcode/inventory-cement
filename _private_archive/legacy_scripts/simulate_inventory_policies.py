"""Compare forecast-driven and fixed reorder policies on stored holdout predictions.

The final chronological holdout is retrospective only. No simulated transactions
are written to the live inventory ledger.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from sqlalchemy import select

from inventory_app import config
from inventory_app.database import Database, initialize_database
from inventory_app.data_quality import history_to_frame
from inventory_app.forecasting import load_saved_assessment
from inventory_app.models import Material
from inventory_app.policy_config import HOLDING_RATE_SENSITIVITY, SHORTAGE_COST_SENSITIVITY
from inventory_app.risk import material_order_parameters


def _ceil_pack(value: float, pack: float) -> float:
    return math.ceil(max(value, 0.0) / max(pack, 1e-9)) * max(pack, 1e-9)


def _simulate(actual, forecasts, *, fixed_mean, fixed_sigma, lead_weeks, unit_price, order_cost, pack, hold_rate, shortage_multiple):
    n = len(actual)
    if n == 0:
        return None
    means = None if forecasts is None else np.maximum(np.asarray(forecasts, dtype=float), 0.0)
    actual = np.maximum(np.asarray(actual, dtype=float), 0.0)
    fixed_mean = max(0.0, float(fixed_mean))
    fixed_sigma = max(0.0, float(fixed_sigma))
    z = 1.6448536269514722
    fixed_rop = fixed_mean * lead_weeks + z * fixed_sigma * math.sqrt(lead_weeks)
    fixed_target = fixed_mean * (lead_weeks + 1.0) + z * fixed_sigma * math.sqrt(lead_weeks)
    stock = fixed_mean * (lead_weeks + 1.0)
    pipeline = []
    total_demand = total_filled = stockout_weeks = orders = 0
    holding_cost = shortage_cost = ordering_cost = 0.0
    stock_sum = 0.0
    for week in range(n):
        arriving = sum(qty for due, qty in pipeline if due <= week)
        pipeline = [(due, qty) for due, qty in pipeline if due > week]
        stock += arriving
        remaining = means[week: min(n, week + max(1, int(math.ceil(lead_weeks))))] if means is not None else []
        mean = float(np.mean(remaining)) if len(remaining) else fixed_mean
        sigma = fixed_sigma
        safety = z * sigma * math.sqrt(lead_weeks)
        position = stock + sum(qty for _, qty in pipeline)
        # Forecast policy recalculates its reorder point from the available rolling
        # holdout forecast; the fixed baseline keeps the train-only threshold.
        rop = fixed_rop if forecasts is None else mean * lead_weeks + safety
        target = fixed_target if forecasts is None else mean * (lead_weeks + 1.0) + safety
        if position <= rop:
            qty = _ceil_pack(max(0.0, target - position), pack)
            if qty > 0:
                pipeline.append((week + max(1, int(math.ceil(lead_weeks))), qty))
                orders += 1
                ordering_cost += order_cost
        demand = actual[week]
        filled = min(stock, demand)
        shortage = max(0.0, demand - stock)
        stock = max(0.0, stock - demand)
        total_demand += demand
        total_filled += filled
        stockout_weeks += int(shortage > 1e-9)
        shortage_cost += shortage * unit_price * shortage_multiple
        stock_sum += stock
        holding_cost += stock * unit_price * hold_rate / 52.0
    return {
        "service_level_pct": 100.0 * total_filled / total_demand if total_demand else 100.0,
        "stockout_weeks": stockout_weeks,
        "average_stock_qty": stock_sum / n,
        "orders": orders,
        "holding_cost_inr": holding_cost,
        "shortage_cost_inr": shortage_cost,
        "ordering_cost_inr": ordering_cost,
        "total_cost_inr": holding_cost + shortage_cost + ordering_cost,
    }


def main() -> int:
    db = Database(config.DATABASE_URL)
    initialize_database(db)
    with db.session() as session:
        history = history_to_frame(session)
        materials = {row.name: row for row in session.scalars(select(Material)).all()}
    pairs = sorted(set(zip(history.project_site_id.astype(str), history.material.astype(str))))
    rows = []
    for site, material_name in pairs:
        assessment = load_saved_assessment(
            db, history, site=site, material=material_name, frequency="weekly", horizon_days=90
        )
        if assessment is None:
            continue
        best = assessment["best_model"]
        selected = assessment["holdout_predictions"].get(best)
        naive = assessment["holdout_predictions"].get("Naive")
        if selected is None or naive is None:
            continue
        valid = selected[["actual", "predicted"]].dropna()
        if valid.empty:
            continue
        # Align Naive to the exact selected-model scored dates.
        naive = naive.set_index("date").reindex(selected.loc[valid.index, "date"])
        if naive["predicted"].isna().any():
            continue
        dates = selected.loc[valid.index, "date"].dt.strftime("%Y-%m-%d").tolist()
        actual = valid["actual"].astype(float).to_numpy()
        selected_forecast = valid["predicted"].astype(float).to_numpy()
        naive_forecast = naive["predicted"].astype(float).to_numpy()
        train = history.loc[
            (history.project_site_id.astype(str) == site)
            & (history.material.astype(str) == material_name)
            & (history.date < selected.loc[valid.index, "date"].min())
        ]["consumption_qty"].astype(float).tail(52)
        if train.empty:
            continue
        fixed_mean = float(train.mean())
        fixed_sigma = float(train.diff().dropna().std(ddof=1) or 0.0)
        metric = next(row for row in assessment["metrics"] if row["model"] == best)
        lead_days = max(1, int(materials[material_name].default_lead_time_days or 7))
        lead_weeks = lead_days / 7.0
        params = material_order_parameters(material_name, unit_price_inr=materials[material_name].benchmark_unit_price_inr)
        scenarios = {
            "selected_model": selected_forecast,
            "Naive": naive_forecast,
            "fixed_reorder_point": None,
        }
        for policy, forecast in scenarios.items():
            for holding in HOLDING_RATE_SENSITIVITY:
                for shortage in SHORTAGE_COST_SENSITIVITY:
                    result = _simulate(
                        actual, forecast, fixed_mean=fixed_mean, fixed_sigma=fixed_sigma,
                        lead_weeks=lead_weeks, unit_price=params["unit_price_inr"],
                        order_cost=params["order_cost_inr"], pack=params["pack_size"],
                        hold_rate=holding, shortage_multiple=shortage,
                    )
                    if result is None:
                        continue
                    rows.append({
                        "site": site, "material": material_name, "model_selected_by_rolling_mae": best,
                        "policy": policy, "holdout_start": dates[0], "holdout_end": dates[-1],
                        "holdout_weeks": len(actual), "lead_time_days": lead_days,
                        "holding_rate": holding, "shortage_cost_multiple": shortage,
                        "unit_price_inr_assumption": params["unit_price_inr"],
                        "order_cost_inr_assumption": params["order_cost_inr"], **result,
                    })
    db.dispose()
    out_csv = config.PROJECT_ROOT / "docs" / "policy_simulation.csv"
    out_json = config.PROJECT_ROOT / "docs" / "policy_simulation_summary.json"
    if not rows:
        print("No compatible saved holdout predictions; train all pairs before running the policy simulation.")
        return 2
    with out_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summaries = []
    groups = {}
    for row in rows:
        groups.setdefault((row["policy"], row["holding_rate"], row["shortage_cost_multiple"]), []).append(row)
    for (policy, holding, shortage), group in sorted(groups.items()):
        summaries.append({
            "policy": policy, "holding_rate": holding, "shortage_cost_multiple": shortage,
            "series_count": len({(r["site"], r["material"]) for r in group}),
            "mean_service_level_pct": float(np.mean([r["service_level_pct"] for r in group])),
            "mean_stockout_weeks": float(np.mean([r["stockout_weeks"] for r in group])),
            "mean_orders": float(np.mean([r["orders"] for r in group])),
            "mean_total_cost_inr_per_series": float(np.mean([r["total_cost_inr"] for r in group])),
        })
    out_json.write_text(json.dumps({
        "method": "Retrospective chronological holdout replay. Forecast candidate is selected using only pre-holdout rolling-origin MAE. Fixed reorder point uses training-only trailing 52-week mean and one-step-difference sigma. Baseline starting inventory is the train-only one-review-cycle target. No live ledger is modified.",
        "scenarios": {"holding_rates": HOLDING_RATE_SENSITIVITY, "shortage_cost_multiples_of_unit_value": SHORTAGE_COST_SENSITIVITY},
        "series_count": len(pairs), "simulated_series_count": len({(r['site'], r['material']) for r in rows}),
        "summary": summaries,
    }, indent=2), encoding="utf-8")
    print(f"Policy simulation complete: {len(rows)} scenarios across {len({(r['site'], r['material']) for r in rows})} series; outputs={out_csv.name}, {out_json.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
