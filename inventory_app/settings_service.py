"""Validated persistence for operational defaults."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from inventory_app.database import DEFAULT_SETTINGS
from inventory_app.models import ApplicationSetting


class SettingsError(ValueError):
    pass


def read_settings(session: Session) -> dict[str, Any]:
    values = dict(DEFAULT_SETTINGS)
    for item in session.scalars(select(ApplicationSetting)).all():
        try:
            values[item.key] = json.loads(item.value_json)
        except json.JSONDecodeError:
            values[item.key] = item.value_json
    values["safety_stock_policy"] = "mean_daily_demand_times_safety_stock_days"
    return values


def save_settings(session: Session, updates: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "safety_stock_days_default",
        "default_forecast_frequency",
        "default_forecast_horizon_days",
        "replenishment_risk_days",
        "currency",
    }
    invalid = set(updates) - allowed
    if invalid:
        raise SettingsError(f"Unsupported setting(s): {', '.join(sorted(invalid))}.")
    values = read_settings(session)
    for key, value in updates.items():
        if key == "safety_stock_days_default":
            value = int(value)
            if not 0 <= value <= 60:
                raise SettingsError("Default safety-stock days must be between 0 and 60.")
        elif key == "default_forecast_frequency" and value not in {"weekly", "monthly"}:
            raise SettingsError("Default forecast frequency must be weekly or monthly.")
        elif key == "default_forecast_horizon_days":
            value = int(value)
            if value not in {7, 14, 30, 60, 90}:
                raise SettingsError("Forecast horizon must be 7, 14, 30, 60 or 90 days.")
        elif key == "replenishment_risk_days":
            value = int(value)
            if not 1 <= value <= 60:
                raise SettingsError("Replenishment risk window must be between 1 and 60 days.")
        elif key == "currency" and value != "INR":
            raise SettingsError("This project currently supports INR cost reporting only.")
        values[key] = value
        item = session.get(ApplicationSetting, key)
        if item is None:
            session.add(ApplicationSetting(key=key, value_json=json.dumps(value)))
        else:
            item.value_json = json.dumps(value)
    session.flush()
    return values
