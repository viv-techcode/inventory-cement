"""Load deterministic, tagged sample transactions reconciled to sample-extension rows.

The sample ledger is intentionally separate from original CSV history. Each site/material
gets one synthetic opening count, extension-aligned receipts and sales, a 30-account generic
customer pool, and one reorder rule. Opening and receipt costs are deterministic fractions
of that week's dataset unit price for sample FIFO valuation.

Run after ``python -m scripts.extend_dataset``:

    python -m scripts.load_operations
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

from inventory_app import config
from inventory_app.database import Database, initialize_database
from inventory_app.ingestion import EXPECTED_COLUMNS, read_csv_bytes
from inventory_app.inventory import get_current_balance, record_inventory_transaction
from inventory_app.models import (
    Customer,
    HistoricalObservation,
    InventoryTransaction,
    Material,
    ProjectSite,
    ReorderRule,
    SalesRecord,
)
from inventory_app.reorder import save_reorder_rule
from inventory_app.sales import create_customer, create_sale
from scripts.extend_dataset import (
    EXTENSION_COLUMNS,
    SAMPLE_TAG as EXTENSION_TAG,
    current_week_monday,
    import_extension,
)

SAMPLE_TAG = "sample_ledger"
QTY_STEP = Decimal("0.0001")
MONEY_STEP = Decimal("0.01")
CUSTOMER_COUNT = 30
CUSTOMER_NAMES = [
    "Rawat Constructions", "Bisht Builders", "Negi Civil Works", "Rana Infra Projects",
    "Chauhan Building Supplies", "Kandari Contractors", "Bhandari Developers", "Rawat Builders",
    "Joshi Construction Co", "Thakur Buildmart", "Semwal Infratech", "Panwar Contractors",
    "Kukreti Builders", "Gusain Civil Contractors", "Nautiyal Enterprises", "Dixit Building Works",
    "Agarwal Construction Supply", "Sharma Building Materials", "Verma Contractors", "Singh Infra",
    "Kapoor Hardware & Build", "Mehta Construction Depot", "Saini Builders", "Arora Civil Works",
    "Mishra Building Traders", "Yadav Contractors", "Kumar Infra Solutions", "Gupta Buildwell",
    "Das Construction Services", "Patel Building Mart",
]


def _decimal(value: object, field: str) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"{field} must be finite.")
    return result


def _q(value: Decimal) -> Decimal:
    return value.quantize(QTY_STEP, rounding=ROUND_HALF_UP)


def _unit_cost(price: Decimal, key: str) -> Decimal:
    """Stable 82–93% cost fraction, keyed to the specific ledger layer."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    fraction = Decimal(82) + Decimal(int.from_bytes(digest[:4], "big")) * Decimal(11) / Decimal(2**32)
    return (price * fraction / Decimal(100)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _pair_key(site: str, material: str) -> str:
    digest = hashlib.sha256(f"{site}\0{material}".encode("utf-8")).hexdigest()[:24]
    return digest


def validate_extension_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [name for name in EXTENSION_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"Sample extension is missing fields: {missing}")
    if frame["source_tag"].astype(str).ne(EXTENSION_TAG).any():
        raise ValueError("Every extension row must have source_tag=sample_extension.")
    result = frame.loc[:, EXTENSION_COLUMNS].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    if result.empty:
        raise ValueError("The sample extension contains no rows.")
    if result[["project_site_id", "material", "date"]].duplicated().any():
        raise ValueError("The sample extension contains duplicate site/material/date rows.")
    if len(result.groupby(["project_site_id", "material"], dropna=False)) != 60:
        raise ValueError("Expected sample rows for all 60 site/material pairs.")
    for column in ("consumption_qty", "opening_stock_qty", "incoming_qty", "unit_price_inr"):
        values = pd.to_numeric(result[column], errors="coerce")
        if values.isna().any() or not values.map(lambda value: Decimal(str(value)).is_finite()).all():
            raise ValueError(f"Sample extension has a missing or non-finite {column} value.")
        if (values < 0).any() or (column == "unit_price_inr" and (values <= 0).any()):
            raise ValueError(f"Sample extension has an invalid negative/zero {column} value.")
    result = result.sort_values(["project_site_id", "material", "date"], kind="stable").reset_index(drop=True)
    for (site, material), series in result.groupby(["project_site_id", "material"], sort=False):
        series = series.sort_values("date")
        intervals = series["date"].diff().dropna().dt.days
        if len(intervals) and not intervals.eq(7).all():
            raise ValueError(f"Sample extension is not weekly for {site} / {material}.")
        values = series.to_dict(orient="records")
        previous_close: Decimal | None = None
        for row in values:
            opening = _q(_decimal(row["opening_stock_qty"], "opening_stock_qty"))
            incoming = _q(_decimal(row["incoming_qty"], "incoming_qty"))
            consumption = _q(_decimal(row["consumption_qty"], "consumption_qty"))
            closing = _q(opening + incoming - consumption)
            if opening < 0 or incoming < 0 or consumption <= 0 or closing < 0:
                raise ValueError(f"Invalid stock flow in sample extension for {site} / {material}.")
            if previous_close is not None and abs(opening - previous_close) > QTY_STEP:
                raise ValueError(f"Extension opening stock does not roll forward for {site} / {material}.")
            previous_close = closing
    return result


def _assert_existing_transaction(
    existing: InventoryTransaction,
    *,
    site_id: int,
    material_id: int,
    transaction_type: str,
    quantity: Decimal,
    unit: str,
    transaction_date: date,
    source: str,
    reference: str,
    unit_cost_inr: Decimal,
) -> None:
    matches = (
        existing.site_id == site_id
        and existing.material_id == material_id
        and existing.transaction_type == transaction_type
        and _q(Decimal(existing.quantity)) == _q(quantity)
        and existing.unit == unit
        and existing.transaction_date == transaction_date
        and existing.source == source
        and existing.source_tag == SAMPLE_TAG
        and existing.reference == reference
        and (existing.unit_cost_inr is None or Decimal(existing.unit_cost_inr) == unit_cost_inr)
    )
    if not matches:
        raise RuntimeError(f"Existing idempotency entry {existing.idempotency_key!r} differs from the expected sample record; no overwrite performed.")
    if existing.unit_cost_inr is None:
        existing.unit_cost_inr = unit_cost_inr


def _record_idempotent_transaction(
    session,
    *,
    idempotency_key: str,
    site_id: int,
    material_id: int,
    transaction_type: str,
    quantity: Decimal,
    unit: str,
    transaction_date: date,
    source: str,
    reference: str,
    unit_cost_inr: Decimal,
):
    existing = session.scalar(
        select(InventoryTransaction).where(InventoryTransaction.idempotency_key == idempotency_key)
    )
    if existing is not None:
        _assert_existing_transaction(
            existing,
            site_id=site_id,
            material_id=material_id,
            transaction_type=transaction_type,
            quantity=quantity,
            unit=unit,
            transaction_date=transaction_date,
            source=source,
            reference=reference,
            unit_cost_inr=unit_cost_inr,
        )
        return existing, False
    txn = record_inventory_transaction(
        session,
        idempotency_key=idempotency_key,
        site_id=site_id,
        material_id=material_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit=unit,
        transaction_date=transaction_date,
        source=source,
        source_tag=SAMPLE_TAG,
        reference=reference,
        unit_cost_inr=unit_cost_inr,
    )
    return txn, True


def _ensure_customers(session) -> list[Customer]:
    customers: list[Customer] = []
    tagged = session.scalars(select(Customer).where(Customer.source_tag == SAMPLE_TAG).order_by(Customer.id)).all()
    by_name = {customer.name.casefold(): customer for customer in tagged}
    for index in range(1, CUSTOMER_COUNT + 1):
        name = CUSTOMER_NAMES[index - 1]
        customer = tagged[index - 1] if len(tagged) >= CUSTOMER_COUNT else by_name.get(name.casefold())
        if customer is not None and customer.name != name:
            customer.name = name
        if customer is None:
            customer = session.scalar(select(Customer).where(func.lower(Customer.name) == name.lower()))
        if customer is None:
            customer = create_customer(
                session,
                name=name,
                email=None,
                source_tag=SAMPLE_TAG,
            )
        elif customer.source_tag != SAMPLE_TAG:
            raise RuntimeError(f"Customer name {name!r} is already owned by a non-sample record; refusing to modify it.")
        customer.email = None
        customer.phone = None
        customers.append(customer)
    return customers


def _verify_sample_observations(session, frame: pd.DataFrame) -> None:
    rows = session.scalars(
        select(HistoricalObservation).where(HistoricalObservation.source_tag == EXTENSION_TAG)
    ).all()
    if len(rows) != len(frame):
        raise RuntimeError(f"Expected {len(frame)} sample_extension observations in the DB, found {len(rows)}.")
    stored = {
        (row.project_site_id, row.material, row.observation_datetime): row
        for row in rows
    }
    for item in frame.to_dict(orient="records"):
        key = (str(item["project_site_id"]), str(item["material"]), item["date"].to_pydatetime())
        row = stored.get(key)
        if row is None:
            raise RuntimeError(f"Sample extension row is absent from the DB: {key}.")
        for field in ("consumption_qty", "opening_stock_qty", "incoming_qty", "unit_price_inr"):
            if _q(Decimal(getattr(row, field))) != _q(_decimal(item[field], field)):
                raise RuntimeError(f"Database sample row does not match extension file for {key} ({field}).")


def load_sample_operations(database: Database, raw_frame: pd.DataFrame) -> dict[str, int | str]:
    """Idempotently add synthetic operations and assert weekly balance reconciliation."""
    frame = validate_extension_frame(raw_frame)
    inserted_openings = 0
    inserted_receipts = 0
    inserted_sales = 0
    pair_count = 0
    with database.session() as session:
        with session.begin():
            _verify_sample_observations(session, frame)
            sites = {site.identifier: site for site in session.scalars(select(ProjectSite)).all()}
            materials = {material.name: material for material in session.scalars(select(Material)).all()}
            customers = _ensure_customers(session)
            for pair_index, ((site_name, material_name), raw_series) in enumerate(
                frame.groupby(["project_site_id", "material"], sort=True, dropna=False)
            ):
                site = sites.get(str(site_name))
                material = materials.get(str(material_name))
                if site is None or material is None or not site.is_active or not material.is_active:
                    raise RuntimeError(f"Missing or inactive catalogue entry: {site_name} / {material_name}.")
                if material.unit != str(raw_series.iloc[0]["unit"]):
                    raise RuntimeError(f"Unit mismatch for {site_name} / {material_name}.")
                series = raw_series.sort_values("date", kind="stable").reset_index(drop=True)
                first_date = series.iloc[0]["date"].date()
                opening_date = first_date - timedelta(days=1)
                key = _pair_key(str(site_name), str(material_name))
                opening_qty = _q(_decimal(series.iloc[0]["opening_stock_qty"], "opening_stock_qty"))
                opening_cost = _unit_cost(_decimal(series.iloc[0]["unit_price_inr"], "unit_price_inr"), f"{key}:opening:{first_date}")
                opening_key = f"sample-ledger:open:{key}"
                existing_opening = session.scalar(
                    select(InventoryTransaction).where(InventoryTransaction.idempotency_key == opening_key)
                )
                if existing_opening is None:
                    other = session.scalar(
                        select(InventoryTransaction.id).where(
                            InventoryTransaction.site_id == site.id,
                            InventoryTransaction.material_id == material.id,
                        ).limit(1)
                    )
                    if other is not None:
                        raise RuntimeError(f"A non-seeded ledger already exists for {site_name} / {material_name}; refusing to mix sources.")
                _, created = _record_idempotent_transaction(
                    session,
                    idempotency_key=opening_key,
                    site_id=site.id,
                    material_id=material.id,
                    transaction_type="opening_balance",
                    quantity=opening_qty,
                    unit=material.unit,
                    transaction_date=opening_date,
                    source="manual",
                    reference=f"OPEN-{key[:8]}-{opening_date:%Y%m%d}",
                    unit_cost_inr=opening_cost,
                )
                inserted_openings += int(created)

                for week_index, item in enumerate(series.to_dict(orient="records")):
                    row_date = item["date"].date()
                    expected_opening = _q(_decimal(item["opening_stock_qty"], "opening_stock_qty"))
                    before = get_current_balance(session, site.id, material.id, as_of=row_date - timedelta(days=1))
                    if before is None or abs(_q(before) - expected_opening) > QTY_STEP:
                        raise RuntimeError(f"Pre-row sample ledger balance does not match the dataset opening for {site_name} / {material_name} on {row_date}.")
                    incoming = _q(_decimal(item["incoming_qty"], "incoming_qty"))
                    if incoming > 0:
                        receipt_key = f"sample-ledger:receipt:{key}:{row_date:%Y%m%d}"
                        _, created = _record_idempotent_transaction(
                            session,
                            idempotency_key=receipt_key,
                            site_id=site.id,
                            material_id=material.id,
                            transaction_type="receipt",
                            quantity=incoming,
                            unit=material.unit,
                            transaction_date=row_date,
                            source="manual",
                            reference=f"RCPT-{key[:8]}-{row_date:%Y%m%d}",
                            unit_cost_inr=_unit_cost(_decimal(item["unit_price_inr"], "unit_price_inr"), f"{key}:receipt:{row_date}"),
                        )
                        inserted_receipts += int(created)
                    quantity = _q(_decimal(item["consumption_qty"], "consumption_qty"))
                    price = (_decimal(item["unit_price_inr"], "unit_price_inr") * Decimal("1.05")).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
                    customer = customers[(pair_index * 7 + week_index) % len(customers)]
                    sale_key = f"sample-ledger:sale:{key}:{row_date:%Y%m%d}"
                    sale_reference = f"INV-{key[:8]}-{row_date:%Y%m%d}"
                    sale, created = create_sale(
                        session,
                        idempotency_key=sale_key,
                        site_id=site.id,
                        material_id=material.id,
                        customer_id=customer.id,
                        quantity=quantity,
                        unit=material.unit,
                        unit_sale_price_inr=price,
                        sale_date=row_date,
                        reference=sale_reference,
                        source_tag=SAMPLE_TAG,
                    )
                    if not created and (sale.source_tag != SAMPLE_TAG or sale.quantity != quantity):
                        raise RuntimeError(f"Existing sale {sale_key!r} differs from the deterministic sample payload.")
                    inserted_sales += int(created)
                    expected_close = _q(expected_opening + incoming - quantity)
                    actual_close = get_current_balance(session, site.id, material.id, as_of=row_date)
                    if actual_close is None or abs(_q(actual_close) - expected_close) > QTY_STEP:
                        raise RuntimeError(f"Sample ledger does not reconcile for {site_name} / {material_name} on {row_date}.")
                pair_count += 1

                recent = series.tail(8)
                avg_weekly = sum((_decimal(value, "consumption_qty") for value in recent["consumption_qty"]), Decimal("0")) / Decimal(len(recent))
                lead_days = max(1, int(round(float(recent["supplier_lead_time_days"].median()))))
                safety_days = 7
                reorder_point = _q(avg_weekly * Decimal(lead_days + safety_days) / Decimal(7))
                existing_rule = session.scalar(
                    select(ReorderRule).where(ReorderRule.site_id == site.id, ReorderRule.material_id == material.id)
                )
                if existing_rule is not None and existing_rule.source_tag != SAMPLE_TAG:
                    raise RuntimeError(f"A non-sample reorder rule already exists for {site_name} / {material_name}; refusing to overwrite it.")
                save_reorder_rule(
                    session,
                    site_id=site.id,
                    material_id=material.id,
                    unit=material.unit,
                    reorder_point_qty=reorder_point,
                    lead_time_days=lead_days,
                    safety_stock_days=safety_days,
                    minimum_order_qty=Decimal("0"),
                    order_multiple=Decimal("0"),
                    maximum_stock_qty=None,
                    is_active=True,
                    notes=None,
                    source_tag=SAMPLE_TAG,
                )

            if pair_count != 60:
                raise RuntimeError(f"Expected 60 seeded site/material pairs, completed {pair_count}.")
            # Keep a small, useful alert queue in the synthetic preview: mark the eight
            # lowest weeks-of-cover pairs below their reorder point, without changing stock.
            ranked: list[tuple[Decimal, ProjectSite, Material, Decimal]] = []
            for (site_name, material_name), raw_series in frame.groupby(["project_site_id", "material"], sort=True):
                site = sites[str(site_name)]
                material = materials[str(material_name)]
                stock = get_current_balance(session, site.id, material.id)
                recent = raw_series.tail(8)
                weekly_use = sum((_decimal(value, "consumption_qty") for value in recent["consumption_qty"]), Decimal("0")) / Decimal(len(recent))
                if stock is None or stock < 0 or weekly_use <= 0:
                    raise RuntimeError(f"Invalid stock/consumption while tuning reorder alerts for {site_name} / {material_name}.")
                ranked.append((stock / weekly_use, site, material, stock))
            low_pairs = { (site.id, material.id) for _, site, material, _ in sorted(ranked, key=lambda row: (row[0], row[1].identifier, row[2].name))[:8] }
            for _, site, material, stock in ranked:
                rule = session.scalar(select(ReorderRule).where(ReorderRule.site_id == site.id, ReorderRule.material_id == material.id))
                assert rule is not None
                rule.reorder_point_qty = stock + QTY_STEP if (site.id, material.id) in low_pairs else max(Decimal("0"), stock - QTY_STEP)
    with database.session() as session:
        return {
            "sample_customers": int(session.scalar(select(func.count(Customer.id)).where(Customer.source_tag == SAMPLE_TAG)) or 0),
            "sample_opening_counts": int(session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source_tag == SAMPLE_TAG, InventoryTransaction.transaction_type == "opening_balance")) or 0),
            "sample_receipts": int(session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source_tag == SAMPLE_TAG, InventoryTransaction.transaction_type == "receipt")) or 0),
            "sample_sale_transactions": int(session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source_tag == SAMPLE_TAG, InventoryTransaction.source == "sale")) or 0),
            "sample_sales": int(session.scalar(select(func.count(SalesRecord.id)).where(SalesRecord.source_tag == SAMPLE_TAG)) or 0),
            "sample_reorder_rules": int(session.scalar(select(func.count(ReorderRule.id)).where(ReorderRule.source_tag == SAMPLE_TAG)) or 0),
            "reconciled_pairs": pair_count,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, default=config.SOURCE_CSV)
    parser.add_argument("--extension-csv", type=Path, default=config.SAMPLE_EXTENSION_CSV)
    parser.add_argument("--database-url", default=config.DATABASE_URL)
    args = parser.parse_args(argv)
    if not args.extension_csv.exists():
        print(f"Sample extension not found: {args.extension_csv}; run scripts.extend_dataset first.", file=sys.stderr)
        return 2
    try:
        imported = import_extension(args.database_url, args.source_csv, args.extension_csv)
        print(f"Verified source rows: {imported}", flush=True)
        frame = read_csv_bytes(args.extension_csv.read_bytes())
        database = Database(args.database_url)
        try:
            initialize_database(database)
            result = load_sample_operations(database, frame)
        finally:
            database.dispose()
        print(f"Sample operations loaded/reconciled: {result}", flush=True)
        if result["sample_customers"] < 25 or result["sample_customers"] > 40:
            raise RuntimeError("Sample customer count is outside the requested 25–40 range.")
        if result["sample_reorder_rules"] != 60 or result["reconciled_pairs"] != 60:
            raise RuntimeError("Sample ledger/rules did not cover all 60 site/material pairs.")
    except Exception as exc:
        print(f"Operations loader failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
