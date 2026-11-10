"""Create and import a deterministic, explicitly tagged weekly sample extension.

The primary CSV is read-only. Generated records are written to a separate CSV and
persisted with source_tag='sample_extension'. Run from the repository root:

    python -m scripts.extend_dataset
"""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import func, select

from inventory_app import config
from inventory_app.database import Database, initialize_database
from inventory_app.ingestion import EXPECTED_COLUMNS, ensure_primary_dataset_import, import_dataframe, read_csv_bytes, validate_frame
from inventory_app.models import HistoricalObservation

BASE_CUTOFF = date(2025, 12, 29)
SAMPLE_TAG = "sample_extension"
EXTENSION_COLUMNS = [*EXPECTED_COLUMNS, "source_tag"]
QTY_STEP = Decimal("0.0001")


def current_week_monday(as_of: date | None = None) -> date:
    day = as_of or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    return day - timedelta(days=day.weekday())


def _q(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(QTY_STEP, rounding=ROUND_HALF_UP)


def _phase_for_week(first_date: date, observed_date: date) -> str:
    phases = ("Foundation", "Structure", "Finishing", "MEP")
    elapsed_weeks = (observed_date - first_date).days // 7
    return phases[(elapsed_weeks // 26) % len(phases)]


def generate_extension_frame(source: pd.DataFrame, *, as_of: date | None = None) -> pd.DataFrame:
    """Generate stable weekly rows from the fixed source through the current Monday.

    Consumption follows a bounded, deterministic trend/seasonal/noise recipe. Incoming
    quantities replenish when projected stock falls below lead-time cover. Unit-price
    drift stays within +/-15% of each pair's last-13-observation median.
    """
    missing = [name for name in EXPECTED_COLUMNS if name not in source.columns]
    if missing:
        raise ValueError(f"Primary CSV is missing required columns: {missing}")
    source_frame = source.loc[:, list(EXPECTED_COLUMNS)].copy()
    source_frame["date"] = pd.to_datetime(source_frame["date"], errors="raise")
    if source_frame.empty:
        raise ValueError("Primary CSV is empty.")
    valid, rejected, summary = validate_frame(source_frame)
    if summary.get("schema_errors") or rejected or len(valid) != len(source_frame):
        raise ValueError("Primary CSV failed source-schema or row validation.")
    if source_frame[["project_site_id", "material", "date"]].duplicated().any():
        raise ValueError("Primary CSV contains duplicate site/material/date observations.")
    source_end = source_frame["date"].max().date()
    if source_end != BASE_CUTOFF:
        raise ValueError(f"Expected primary source cutoff {BASE_CUTOFF}, found {source_end}; refusing to relabel a changed source.")
    pair_columns = ["project_site_id", "material"]
    last_dates = source_frame.groupby(pair_columns)["date"].max().dt.date
    if last_dates.nunique() != 1 or last_dates.iloc[0] != BASE_CUTOFF:
        raise ValueError("All 60 source series must end on 2025-12-29 before extension.")
    if len(last_dates) != 60:
        raise ValueError(f"Expected 60 site/material series, found {len(last_dates)}.")

    end_monday = current_week_monday(as_of)
    if end_monday <= BASE_CUTOFF:
        return pd.DataFrame(columns=EXTENSION_COLUMNS)
    week_count = (end_monday - BASE_CUTOFF).days // 7
    if BASE_CUTOFF + timedelta(days=7 * week_count) != end_monday:
        raise ValueError("The extension endpoint must align to a weekly observation date.")

    future_rows: list[dict[str, object]] = []
    grouped = source_frame.sort_values("date").groupby(pair_columns, sort=False, dropna=False)
    for pair_index, ((site, material), raw_group) in enumerate(grouped):
        group = raw_group.sort_values("date").reset_index(drop=True)
        dates = group["date"].dt.date.tolist()
        intervals = [(right - left).days for left, right in zip(dates, dates[1:])]
        if any(days != 7 for days in intervals):
            raise ValueError(f"Source series {site} / {material} is not continuous weekly data.")
        last = group.iloc[-1]
        last13 = group.tail(13)
        last26 = group.tail(26)
        anchor_price = float(last13["unit_price_inr"].median())
        if not math.isfinite(anchor_price) or anchor_price <= 0:
            raise ValueError(f"Invalid last-quarter price anchor for {site} / {material}.")
        baseline = float(last13["consumption_qty"].median())
        if not math.isfinite(baseline) or baseline <= 0:
            raise ValueError(f"Invalid demand anchor for {site} / {material}.")

        consumption_values = pd.to_numeric(group["consumption_qty"], errors="raise").astype(float)
        global_median = max(float(consumption_values.median()), 0.0001)
        month_medians = group.assign(_month=group["date"].dt.month).groupby("_month")["consumption_qty"].median()
        seasonal = {
            int(month): min(1.25, max(0.75, float(value) / global_median))
            for month, value in month_medians.items()
        }
        if len(last26) >= 2:
            raw_qty_slope = float(np.polyfit(np.arange(len(last26)), last26["consumption_qty"].astype(float), 1)[0])
        else:
            raw_qty_slope = 0.0
        qty_trend = min(0.0015, max(-0.0015, raw_qty_slope / baseline))
        price_values = last13["unit_price_inr"].astype(float).to_numpy()
        raw_price_slope = float(np.polyfit(np.arange(len(price_values)), price_values, 1)[0]) if len(price_values) > 1 else 0.0
        price_trend = min(0.001, max(-0.001, raw_price_slope / anchor_price))
        lead_days = max(1, int(round(float(last13["supplier_lead_time_days"].median()))))
        lead_weeks = max(1, math.ceil(lead_days / 7))
        reorder_level = Decimal(str(baseline * (lead_weeks + 1)))
        order_up_to = Decimal(str(baseline * (lead_weeks + 4)))
        first_date = dates[0]

        close = _q(
            Decimal(str(last["opening_stock_qty"]))
            + Decimal(str(last["incoming_qty"]))
            - Decimal(str(last["consumption_qty"]))
        )
        if close < 0:
            raise ValueError(f"Primary source has negative estimated closing stock for {site} / {material}.")
        stock = close
        digest = hashlib.sha256(f"{site}\0{material}\0sitestock-sample-extension-v1".encode("utf-8")).digest()
        rng = random.Random(int.from_bytes(digest[:8], "big"))
        last_price = float(last["unit_price_inr"])

        for step in range(1, week_count + 1):
            row_date = BASE_CUTOFF + timedelta(days=7 * step)
            if row_date > end_monday:
                break
            month_factor = seasonal.get(row_date.month, 1.0)
            noise = rng.uniform(-0.04, 0.04)
            demand_value = baseline * (1.0 + qty_trend * step) * month_factor * (1.0 + noise)
            consumption = max(QTY_STEP, _q(max(0.0001, demand_value)))
            opening = stock
            before_receipt = opening - consumption
            incoming = Decimal("0.0000")
            if before_receipt < reorder_level:
                incoming = max(Decimal("0"), _q(order_up_to - before_receipt))
            # Seed every series with at least one sample receipt while keeping the
            # movement small; subsequent receipts follow the lead-time stock rule.
            if step == 1:
                incoming = max(incoming, _q(baseline * 0.5))
            incoming = _q(incoming)
            closing = _q(opening + incoming - consumption)
            if opening < 0 or incoming < 0 or consumption <= 0 or closing < 0:
                raise ValueError(f"Generated non-integral stock flow for {site} / {material} on {row_date}.")

            price_noise = rng.uniform(-0.0025, 0.0025)
            price_candidate = last_price * (1.0 + price_trend * step) * (1.0 + price_noise)
            lower_price = _q(Decimal(str(anchor_price)) * Decimal("0.85"))
            upper_price = _q(Decimal(str(anchor_price)) * Decimal("1.15"))
            price = min(upper_price, max(lower_price, _q(price_candidate)))
            if not lower_price <= price <= upper_price:
                raise ValueError(f"Generated price left the +/-15% anchor band for {site} / {material}.")

            future_rows.append({
                "date": f"{row_date.isoformat()} 12:00:00",
                "project_site_id": str(last["project_site_id"]),
                "city": str(last["city"]),
                "state": str(last["state"]),
                "project_type": str(last["project_type"]),
                "project_phase": _phase_for_week(first_date, row_date),
                "material": str(last["material"]),
                "unit": str(last["unit"]),
                "consumption_qty": float(consumption),
                "opening_stock_qty": float(opening),
                "incoming_qty": float(incoming),
                "unit_price_inr": float(price),
                "supplier_lead_time_days": lead_days,
                "wpi_reference_month": row_date.strftime("%Y-%m"),
                "source_tag": SAMPLE_TAG,
            })
            stock = closing
            last_price = float(price)

    result = pd.DataFrame.from_records(future_rows, columns=EXTENSION_COLUMNS)
    if len(result) != 60 * week_count:
        raise ValueError(f"Expected {60 * week_count} extension rows, generated {len(result)}.")
    if not result.empty:
        result = result.sort_values(["date", "project_site_id", "material"], kind="stable").reset_index(drop=True)
        if result["source_tag"].ne(SAMPLE_TAG).any():
            raise ValueError("Every generated row must be tagged sample_extension.")
        result["date"] = pd.to_datetime(result["date"], errors="raise")
        for (site, material), series in result.groupby(pair_columns, sort=False):
            series = series.sort_values("date")
            if not series["date"].diff().dropna().dt.days.eq(7).all():
                raise ValueError(f"Generated series is not weekly for {site} / {material}.")
            close_values = series["opening_stock_qty"] + series["incoming_qty"] - series["consumption_qty"]
            if (close_values < 0).any() or (series[["opening_stock_qty", "incoming_qty", "consumption_qty"]] < 0).any().any():
                raise ValueError(f"Generated series contains negative stock/quantity for {site} / {material}.")
    return result.loc[:, EXTENSION_COLUMNS]


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, float_format="%.4f", lineterminator="\n").encode("utf-8")


def write_extension_csv(source: pd.DataFrame, destination: Path, *, as_of: date | None = None) -> tuple[pd.DataFrame, bool]:
    """Write a deterministic extension, accepting only an identical existing prefix."""
    generated = generate_extension_frame(source, as_of=as_of)
    raw = _csv_bytes(generated)
    changed = True
    if destination.exists():
        existing_raw = destination.read_bytes()
        if existing_raw == raw:
            changed = False
        else:
            existing = read_csv_bytes(existing_raw)
            if list(existing.columns) != EXTENSION_COLUMNS or existing.empty:
                raise ValueError(f"Existing extension file has an unexpected schema or no rows: {destination}")
            if existing["source_tag"].astype(str).ne(SAMPLE_TAG).any():
                raise ValueError("Existing extension file contains rows without the required sample_extension tag.")
            existing_end = pd.to_datetime(existing["date"], errors="raise").max().date()
            requested_end = current_week_monday(as_of)
            if existing_end > requested_end:
                raise ValueError("Existing extension extends beyond the requested current week; refusing to shorten it.")
            prefix = generate_extension_frame(source, as_of=existing_end)
            if _csv_bytes(prefix) != existing_raw:
                raise ValueError("Existing extension does not match the deterministic generated prefix; refusing to overwrite it.")
    if changed:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_bytes(raw)
        temporary.replace(destination)
    return generated, changed


def import_extension(database_url: str, source_path: Path, extension_path: Path) -> dict[str, object]:
    database = Database(database_url)
    try:
        initialize_database(database)
        ensure_primary_dataset_import(database, str(source_path))
        raw = extension_path.read_bytes()
        frame = read_csv_bytes(raw)
        result = import_dataframe(
            database,
            frame,
            file_name=extension_path.name,
            file_bytes=raw,
            source_kind=SAMPLE_TAG,
            source_tag=SAMPLE_TAG,
        )
        if not result.duplicate_file and result.rejected_rows != result.duplicate_rows:
            raise RuntimeError(
                f"Sample extension import has {result.rejected_rows - result.duplicate_rows} non-duplicate rejection(s); refusing to continue."
            )
        with database.session() as session:
            persisted = session.scalar(
                select(func.count(HistoricalObservation.id)).where(HistoricalObservation.source_tag == SAMPLE_TAG)
            )
        if persisted != len(frame):
            raise RuntimeError(f"Expected {len(frame)} tagged sample observations in the DB; found {persisted}.")
        return {
            "run_id": result.run_id,
            "accepted_rows": result.accepted_rows,
            "rejected_rows": result.rejected_rows,
            "duplicate_rows": result.duplicate_rows,
            "duplicate_file": result.duplicate_file,
            "sample_extension_rows": persisted,
        }
    finally:
        database.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, default=config.SOURCE_CSV)
    parser.add_argument("--output-csv", type=Path, default=config.SAMPLE_EXTENSION_CSV)
    parser.add_argument("--database-url", default=config.DATABASE_URL)
    parser.add_argument("--as-of-date", type=date.fromisoformat, help="Optional reproducibility date; output ends on that week's Monday.")
    parser.add_argument("--skip-database", action="store_true", help="Write the extension CSV without importing it.")
    args = parser.parse_args(argv)
    if not args.source_csv.exists():
        print(f"Primary CSV not found: {args.source_csv}", file=sys.stderr)
        return 2
    original_bytes = args.source_csv.read_bytes()
    source = read_csv_bytes(original_bytes)
    try:
        extension, changed = write_extension_csv(source, args.output_csv, as_of=args.as_of_date)
        print(
            f"Extension CSV {'updated' if changed else 'already current'}: {len(extension)} rows, "
            f"{extension['date'].min().date() if len(extension) else 'no rows'} through "
            f"{extension['date'].max().date() if len(extension) else 'no rows'}; tag={SAMPLE_TAG}.",
            flush=True,
        )
        if not args.skip_database and len(extension):
            result = import_extension(args.database_url, args.source_csv, args.output_csv)
            print(f"Database import: {result}", flush=True)
        elif not args.skip_database:
            print("No extension rows are due yet; no sample rows were imported.", flush=True)
    except Exception as exc:
        print(f"Dataset extension failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.source_csv.read_bytes() != original_bytes:
        raise RuntimeError("Original CSV changed during extension; this should never happen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
