from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import select

from inventory_app.analytics import aggregate_consumption, filter_history, material_usage
from inventory_app.data_quality import history_to_frame
from inventory_app.models import ApplicationSetting
from inventory_app.inventory import local_today, record_inventory_transaction
from inventory_app.models import Material, ProjectSite
from inventory_app.reports import current_inventory_report, dataframe_csv_bytes, excel_workbook_bytes
from inventory_app.settings_service import read_settings, save_settings


def test_filters_apply_and_unit_aware_exports(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        history = history_to_frame(session)
    one_series = filter_history(
        history,
        start_date=None,
        end_date=None,
        sites=["Jakhan, Dehradun"],
        materials=["Cement"],
        project_types=["Residential"],
        phases=["Foundation"],
    )
    assert len(one_series) > 0
    assert set(one_series["project_site_id"]) == {"Jakhan, Dehradun"}
    assert set(one_series["material"]) == {"Cement"}
    assert set(one_series["unit"]) == {"50-kg bags"}
    monthly = aggregate_consumption(one_series, "Monthly")
    assert set(monthly["unit"]) == {"50-kg bags"}
    usage = material_usage(one_series)
    assert len(usage) == 1
    assert usage.iloc[0]["unit"] == "50-kg bags"

    csv = dataframe_csv_bytes(usage)
    assert csv.startswith(b"\xef\xbb\xbf")
    assert b"material" in csv and b"unit" in csv
    workbook = excel_workbook_bytes({"Material usage": usage, "No rows": pd.DataFrame(columns=["site", "qty"])} )
    loaded = load_workbook(BytesIO(workbook), read_only=True)
    assert loaded.sheetnames == ["Material usage", "No rows"]
    assert list(loaded["No rows"].values)[0] == ("site", "qty")


def test_empty_csv_export_keeps_columns():
    frame = pd.DataFrame(columns=["material", "unit", "quantity"])
    payload = dataframe_csv_bytes(frame).decode("utf-8-sig")
    assert payload.splitlines()[0] == "material,unit,quantity"
    assert len(payload.splitlines()) == 1


def test_current_inventory_report_keeps_uninitialized_balances_blank(seeded_db):
    db, _ = seeded_db
    with db.session() as session:
        report = current_inventory_report(session)
        assert len(report) == 60
        assert set(report["stock_status"]) == {"Not initialized"}
        assert report["current_usable_stock"].isna().all()
        site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == "Jakhan, Dehradun"))
        material = session.scalar(select(Material).where(Material.name == "Cement"))
        record_inventory_transaction(session, idempotency_key="report-opening", site_id=site.id, material_id=material.id, transaction_type="opening_balance", quantity=20, unit=material.unit, transaction_date=local_today())
        session.commit()
    with db.session() as session:
        report = current_inventory_report(session)
        row = report.loc[(report["site"] == "Jakhan, Dehradun") & (report["material"] == "Cement")].iloc[0]
        assert row["stock_status"] == "Known operational balance"
        assert row["current_usable_stock"] == 20


def test_settings_persist_and_validate(fresh_db):
    with fresh_db.session() as session:
        saved = save_settings(session, {"safety_stock_days_default": 12, "default_forecast_frequency": "monthly", "default_forecast_horizon_days": 60, "replenishment_risk_days": 9, "currency": "INR"})
        session.commit()
    with fresh_db.session() as session:
        settings = read_settings(session)
        assert settings["safety_stock_days_default"] == 12
        assert settings["default_forecast_frequency"] == "monthly"
        assert session.get(ApplicationSetting, "default_forecast_horizon_days") is not None
