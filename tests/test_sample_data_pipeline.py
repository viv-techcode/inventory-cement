from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, select

from inventory_app import config
from inventory_app.database import Database, initialize_database
from inventory_app.ingestion import read_csv_bytes
from inventory_app.inventory import get_current_balance
from inventory_app.models import Customer, HistoricalObservation, InventoryTransaction, Material, ProjectSite, ReorderRule, SalesRecord
from scripts.extend_dataset import generate_extension_frame, import_extension, write_extension_csv
from scripts.load_operations import CUSTOMER_NAMES, _pair_key, _unit_cost, load_sample_operations


def test_sample_extension_and_operations_are_deterministic_tagged_and_idempotent(tmp_path):
    original_bytes = config.SOURCE_CSV.read_bytes()
    source = read_csv_bytes(original_bytes)
    first = generate_extension_frame(source, as_of=date(2026, 1, 12))
    second = generate_extension_frame(source, as_of=date(2026, 1, 12))
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 120
    assert first["source_tag"].eq("sample_extension").all()
    assert first["date"].min().date() == date(2026, 1, 5)
    assert first["date"].max().date() == date(2026, 1, 12)
    assert first.groupby(["project_site_id", "material"]).size().eq(2).all()

    extension_path = tmp_path / "extension.csv"
    extension, _ = write_extension_csv(source, extension_path, as_of=date(2026, 1, 12))
    assert len(extension) == 120
    assert config.SOURCE_CSV.read_bytes() == original_bytes

    database_url = f"sqlite:///{(tmp_path / 'sample.db').as_posix()}"
    imported = import_extension(database_url, config.SOURCE_CSV, extension_path)
    assert imported["sample_extension_rows"] == 120
    database = Database(database_url)
    try:
        initialize_database(database)
        frame = read_csv_bytes(extension_path.read_bytes())
        frame["date"] = pd.to_datetime(frame["date"])
        first_load = load_sample_operations(database, frame)
        with database.session() as session:
            before = (
                session.scalar(select(func.count(InventoryTransaction.id))),
                session.scalar(select(func.count(SalesRecord.id))),
                session.scalar(select(func.count(ReorderRule.id))),
                session.scalar(select(func.count(HistoricalObservation.id))),
            )
        second_load = load_sample_operations(database, frame)
        with database.session() as session:
            after = (
                session.scalar(select(func.count(InventoryTransaction.id))),
                session.scalar(select(func.count(SalesRecord.id))),
                session.scalar(select(func.count(ReorderRule.id))),
                session.scalar(select(func.count(HistoricalObservation.id))),
            )
            costed_layers = session.scalars(select(InventoryTransaction).where(
                InventoryTransaction.source_tag == "sample_ledger",
                InventoryTransaction.transaction_type.in_(["opening_balance", "receipt"]),
            )).all()
            expected_layer_count = 60 + int(pd.to_numeric(frame["incoming_qty"]).gt(0).sum())
            assert len(costed_layers) == expected_layer_count
            assert all(txn.unit_cost_inr is not None for txn in costed_layers)
            site_names = {site.id: site.identifier for site in session.scalars(select(ProjectSite)).all()}
            material_names = {material.id: material.name for material in session.scalars(select(Material)).all()}
            for txn in costed_layers:
                pair = frame.loc[
                    (frame["project_site_id"] == site_names[txn.site_id])
                    & (frame["material"] == material_names[txn.material_id])
                ].sort_values("date")
                key = _pair_key(site_names[txn.site_id], material_names[txn.material_id])
                if txn.transaction_type == "opening_balance":
                    item = pair.iloc[0]
                    expected = _unit_cost(Decimal(str(item["unit_price_inr"])), f"{key}:opening:{pd.Timestamp(item['date']).date()}")
                else:
                    item = pair.loc[pair["date"].dt.date == txn.transaction_date].iloc[0]
                    expected = _unit_cost(Decimal(str(item["unit_price_inr"])), f"{key}:receipt:{txn.transaction_date}")
                assert Decimal(txn.unit_cost_inr) == expected
            assert session.scalar(select(func.count(SalesRecord.id)).where(SalesRecord.source_tag == "sample_ledger")) == 120
            assert session.scalar(select(func.count(SalesRecord.id)).where(SalesRecord.source_tag == "sample_ledger", SalesRecord.cost_of_goods_sold_inr.is_not(None), SalesRecord.gross_margin_inr.is_not(None))) == 120
            assert session.scalar(select(func.count(ReorderRule.id)).where(ReorderRule.source_tag == "sample_ledger")) == 60
            assert session.scalar(select(func.count(HistoricalObservation.id)).where(HistoricalObservation.source_tag == "sample_extension")) == 120
            rules = session.scalars(select(ReorderRule).where(ReorderRule.source_tag == "sample_ledger")).all()
            below = sum(
                get_current_balance(session, rule.site_id, rule.material_id) <= Decimal(rule.reorder_point_qty)
                for rule in rules
            )
            assert below == 8
            customers = session.scalars(select(Customer).where(Customer.source_tag == "sample_ledger")).all()
            assert [customer.name for customer in customers] == CUSTOMER_NAMES
            assert all(customer.email is None and customer.phone is None and "sample" not in customer.name.lower() for customer in customers)
        assert first_load["reconciled_pairs"] == second_load["reconciled_pairs"] == 60
        assert first_load["sample_customers"] == second_load["sample_customers"] == 30
        assert before == after
    finally:
        database.dispose()
    assert config.SOURCE_CSV.read_bytes() == original_bytes
