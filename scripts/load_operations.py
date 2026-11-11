"""Load the committed ledger and its relational operating records into an empty database."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from sqlalchemy import func, select

from inventory_app import config
from inventory_app.database import Database
from inventory_app.models import (
    Customer, HistoricalObservation, ImportRun, InventoryTransaction, Material, ProjectSite, PurchaseOrder,
    PurchaseOrderLine, PlannerRun, ReceiptRecord, ReorderRule, SalesRecord, Supplier,
)

AS_OF_DATE = date.fromisoformat(config.AS_OF_DATE)
BASELINE_TAG = "baseline_ledger"


def ensure_ledger_baseline(database: Database, ledger_path: Path = config.SOURCE_CSV) -> dict[str, int] | None:
    """Load every ledger event once and create the related purchase/sales records."""
    with database.session() as session:
        existing = session.scalar(select(func.count(InventoryTransaction.id)).where(InventoryTransaction.source_tag == BASELINE_TAG)) or 0
        if existing:
            return None
    raw_ledger = ledger_path.read_bytes()
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as stream:
        events = list(csv.DictReader(stream))
    with database.session() as session, session.begin():
        import_run = ImportRun(file_name=ledger_path.name, file_hash=hashlib.sha256(raw_ledger).hexdigest(), source_kind="construction_materials_ledger", total_rows=len(events), accepted_rows=0, rejected_rows=0, duplicate_rows=0, status="complete", report_json="{}")
        session.add(import_run)
        session.flush()
        site_rows = {}
        for name in sorted({row["site"] for row in events}):
            site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == name))
            if site is None:
                site = ProjectSite(identifier=name, name=name.split(",")[0], city="Dehradun", state="Uttarakhand", project_type="Distributor branch")
                session.add(site)
            site_rows[name] = site
        material_rows = {}
        for name in sorted({row["material"] for row in events}):
            examples = [row for row in events if row["material"] == name]
            units = {row["unit"] for row in examples}
            if len(units) != 1:
                raise ValueError(f"Inconsistent units for {name}")
            material = session.scalar(select(Material).where(Material.name == name))
            if material is None:
                unit = units.pop()
                pack = Decimal("50") if "cement" in name.lower() else Decimal("500") if "tmt" in name.lower() else Decimal("5") if unit == "m3" else Decimal("25") if name == "Binding Wire" else Decimal("20") if unit == "litre" else Decimal("1")
                material = Material(name=name, unit=unit, benchmark_unit_price_inr=Decimal(examples[-1]["unit_price"]), price_basis="INR per unit, ex-GST", default_lead_time_days=14, safety_stock_days=14, minimum_order_qty=pack, order_multiple=pack)
                session.add(material)
            material_rows[name] = material
        customers = {}
        suppliers = {}
        for name in sorted({row["counterparty"] for row in events if row["event_type"] == "sale"}):
            customer = session.scalar(select(Customer).where(Customer.name == name))
            if customer is None:
                customer = Customer(name=name, notes="Business account", source_tag=BASELINE_TAG)
                session.add(customer)
            customers[name] = customer
        for name in sorted({row["counterparty"] for row in events if row["event_type"] == "purchase_receipt"}):
            supplier = session.scalar(select(Supplier).where(Supplier.name == name))
            if supplier is None:
                supplier = Supplier(name=name, city="Dehradun", notes="Regional trade supplier")
                session.add(supplier)
            suppliers[name] = supplier
        session.flush()

        po_events: dict[str, list[dict]] = defaultdict(list)
        for row in events:
            if row["event_type"] == "purchase_receipt":
                po_events[row["document_reference"].split("/")[0]].append(row)
        po_lines = {}
        receipt_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for po_number, rows in po_events.items():
            first = rows[0]
            supplier = suppliers[first["counterparty"]]
            site = site_rows[first["site"]]
            receipt_day = min(date.fromisoformat(row["date"]) for row in rows)
            order = PurchaseOrder(po_number=po_number, idempotency_key=f"baseline:{po_number}", supplier_id=supplier.id, site_id=site.id, status="Received", order_date=max(date(2024, 3, 1), receipt_day-timedelta(days=14)), expected_delivery_date=receipt_day, notes="Baseline purchasing record")
            session.add(order)
            session.flush()
            grouped = defaultdict(list)
            for row in rows:
                grouped[row["material"]].append(row)
            for material_name, line_rows in grouped.items():
                quantity = sum((Decimal(row["quantity"]) for row in line_rows), Decimal("0"))
                if po_number == "PO-0024" and material_name == next(iter(grouped)):
                    ordered = quantity * Decimal("1.05")
                    order.status = "Partially received"
                else:
                    ordered = quantity
                line = PurchaseOrderLine(purchase_order_id=order.id, material_id=material_rows[material_name].id, quantity_ordered=ordered, unit=material_rows[material_name].unit, unit_price_inr=Decimal(line_rows[0]["unit_cost"]))
                session.add(line)
                session.flush()
                po_lines[(po_number, material_name)] = line
                receipt_groups[(po_number, material_name)].extend(line_rows)

        # Four dated planning orders complete the 28-order register.
        for po_number, status, supplier_name, site_name in [
            ("PO-0025", "Pending approval", next(iter(suppliers)), "GMS Road, Dehradun"),
            ("PO-0026", "Approved", next(iter(suppliers)), "ISBT-Transport Nagar, Dehradun"),
            ("PO-0027", "Draft", next(iter(suppliers)), "Jakhan, Dehradun"),
            ("PO-0028", "Cancelled", next(iter(suppliers)), "Paltan Bazaar, Dehradun"),
        ]:
            order_date = date(2026, 6, 15) - timedelta(days=int(po_number[-2:]))
            session.add(PurchaseOrder(po_number=po_number, idempotency_key=f"baseline:{po_number}", supplier_id=suppliers[supplier_name].id, site_id=site_rows[site_name].id, status=status, order_date=order_date, expected_delivery_date=min(AS_OF_DATE, order_date+timedelta(days=7)), notes="Planning register"))
        session.flush()

        sale_rows = []
        receipt_rows = []
        for row in events:
            site = site_rows[row["site"]]
            material = material_rows[row["material"]]
            qty = Decimal(row["quantity"])
            unit_cost = Decimal(row["unit_cost"])
            tx_type = {"opening_balance": "opening_balance", "sale": "consumption", "purchase_receipt": "receipt", "adjustment": "adjustment"}[row["event_type"]]
            tx = InventoryTransaction(idempotency_key=f"baseline:{row['event_id']}", site_id=site.id, material_id=material.id, transaction_type=tx_type, quantity=qty, unit=material.unit, unit_cost_inr=unit_cost, transaction_date=date.fromisoformat(row["date"]), reference=row["document_reference"], source=BASELINE_TAG, source_tag=BASELINE_TAG, notes=row["event_type"])
            session.add(tx)
            session.flush()
            if row["event_type"] == "sale":
                customer = customers[row["counterparty"]]
                revenue = qty * Decimal(row["unit_price"])
                cogs = qty * unit_cost
                sale_rows.append(SalesRecord(idempotency_key=row["event_id"], site_id=site.id, material_id=material.id, customer_id=customer.id, inventory_transaction_id=tx.id, sale_date=date.fromisoformat(row["date"]), quantity=qty, unit=material.unit, unit_sale_price_inr=Decimal(row["unit_price"]), revenue_inr=revenue, unit_cost_basis_inr=unit_cost, cost_of_goods_sold_inr=cogs, gross_margin_inr=revenue-cogs, reference=row["document_reference"], source_tag=BASELINE_TAG))
            elif row["event_type"] == "purchase_receipt":
                receipt_rows.append((row, tx))
            elif row["event_type"] == "opening_balance":
                pass
        session.add_all(sale_rows)
        session.flush()
        for row, tx in receipt_rows:
            po_number = row["document_reference"].split("/")[0]
            line = po_lines[(po_number, row["material"])]
            line.quantity_received = Decimal(line.quantity_received or 0) + Decimal(row["quantity"])
            grn = row["document_reference"].split("/")[1]
            session.add(ReceiptRecord(idempotency_key=f"baseline:{row['event_id']}", receipt_reference=f"{grn}-{row['event_id']}", purchase_order_line_id=line.id, quantity=Decimal(row["quantity"]), unit=row["unit"], receipt_date=date.fromisoformat(row["date"]), inventory_transaction_id=tx.id, notes="Baseline goods receipt"))

        # Store ledger-derived weekly aggregates in the database for existing analysis routes.
        weekly_groups = defaultdict(lambda: {"sales": Decimal("0"), "receipts": Decimal("0"), "adjustments": Decimal("0"), "price_value": Decimal("0"), "price_qty": Decimal("0"), "unit_cost": Decimal("0")})
        for row in events:
            event_day = date.fromisoformat(row["date"])
            week_end = event_day + timedelta(days=6-event_day.weekday())
            agg = weekly_groups[(row["site"], row["material"], week_end)]
            quantity = Decimal(row["quantity"])
            if row["event_type"] == "sale":
                agg["sales"] += quantity
                agg["price_value"] += quantity * Decimal(row["unit_price"])
                agg["price_qty"] += quantity
                agg["unit_cost"] = Decimal(row["unit_cost"])
            elif row["event_type"] == "purchase_receipt":
                agg["receipts"] += quantity
            elif row["event_type"] == "adjustment":
                agg["adjustments"] += quantity
        weekly_count = 0
        first_week = date.fromisoformat(events[0]["date"]) + timedelta(days=6-date.fromisoformat(events[0]["date"]).weekday())
        last_day = date.fromisoformat(events[-1]["date"])
        last_week = last_day + timedelta(days=6-last_day.weekday())
        for site_name, site in site_rows.items():
            for material_name, material in material_rows.items():
                balance = Decimal("0")
                week = first_week
                while week <= last_week:
                    values = weekly_groups[(site_name, material_name, week)]
                    if week == first_week:
                        opening = sum((Decimal(row["quantity"]) for row in events if row["site"] == site_name and row["material"] == material_name and row["event_type"] == "opening_balance"), Decimal("0"))
                        balance = opening
                    else:
                        opening = balance
                    incoming = values["receipts"] + max(values["adjustments"], Decimal("0"))
                    consumption = values["sales"] + max(-values["adjustments"], Decimal("0"))
                    price = values["price_value"] / values["price_qty"] if values["price_qty"] else Decimal(material.benchmark_unit_price_inr or 0)
                    natural = f"{week.isoformat()}|{site_name}|{material_name}"
                    key = hashlib.sha256(natural.encode()).hexdigest()
                    session.add(HistoricalObservation(import_id=import_run.id, source_row_number=weekly_count+1, source_key=key, natural_key=key, observation_datetime=min(week, AS_OF_DATE), project_site_id=site_name, city="Dehradun", state="Uttarakhand", project_type="Distribution", project_phase="Operations", material=material_name, unit=material.unit, consumption_qty=consumption, opening_stock_qty=opening, incoming_qty=incoming, unit_price_inr=price, demand_level="Medium", price_level="Medium", supplier_lead_time_days=7, wpi_reference_month=week.strftime("%Y-%m"), raw_json=json.dumps({"week_ending":min(week, AS_OF_DATE).isoformat(),"site":site_name,"material":material_name})))
                    weekly_count += 1
                    balance += incoming - consumption
                    week += timedelta(days=7)
        import_run.accepted_rows = len(events)

        for site_name, site in site_rows.items():
            for material_name, material in material_rows.items():
                demand_total = sum((Decimal(row["quantity"]) for row in events if row["site"] == site_name and row["material"] == material_name and row["event_type"] == "sale"), Decimal("0"))
                daily_rate = demand_total / Decimal((AS_OF_DATE - date(2024, 4, 1)).days + 1)
                pack = Decimal(material.order_multiple or 1)
                session.add(ReorderRule(site_id=site.id, material_id=material.id, reorder_point_qty=daily_rate * Decimal("28"), lead_time_days=14, safety_stock_days=14, minimum_order_qty=pack, order_multiple=pack, source_tag=BASELINE_TAG, notes="Baseline reorder parameters"))
    return {"ledger_rows": len(events), "sales": len(sale_rows), "receipts": len(receipt_rows), "purchase_orders": len(po_events)+4, "sites": len(site_rows), "materials": len(material_rows)}


def ensure_baseline_planner_history(database: Database, ledger_path: Path = config.SOURCE_CSV) -> int:
    """Record one as-of-date planning review for every site/material pair."""
    with database.session() as session:
        if session.scalar(select(func.count(PlannerRun.id))) or not ledger_path.exists():
            return 0
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as stream:
        events = list(csv.DictReader(stream))
    totals = defaultdict(lambda: {"demand": Decimal("0"), "stock": Decimal("0")})
    for row in events:
        key = (row["site"], row["material"])
        qty = Decimal(row["quantity"])
        if row["event_type"] == "sale":
            totals[key]["demand"] += qty
            totals[key]["stock"] -= qty
        else:
            totals[key]["stock"] += qty
    days = Decimal((AS_OF_DATE - date(2024, 4, 1)).days + 1)
    created = 0
    with database.session() as session, session.begin():
        for (site_name, material_name), values in totals.items():
            site = session.scalar(select(ProjectSite).where(ProjectSite.identifier == site_name))
            material = session.scalar(select(Material).where(Material.name == material_name))
            if not site or not material:
                continue
            rule = session.scalar(select(ReorderRule).where(ReorderRule.site_id == site.id, ReorderRule.material_id == material.id))
            if not rule:
                continue
            stock = max(Decimal("0"), values["stock"])
            target = Decimal(rule.reorder_point_qty or 0)
            gap = max(Decimal("0"), target - stock)
            multiple = Decimal(rule.order_multiple or 1)
            recommended = (gap / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple if gap else Decimal("0")
            result = {
                "status": "Order review" if recommended else "No order",
                "site": site_name,
                "material": material_name,
                "unit": material.unit,
                "current_stock": float(stock),
                "lead_time_days": rule.lead_time_days,
                "safety_stock_days": rule.safety_stock_days,
                "historical_daily_rate": float(values["demand"] / days),
                "recommendation": {"recommended_order_qty": float(recommended), "unit": material.unit,
                                   "reorder_point_qty": float(target), "basis": "as-of ledger and configured reorder rule"},
            }
            session.add(PlannerRun(
                run_key=f"baseline:{AS_OF_DATE.isoformat()}:{site.id}:{material.id}",
                site_identifier=site_name, material_name=material_name,
                status=result["status"], result_json=json.dumps(result, sort_keys=True),
                created_at=datetime.combine(AS_OF_DATE, datetime.min.time()),
            ))
            created += 1
    return created
