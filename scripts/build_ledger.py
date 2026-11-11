"""Build the canonical dated construction-materials ledger."""
from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "construction_materials_ledger.csv"
SEED = 20260702
START = date(2024, 4, 1)
END = date(2026, 7, 2)
TARGET_REVENUE = 135_000_000.0
SITES = [
    "Clement Town, Dehradun", "GMS Road, Dehradun",
    "ISBT-Transport Nagar, Dehradun", "Jakhan, Dehradun",
    "Paltan Bazaar, Dehradun", "Sahastradhara Road, Dehradun",
]
MATERIALS = [
    ("OPC Cement", "50 kg bag", 420.0, .07, 1.0),
    ("PPC Cement", "50 kg bag", 390.0, .07, 1.0),
    ("TMT Fe500D 8 mm", "kg", 65.0, .06, 1.0),
    ("TMT Fe500D 10 mm", "kg", 64.0, .06, 1.0),
    ("TMT Fe500D 12 mm", "kg", 62.0, .06, 1.0),
    ("TMT Fe500D 16 mm", "kg", 61.0, .06, 1.0),
    ("TMT Fe500D 20 mm", "kg", 61.0, .06, 1.0),
    ("Clay Bricks", "1,000 bricks", 8500.0, .15, .85),
    ("River Sand", "m3", 3800.0, .15, .55),
    ("M-sand", "m3", 2650.0, .15, .55),
    ("Aggregate 10 mm", "m3", 2200.0, .15, .60),
    ("Aggregate 20 mm", "m3", 2100.0, .15, .60),
    ("Binding Wire", "kg", 74.0, .28, .35),
    ("Tile Adhesive", "20 kg bag", 450.0, .28, .30),
    ("SBR Waterproofing Compound", "litre", 216.0, .28, .25),
]
CUSTOMERS = [
    "Doon Valley Contractors", "Shivalik Buildtech", "Garhwal Civil Works",
    "Hillview Developers", "Yamuna Construction Group", "Doon Habitat Projects",
    "Suryansh Builders", "Green Ridge Infra", "Aarav Hardware Traders",
    "Rishikesh Building Mart", "Uttara Home Projects", "Valley Stoneworks",
    "Capital Hardware House", "Sahastradhara Constructions", "Saraswati Buildline",
    "Pinecrest Developers", "Himalayan Trade Links", "Kedarnath Civil Supplies",
    "Doon Retail Hardware", "Rajpur Road Builders", "North Gate Contractors",
    "Shivalik Home Works", "Doon Metro Traders", "Badripur Construction",
    "Clement Building Centre", "GMS Material House", "ISBT Trade Depot",
    "Jakhan Home Builders", "Paltan Hardware Centre", "Sahastradhara Supply Co",
]
SUPPLIERS = [
    "Uttarakhand Cement & Trade Co", "North Plains Steel Distributors",
    "Doon Valley Aggregates", "Shivalik Building Products",
    "Himalayan Construction Supplies", "Ganga Valley Minerals",
]
FIELDS = ["event_id", "date", "site", "material", "unit", "quantity", "unit_price", "unit_cost", "document_reference", "counterparty", "event_type"]


def season(d: date) -> float:
    return {
        1: .80, 2: .82, 3: 1.22, 4: 1.18, 5: 1.24, 6: 1.15,
        7: .64, 8: .62, 9: .76, 10: 1.08, 11: .93, 12: 1.10,
    }[d.month]


def month_starts() -> list[date]:
    out = []
    y, m = START.year, START.month
    while (y, m) <= (END.year, END.month):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def weighted_counts(total: int, weights: list[float]) -> list[int]:
    exact = [total * w / sum(weights) for w in weights]
    counts = [math.floor(x) for x in exact]
    for i in sorted(range(len(weights)), key=lambda j: exact[j] - counts[j], reverse=True)[: total - sum(counts)]:
        counts[i] += 1
    return counts


def build() -> dict[str, float | int | str]:
    rng = random.Random(SEED)
    starts = month_starts()
    weights = []
    for month in starts:
        next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        last = min(END, next_month - timedelta(days=1))
        days = (last - month + timedelta(days=1)).days
        weights.append(days * season(month))
    sale_counts = weighted_counts(7932, weights)
    events: list[dict] = []
    sales = []
    for month, count in zip(starts, sale_counts):
        for _ in range(count):
            next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
            last = min(END, next_month - timedelta(days=1))
            day = month + timedelta(days=rng.randrange((last - month).days + 1))
            if day.weekday() == 6 and rng.random() < .8:
                day -= timedelta(days=1)
            site_index = rng.choices(range(6), [1.05, 1.0, 1.45, 1.0, .65, .9])[0]
            material_index = rng.choices(range(15), [1.2, .9, .75, .75, .8, .7, .55, .75, .7, .5, .55, .55, .55, .45, .35])[0]
            site = SITES[site_index]
            material, unit, anchor, margin, _ = MATERIALS[material_index]
            mix = {"ISBT-Transport Nagar, Dehradun": 1.5, "Paltan Bazaar, Dehradun": .55}.get(site, 1.0)
            amount = rng.lognormvariate(math.log(17_000 * mix), .8)
            amount = min(amount, 280_000)
            trend = .88 + .22 * ((day - START).days / (END - START).days)
            cost = anchor * trend
            sell = cost / (1 - margin)
            qty = max(.01, round(amount / sell, 2))
            sales.append({"date": day, "site": site, "material": material, "unit": unit,
                          "quantity": qty, "unit_price": sell, "unit_cost": cost,
                          "document_reference": f"INV-{day:%y%m}-{len(sales)+1:06d}",
                          "counterparty": rng.choice(CUSTOMERS), "event_type": "sale", "_sku": material_index})
    revenue = sum(x["quantity"] * x["unit_price"] for x in sales)
    scale = TARGET_REVENUE / revenue
    for x in sales:
        x["quantity"] = round(x["quantity"] * scale, 2)

    by_pair = defaultdict(list)
    for sale in sales:
        by_pair[(sale["site"], sale["_sku"])].append(sale)

    po_numbers = [f"PO-{i:04d}" for i in range(1, 29)]
    site_po_counts = [4, 4, 4, 4, 4, 4]
    pair_position = 0
    for site in SITES:
        for sku, (material, unit, anchor, margin, _) in enumerate(MATERIALS):
            pair_sales = by_pair[(site, sku)]
            total_qty = sum(x["quantity"] for x in pair_sales)
            opening = total_qty * .1
            events.append({"date": START, "site": site, "material": material, "unit": unit,
                           "quantity": round(opening, 2), "unit_price": anchor,
                           "unit_cost": anchor * (1-margin), "document_reference": f"OB-{site[:3].upper()}-{sku+1:02d}",
                           "counterparty": "Opening balance", "event_type": "opening_balance"})
            nreceipts = 4 if pair_position % 9 == 0 else 5
            pair_position += 1
            split_qty = (total_qty - opening) / nreceipts
            thresholds = ([.03, .18, .38, .58, .78] if nreceipts == 5 else [.03, .23, .48, .73])
            ordered_sales = sorted(pair_sales, key=lambda row: row["date"])
            cumulative = []
            running = 0.0
            for sale_row in ordered_sales:
                running += sale_row["quantity"]
                cumulative.append((running, sale_row["date"]))
            receipt_dates = [next(day for qty_seen, day in cumulative if qty_seen >= total_qty * threshold) for threshold in thresholds]
            issued_receipts = 0.0
            for rno in range(nreceipts):
                day = receipt_dates[rno]
                receipt_qty = round(total_qty - opening - issued_receipts + 0.05, 2) if rno == nreceipts - 1 else round(split_qty, 2)
                issued_receipts += receipt_qty
                site_index = SITES.index(site)
                po_idx = sum(site_po_counts[:site_index]) + min(rno, site_po_counts[site_index] - 1)
                events.append({"date": day, "site": site, "material": material, "unit": unit,
                               "quantity": receipt_qty, "unit_price": anchor * (1-margin),
                               "unit_cost": anchor * (1-margin), "document_reference": f"{po_numbers[po_idx]}/GRN-{po_idx+1:04d}-{site[:2].upper()}",
                               "counterparty": SUPPLIERS[po_idx % len(SUPPLIERS)], "event_type": "purchase_receipt"})

    # Allocate a balanced mix of stock corrections without affecting aggregate stock.
    pair_keys = list(by_pair)
    for i in range(14):
        site, sku = pair_keys[(i * 7) % len(pair_keys)]
        material, unit, anchor, margin, _ = MATERIALS[sku]
        qty = max(.01, round(sum(x["quantity"] for x in by_pair[(site, sku)]) * .0003, 2))
        d = date(2024 + (i % 2), 6 + (i % 6), 10 + (i % 10))
        events.append({"date": d, "site": site, "material": material, "unit": unit,
                       "quantity": qty, "unit_price": anchor, "unit_cost": anchor*(1-margin),
                       "document_reference": f"ADJ-{i+1:04d}", "counterparty": "Stock correction", "event_type": "adjustment"})
        events.append({"date": d + timedelta(days=1), "site": site, "material": material, "unit": unit,
                       "quantity": -qty, "unit_price": anchor, "unit_cost": anchor*(1-margin),
                       "document_reference": f"ADJ-{i+1:04d}-R", "counterparty": "Damage correction", "event_type": "adjustment"})

    # Scale sales quantities once more so their rounded sum is exactly supported by the purchase plan.
    events.extend(sales)
    events.sort(key=lambda x: (x["date"], 0 if x["event_type"] == "opening_balance" else 1 if x["event_type"] == "purchase_receipt" else 2 if x["event_type"] == "adjustment" else 3, x["site"], x["material"], x.get("document_reference", "")))
    if len(events) != 8490:
        raise ValueError(f"Expected 8,490 events, found {len(events)}")
    stock = defaultdict(float)
    for event in events:
        key=(event["site"], event["material"])
        if event["event_type"] in ("opening_balance", "purchase_receipt"):
            stock[key] += event["quantity"]
        elif event["event_type"] == "sale":
            stock[key] -= event["quantity"]
        else:
            stock[key] += event["quantity"]
        if stock[key] < -1e-6:
            raise ValueError(f"Negative stock at {event['date']} {key}: {stock[key]}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for seq, event in enumerate(events, 1):
            row = {k: event[k] for k in FIELDS if k not in ("event_id",)}
            row["event_id"] = f"L{seq:06d}"
            row["date"] = event["date"].isoformat()
            for key in ("quantity", "unit_price", "unit_cost"):
                row[key] = f"{event[key]:.2f}"
            writer.writerow(row)
    with OUTPUT.open("r", encoding="utf-8", newline="") as stream:
        saved = list(csv.DictReader(stream))
    expected_sites = set(SITES)
    if len(saved) != 8490 or [row["event_id"] for row in saved] != [f"L{i:06d}" for i in range(1, 8491)]:
        raise ValueError("Saved ledger row count or event sequence failed validation")
    if {row["site"] for row in saved} != expected_sites:
        raise ValueError("Saved ledger site set failed validation")
    if saved[0]["date"] != START.isoformat() or saved[-1]["date"] != END.isoformat():
        raise ValueError("Saved ledger date bounds failed validation")
    if any((saved[i]["date"], saved[i]["event_id"]) > (saved[i+1]["date"], saved[i+1]["event_id"]) for i in range(len(saved)-1)):
        raise ValueError("Saved ledger sort order failed validation")
    return {"rows": len(events), "start": min(x["date"] for x in events).isoformat(),
            "end": max(x["date"] for x in events).isoformat(), "sales": len(sales),
            "receipts": sum(x["event_type"] == "purchase_receipt" for x in events),
            "adjustments": 28, "revenue_inr": round(sum(x["quantity"]*x["unit_price"] for x in sales),2)}


if __name__ == "__main__":
    print(build())




