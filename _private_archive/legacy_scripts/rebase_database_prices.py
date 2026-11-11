"""Apply canonical price and level columns to matching historical DB rows."""
from __future__ import annotations

import json
from decimal import Decimal

import pandas as pd
from sqlalchemy import select

from inventory_app import config
from inventory_app.database import Database, initialize_database
from inventory_app.ingestion import ensure_primary_dataset_import, validate_frame
from inventory_app.models import HistoricalObservation, Material


def main() -> int:
    raw = config.SOURCE_CSV.read_bytes()
    frame = pd.read_csv(config.SOURCE_CSV, encoding="utf-8-sig")
    valid, rejected, summary = validate_frame(frame)
    if rejected or summary.get("schema_errors") or len(valid) != len(frame):
        raise RuntimeError("Canonical dataset did not pass import validation; database was not changed.")

    db = Database(config.DATABASE_URL)
    initialize_database(db)
    try:
        with db.session() as session:
            records = session.scalars(select(HistoricalObservation)).all()
            by_key = {record.natural_key: record for record in records}
            incoming_keys = {row["_natural_key"] for row in valid}
            if incoming_keys != set(by_key):
                raise RuntimeError(
                    f"Database/dataset key mismatch: csv={len(incoming_keys)}, database={len(by_key)}; no prices changed."
                )

            for item in valid:
                record = by_key[item["_natural_key"]]
                comparisons = (
                    (Decimal(record.consumption_qty), item["consumption_qty"], "consumption_qty"),
                    (Decimal(record.opening_stock_qty), item["opening_stock_qty"], "opening_stock_qty"),
                    (Decimal(record.incoming_qty), item["incoming_qty"], "incoming_qty"),
                )
                for stored, canonical, field in comparisons:
                    if stored != Decimal(canonical):
                        raise RuntimeError(f"{field} differs for {record.project_site_id} / {record.material}; no prices changed.")
                if record.unit != item["unit"] or record.supplier_lead_time_days != item["supplier_lead_time_days"]:
                    raise RuntimeError(f"Unit or lead time differs for {record.project_site_id} / {record.material}; no prices changed.")

            for item in valid:
                record = by_key[item["_natural_key"]]
                record.unit_price_inr = item["unit_price_inr"]
                record.demand_level = item["demand_level"]
                record.price_level = item["price_level"]
                raw_row = json.loads(record.raw_json or "{}")
                raw_row["unit_price_inr"] = str(item["unit_price_inr"])
                raw_row["demand_level"] = item["demand_level"]
                raw_row["price_level"] = item["price_level"]
                record.raw_json = json.dumps(raw_row, ensure_ascii=False, default=str)
            median_prices = frame.groupby("material")["unit_price_inr"].median().to_dict()
            for material in session.scalars(select(Material)).all():
                if material.price_basis == "historical dataset median (estimate)" and material.name in median_prices:
                    material.benchmark_unit_price_inr = Decimal(str(median_prices[material.name])).quantize(Decimal("0.0001"))
            session.commit()

        imported = ensure_primary_dataset_import(db, str(config.SOURCE_CSV))
        print(
            f"DB price rebase complete: rows={len(valid)}, updated={len(valid)}, "
            "derived catalogue medians refreshed, "
            f"canonical_import_run={imported.run_id if imported else 'not recorded'}"
        )
    finally:
        db.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
