"""Complete generator and forensics verification script."""
from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

START = date(2024, 4, 1)
END = date(2026, 7, 2)
SEED = 20260702
TARGET_REVENUE = 135_000_000.0

SITES = [
    "Clement Town, Dehradun",
    "GMS Road, Dehradun",
    "ISBT-Transport Nagar, Dehradun",
    "Jakhan, Dehradun",
    "Paltan Bazaar, Dehradun",
    "Sahastradhara Road, Dehradun",
]

# Material definition:
# (name, unit, anchor_cost, base_margin, turnover_tier, base_demand_weight)
MATERIALS = [
    ("OPC Cement", "50 kg bag", 390.0, 0.071, "fast", 1.25),
    ("PPC Cement", "50 kg bag", 362.0, 0.072, "fast", 1.05),
    ("TMT Fe500D 8 mm", "kg", 60.5, 0.063, "fast", 0.95),
    ("TMT Fe500D 10 mm", "kg", 59.8, 0.065, "fast", 0.95),
    ("TMT Fe500D 12 mm", "kg", 58.0, 0.064, "fast", 1.00),
    ("TMT Fe500D 16 mm", "kg", 57.0, 0.065, "fast", 0.85),
    ("TMT Fe500D 20 mm", "kg", 57.0, 0.065, "medium", 0.70),
    ("Clay Bricks", "1,000 bricks", 7300.0, 0.141, "medium", 0.85),
    ("River Sand", "m3", 3250.0, 0.145, "fast", 0.75),
    ("M-sand", "m3", 2280.0, 0.140, "medium", 0.60),
    ("Aggregate 10 mm", "m3", 1880.0, 0.145, "medium", 0.65),
    ("Aggregate 20 mm", "m3", 1800.0, 0.143, "medium", 0.65),
    ("Binding Wire", "kg", 54.0, 0.270, "slow", 0.50),
    ("Tile Adhesive", "20 kg bag", 328.0, 0.271, "slow", 0.45),
    ("SBR Waterproofing Compound", "litre", 158.0, 0.268, "slow", 0.35),
]
MATERIAL_DICT = {m[0]: m for m in MATERIALS}

CUSTOMERS = [
    "Doon Valley Contractors", "Shivalik Buildtech", "Garhwal Civil Works",
    "Hillview Developers", "Yamuna Construction Group", "Doon Habitat Projects",
    "Suryansh Builders", "Green Ridge Infra", "Aarav Hardware Traders",
    "Rishikesh Building Mart", "Uttara Home Projects", "Valley Stoneworks",
    "Capital Hardware House", "Sahastradhara Constructions", "Saraswati Buildline",
    "Pinecrest Developers", "Himalayan Trade Links", "Kedarnath Civil Supplies",
    "Doon Ridge Hardware", "Rajpur Road Builders", "North Gate Contractors",
    "Shivalik Home Works", "Doon Metro Traders", "Badripur Construction",
    "Clement Building Centre", "GMS Material House", "ISBT Trade Depot",
    "Jakhan Home Builders", "Paltan Hardware Centre", "Sahastradhara Supply Co",
]

# Customer frequency weights to concentrate top-10 revenue to ~50%
CUSTOMER_WEIGHTS = [1.60, 1.55, 1.50, 1.45, 1.40, 1.35, 1.30, 1.25, 1.20, 1.15] + [
    0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65,
    0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65
]

# Customer discount tiers (repeat accounts get higher discounts)
CUSTOMER_TIERS = {
    c: (0.015 if i < 3 else 0.010 if i < 10 else 0.003 if i < 20 else 0.0)
    for i, c in enumerate(CUSTOMERS)
}

# Site personalities: material preference multipliers
SITE_MATERIAL_WEIGHTS = {
    # ISBT: heavy trade & commercial bulk (steel, bulk cement, sand/aggregates)
    "ISBT-Transport Nagar, Dehradun": {
        "OPC Cement": 1.4, "PPC Cement": 1.3,
        "TMT Fe500D 8 mm": 1.5, "TMT Fe500D 10 mm": 1.5, "TMT Fe500D 12 mm": 1.5,
        "TMT Fe500D 16 mm": 1.6, "TMT Fe500D 20 mm": 1.7,
        "Clay Bricks": 0.9, "River Sand": 1.3, "M-sand": 1.2,
        "Aggregate 10 mm": 1.3, "Aggregate 20 mm": 1.3,
        "Binding Wire": 1.2, "Tile Adhesive": 0.5, "SBR Waterproofing Compound": 0.5,
    },
    # Paltan Bazaar: central urban retail & hardware (finishing, bags, wire, low heavy bulk)
    "Paltan Bazaar, Dehradun": {
        "OPC Cement": 0.6, "PPC Cement": 0.7,
        "TMT Fe500D 8 mm": 0.5, "TMT Fe500D 10 mm": 0.5, "TMT Fe500D 12 mm": 0.4,
        "TMT Fe500D 16 mm": 0.3, "TMT Fe500D 20 mm": 0.2,
        "Clay Bricks": 0.6, "River Sand": 0.4, "M-sand": 0.4,
        "Aggregate 10 mm": 0.4, "Aggregate 20 mm": 0.4,
        "Binding Wire": 1.6, "Tile Adhesive": 1.8, "SBR Waterproofing Compound": 1.7,
    },
    # Clement Town: residential construction
    "Clement Town, Dehradun": {
        "OPC Cement": 1.1, "PPC Cement": 1.2,
        "TMT Fe500D 8 mm": 1.1, "TMT Fe500D 10 mm": 1.1, "TMT Fe500D 12 mm": 1.1,
        "TMT Fe500D 16 mm": 0.9, "TMT Fe500D 20 mm": 0.8,
        "Clay Bricks": 1.3, "River Sand": 1.1, "M-sand": 1.0,
        "Aggregate 10 mm": 1.1, "Aggregate 20 mm": 1.1,
        "Binding Wire": 1.0, "Tile Adhesive": 1.1, "SBR Waterproofing Compound": 1.1,
    },
    # Jakhan: premium residential / hillside villas
    "Jakhan, Dehradun": {
        "OPC Cement": 1.1, "PPC Cement": 1.1,
        "TMT Fe500D 8 mm": 1.0, "TMT Fe500D 10 mm": 1.1, "TMT Fe500D 12 mm": 1.0,
        "TMT Fe500D 16 mm": 0.9, "TMT Fe500D 20 mm": 0.8,
        "Clay Bricks": 1.2, "River Sand": 1.0, "M-sand": 1.0,
        "Aggregate 10 mm": 1.0, "Aggregate 20 mm": 1.0,
        "Binding Wire": 0.9, "Tile Adhesive": 1.4, "SBR Waterproofing Compound": 1.4,
    },
    # GMS Road: mixed commercial & residential
    "GMS Road, Dehradun": {
        "OPC Cement": 1.0, "PPC Cement": 1.0,
        "TMT Fe500D 8 mm": 1.0, "TMT Fe500D 10 mm": 1.0, "TMT Fe500D 12 mm": 1.0,
        "TMT Fe500D 16 mm": 1.0, "TMT Fe500D 20 mm": 1.0,
        "Clay Bricks": 1.0, "River Sand": 1.0, "M-sand": 1.0,
        "Aggregate 10 mm": 1.0, "Aggregate 20 mm": 1.0,
        "Binding Wire": 1.0, "Tile Adhesive": 1.0, "SBR Waterproofing Compound": 1.0,
    },
    # Sahastradhara Road: mixed corridor
    "Sahastradhara Road, Dehradun": {
        "OPC Cement": 1.0, "PPC Cement": 1.0,
        "TMT Fe500D 8 mm": 1.0, "TMT Fe500D 10 mm": 1.0, "TMT Fe500D 12 mm": 1.0,
        "TMT Fe500D 16 mm": 1.0, "TMT Fe500D 20 mm": 0.9,
        "Clay Bricks": 1.1, "River Sand": 1.0, "M-sand": 1.1,
        "Aggregate 10 mm": 1.0, "Aggregate 20 mm": 1.0,
        "Binding Wire": 0.9, "Tile Adhesive": 1.0, "SBR Waterproofing Compound": 1.1,
    },
}

# 4 purchase orders per site = 24 POs for receipt lines (plus 4 open POs = 28 total)
SITE_PO_CONFIG = [
    # Clement Town (PO-0001 to PO-0004)
    [
        ("PO-0001", "Uttarakhand Cement & Trade Co", ["OPC Cement", "PPC Cement"]),
        ("PO-0002", "North Plains Steel Distributors", ["TMT Fe500D 8 mm", "TMT Fe500D 10 mm", "TMT Fe500D 12 mm", "TMT Fe500D 16 mm", "TMT Fe500D 20 mm", "Binding Wire"]),
        ("PO-0003", "Doon Valley Aggregates", ["River Sand", "M-sand", "Aggregate 10 mm", "Aggregate 20 mm"]),
        ("PO-0004", "Shivalik Building Products", ["Clay Bricks", "Tile Adhesive", "SBR Waterproofing Compound"]),
    ],
    # GMS Road (PO-0005 to PO-0008)
    [
        ("PO-0005", "Uttarakhand Cement & Trade Co", ["OPC Cement", "PPC Cement"]),
        ("PO-0006", "North Plains Steel Distributors", ["TMT Fe500D 8 mm", "TMT Fe500D 10 mm", "TMT Fe500D 12 mm", "TMT Fe500D 16 mm", "TMT Fe500D 20 mm", "Binding Wire"]),
        ("PO-0007", "Ganga Valley Minerals", ["River Sand", "M-sand", "Aggregate 10 mm", "Aggregate 20 mm"]),
        ("PO-0008", "Himalayan Construction Supplies", ["Clay Bricks", "Tile Adhesive", "SBR Waterproofing Compound"]),
    ],
    # ISBT-Transport Nagar (PO-0009 to PO-0012)
    [
        ("PO-0009", "Uttarakhand Cement & Trade Co", ["OPC Cement", "PPC Cement"]),
        ("PO-0010", "North Plains Steel Distributors", ["TMT Fe500D 8 mm", "TMT Fe500D 10 mm", "TMT Fe500D 12 mm", "TMT Fe500D 16 mm", "TMT Fe500D 20 mm", "Binding Wire"]),
        ("PO-0011", "Doon Valley Aggregates", ["River Sand", "M-sand", "Aggregate 10 mm", "Aggregate 20 mm"]),
        ("PO-0012", "Shivalik Building Products", ["Clay Bricks", "Tile Adhesive", "SBR Waterproofing Compound"]),
    ],
    # Jakhan (PO-0013 to PO-0016)
    [
        ("PO-0013", "Uttarakhand Cement & Trade Co", ["OPC Cement", "PPC Cement"]),
        ("PO-0014", "North Plains Steel Distributors", ["TMT Fe500D 8 mm", "TMT Fe500D 10 mm", "TMT Fe500D 12 mm", "TMT Fe500D 16 mm", "TMT Fe500D 20 mm", "Binding Wire"]),
        ("PO-0015", "Ganga Valley Minerals", ["River Sand", "M-sand", "Aggregate 10 mm", "Aggregate 20 mm"]),
        ("PO-0016", "Himalayan Construction Supplies", ["Clay Bricks", "Tile Adhesive", "SBR Waterproofing Compound"]),
    ],
    # Paltan Bazaar (PO-0017 to PO-0020)
    [
        ("PO-0017", "Uttarakhand Cement & Trade Co", ["OPC Cement", "PPC Cement"]),
        ("PO-0018", "North Plains Steel Distributors", ["TMT Fe500D 8 mm", "TMT Fe500D 10 mm", "TMT Fe500D 12 mm", "TMT Fe500D 16 mm", "TMT Fe500D 20 mm", "Binding Wire"]),
        ("PO-0019", "Doon Valley Aggregates", ["River Sand", "M-sand", "Aggregate 10 mm", "Aggregate 20 mm"]),
        ("PO-0020", "Shivalik Building Products", ["Clay Bricks", "Tile Adhesive", "SBR Waterproofing Compound"]),
    ],
    # Sahastradhara Road (PO-0021 to PO-0024)
    [
        ("PO-0021", "Uttarakhand Cement & Trade Co", ["OPC Cement", "PPC Cement"]),
        ("PO-0022", "North Plains Steel Distributors", ["TMT Fe500D 8 mm", "TMT Fe500D 10 mm", "TMT Fe500D 12 mm", "TMT Fe500D 16 mm", "TMT Fe500D 20 mm", "Binding Wire"]),
        ("PO-0023", "Ganga Valley Minerals", ["River Sand", "M-sand", "Aggregate 10 mm", "Aggregate 20 mm"]),
        ("PO-0024", "Himalayan Construction Supplies", ["Clay Bricks", "Tile Adhesive", "SBR Waterproofing Compound"]),
    ],
]

PO_MAP = {}
for s_idx, site in enumerate(SITES):
    for po_num, supp, mats in SITE_PO_CONFIG[s_idx]:
        for mat in mats:
            PO_MAP[(site, mat)] = (po_num, supp)

def season_factor(d: date) -> float:
    m = d.month
    # Monthly construction seasonal index in Dehradun:
    base = {
        1: 0.80, 2: 0.88, 3: 1.25, 4: 1.20, 5: 1.26, 6: 1.12,
        7: 0.58, 8: 0.55, 9: 0.76, 10: 1.08, 11: 0.90, 12: 1.06,
    }[m]
    # Monsoon 2025 excess rainfall effect
    if d.year == 2025 and m in (7, 8):
        base *= 0.85
    # Pre-monsoon 2026 infrastructure acceleration
    if d.year == 2026 and m in (3, 4, 5):
        base *= 1.06
    # Diwali festival days dip (late Oct / early Nov)
    if (d.month == 10 and d.day >= 28) or (d.month == 11 and d.day <= 3):
        base *= 0.55
    # Holi festival days dip (late March)
    if d.month == 3 and 23 <= d.day <= 26:
        base *= 0.60
    return base

def month_starts() -> list[date]:
    out = []
    y, m = START.year, START.month
    while (y, m) <= (END.year, END.month):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "construction_materials_ledger.csv"

def build() -> dict[str, float | int | str]:
    rng = random.Random(SEED)
    starts = month_starts()
    
    # Generate 7,932 sales events
    weights = []
    for month in starts:
        next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        last = min(END, next_month - timedelta(days=1))
        days = (last - month + timedelta(days=1)).days
        weights.append(days * season_factor(month))
    
    exact = [7932 * w / sum(weights) for w in weights]
    sale_counts = [math.floor(x) for x in exact]
    for i in sorted(range(len(weights)), key=lambda j: exact[j] - sale_counts[j], reverse=True)[: 7932 - sum(sale_counts)]:
        sale_counts[i] += 1
    
    sales = []
    for month, count in zip(starts, sale_counts):
        next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        last = min(END, next_month - timedelta(days=1))
        month_days = (last - month).days + 1
        
        for _ in range(count):
            day = month + timedelta(days=rng.randrange(month_days))
            # Sunday drop
            if day.weekday() == 6 and rng.random() < 0.82:
                day = max(START, day - timedelta(days=1))
            
            # Site distribution
            site_index = rng.choices(range(6), [1.1, 1.0, 1.5, 1.0, 0.65, 0.95])[0]
            site = SITES[site_index]
            
            # Material choice incorporating site personality
            mat_weights = [m[5] * SITE_MATERIAL_WEIGHTS[site][m[0]] for m in MATERIALS]
            mat_idx = rng.choices(range(15), mat_weights)[0]
            material, unit, anchor, target_margin, tier, _ = MATERIALS[mat_idx]
            
            # Customer choice (top 10 concentrated)
            cust_idx = rng.choices(range(len(CUSTOMERS)), CUSTOMER_WEIGHTS)[0]
            customer = CUSTOMERS[cust_idx]
            tier_discount = CUSTOMER_TIERS[customer]
            
            # Amount distribution by site personality
            site_amount_scale = {
                "ISBT-Transport Nagar, Dehradun": 1.75,
                "Paltan Bazaar, Dehradun": 0.45,
                "Clement Town, Dehradun": 1.05,
                "Jakhan, Dehradun": 1.00,
                "GMS Road, Dehradun": 1.00,
                "Sahastradhara Road, Dehradun": 1.00,
            }[site]
            
            amount = rng.lognormvariate(math.log(16_500 * site_amount_scale), 0.75)
            amount = max(1_200, min(amount, 320_000))
            
            # Baseline price & cost with time inflation
            t_frac = (day - START).days / (END - START).days
            cost_trend = 0.89 + 0.20 * t_frac
            
            # Steel margin squeeze in March 2025
            is_steel = "TMT" in material
            if is_steel and day.year == 2025 and day.month == 3:
                # Raw material spike compresses steel margin to 2.5% - 3.8%
                actual_margin = rng.uniform(0.025, 0.038) - tier_discount
            elif is_steel:
                actual_margin = target_margin + rng.uniform(-0.010, 0.012) - tier_discount
            elif "Cement" in material:
                actual_margin = target_margin + rng.uniform(-0.012, 0.015) - tier_discount
            elif tier == "slow":
                actual_margin = target_margin + rng.uniform(-0.025, 0.030) - tier_discount
            else: # sand, bricks, aggregate
                actual_margin = target_margin + rng.uniform(-0.020, 0.025) - tier_discount
            
            # Cost basis
            unit_cost = anchor * cost_trend * rng.uniform(0.985, 1.015)
            # Sell price based on actual realized margin
            sell_price = unit_cost / (1.0 - actual_margin)
            
            # Small random dealer bargaining variance (+/- 0.8%)
            sell_price *= rng.uniform(0.992, 1.008)
            
            qty = max(0.05, round(amount / sell_price, 2))
            
            sales.append({
                "date": day,
                "site": site,
                "material": material,
                "unit": unit,
                "quantity": qty,
                "unit_price": sell_price,
                "unit_cost": unit_cost,
                "document_reference": f"INV-{day:%y%m}-{len(sales)+1:06d}",
                "counterparty": customer,
                "event_type": "sale",
                "_sku": mat_idx,
                "_tier": tier,
            })
            
    # Revenue scaling to target
    current_rev = sum(s["quantity"] * s["unit_price"] for s in sales)
    scale = TARGET_REVENUE / current_rev
    for s in sales:
        s["quantity"] = max(0.01, round(s["quantity"] * scale, 2))
        s["unit_price"] = round(s["unit_price"], 2)
        s["unit_cost"] = round(s["unit_cost"], 2)
    
    events = []
    
    # Opening balances: 90 rows (6 sites * 15 materials)
    # Differentiate fast movers vs slow movers!
    by_pair = defaultdict(list)
    for s in sales:
        by_pair[(s["site"], s["material"])].append(s)
        
    for site in SITES:
        for sku_idx, (material, unit, anchor, margin, tier, _) in enumerate(MATERIALS):
            pair_sales = by_pair[(site, material)]
            total_qty = sum(x["quantity"] for x in pair_sales)
            
            # Differentiated opening fraction:
            # Fast movers turn 9-12x/yr -> opening stock is ~4.5% of total sales
            # Medium movers turn 6-8x/yr -> opening stock is ~7.5% of total sales
            # Slow movers turn 3-5x/yr -> opening stock is ~15% of total sales
            if tier == "fast":
                opening_frac = 0.045
            elif tier == "medium":
                opening_frac = 0.075
            else:
                opening_frac = 0.150
                
            opening_qty = round(total_qty * opening_frac, 2)
            events.append({
                "date": START,
                "site": site,
                "material": material,
                "unit": unit,
                "quantity": opening_qty,
                "unit_price": anchor,
                "unit_cost": round(anchor * (1.0 - margin), 2),
                "document_reference": f"OB-{site[:3].upper()}-{sku_idx+1:02d}",
                "counterparty": "Opening balance",
                "event_type": "opening_balance",
            })
            
    # Receipts: 440 rows
    pair_list = []
    for site in SITES:
        for m in MATERIALS:
            pair_list.append((site, m[0], m[4])) # site, material, tier
    for p_idx, (site, material, tier) in enumerate(pair_list):
        pair_sales = sorted(by_pair[(site, material)], key=lambda x: x["date"])
        total_qty = sum(x["quantity"] for x in pair_sales)
        material_row = MATERIAL_DICT[material]
        anchor = material_row[2]
        margin = material_row[3]
        
        # 10 pairs have 4 receipts, 80 pairs have 5 receipts -> 440 total receipts
        nreceipts = 4 if p_idx in [12, 13, 14, 27, 28, 29, 42, 43, 44, 57] else 5
        
        opening_row = next(e for e in events if e["event_type"] == "opening_balance" and e["site"] == site and e["material"] == material)
        opening_qty = opening_row["quantity"]
        
        # Fast movers turn faster (lower opening stock, ~4.5%), slow movers higher (~15%)
        if tier == "fast":
            thresholds = [0.03, 0.20, 0.40, 0.60, 0.80] if nreceipts == 5 else [0.03, 0.25, 0.50, 0.75]
        elif tier == "medium":
            thresholds = [0.04, 0.22, 0.44, 0.66, 0.84] if nreceipts == 5 else [0.04, 0.28, 0.54, 0.78]
        else: # slow
            thresholds = [0.05, 0.25, 0.48, 0.70, 0.88] if nreceipts == 5 else [0.05, 0.32, 0.60, 0.85]
        
        closing_frac = 0.02 if tier == "fast" else 0.05 if tier == "medium" else 0.10
        total_receipt_qty = total_qty * (1.0 + closing_frac) - opening_qty
        split_qty = round(total_receipt_qty / nreceipts, 2)
        
        cum_qty = 0.0
        cumulative = []
        for s in pair_sales:
            cum_qty += s["quantity"]
            cumulative.append((cum_qty, s["date"]))
            
        receipt_dates = [next(day for qty_seen, day in cumulative if qty_seen >= total_qty * th) for th in thresholds]
        
        po_number, supplier = PO_MAP[(site, material)]
        issued = 0.0
        
        for r_num in range(nreceipts):
            r_day = receipt_dates[r_num]
            if r_num == nreceipts - 1:
                r_qty = round(total_receipt_qty - issued + 0.10, 2)
            else:
                r_qty = split_qty
                issued += r_qty
                
            t_frac = (r_day - START).days / (END - START).days
            cost_val = round(anchor * (1.0 - margin) * (0.90 + 0.18 * t_frac), 2)
            
            events.append({
                "date": r_day,
                "site": site,
                "material": material,
                "unit": material_row[1],
                "quantity": r_qty,
                "unit_price": cost_val,
                "unit_cost": cost_val,
                "document_reference": f"{po_number}/GRN-{po_number[-4:]}-{site[:2].upper()}",
                "counterparty": supplier,
                "event_type": "purchase_receipt",
            })
            
    # Adjustments: exactly 28 rows, net non-zero, small in value
    # 18 negative adjustments (breakage, damage, bag tear, spillage)
    # 10 positive adjustments (physical inventory surplus, count adjustment)
    ADJ_SAMPLES = [
        # (site, material, qty, date, reason, counterparty)
        ("Clement Town, Dehradun", "OPC Cement", -2.0, date(2024, 6, 12), "Moisture damage write-off", "Damage correction"),
        ("GMS Road, Dehradun", "Tile Adhesive", -1.0, date(2024, 6, 25), "Bag puncture in transit", "Damage correction"),
        ("ISBT-Transport Nagar, Dehradun", "River Sand", 0.45, date(2024, 7, 10), "Physical yard count surplus", "Stock adjustment"),
        ("ISBT-Transport Nagar, Dehradun", "TMT Fe500D 10 mm", -15.5, date(2024, 7, 28), "Offcut trimming scrap write-off", "Damage correction"),
        ("Jakhan, Dehradun", "Clay Bricks", -0.15, date(2024, 8, 14), "Handling breakage at unloading", "Damage correction"),
        ("Paltan Bazaar, Dehradun", "Binding Wire", -1.5, date(2024, 8, 22), "Coil rust scrap", "Damage correction"),
        ("Sahastradhara Road, Dehradun", "Aggregate 10 mm", 0.35, date(2024, 9, 5), "Quarterly stock audit reconciliation", "Stock adjustment"),
        ("Clement Town, Dehradun", "SBR Waterproofing Compound", -1.0, date(2024, 9, 18), "Canister seal leak", "Damage correction"),
        ("GMS Road, Dehradun", "PPC Cement", -3.0, date(2024, 10, 15), "Forklift puncture write-off", "Damage correction"),
        ("ISBT-Transport Nagar, Dehradun", "M-sand", 0.60, date(2024, 11, 8), "Truck weighbridge tare reconciliation", "Stock adjustment"),
        ("Jakhan, Dehradun", "TMT Fe500D 12 mm", -12.0, date(2024, 11, 25), "Bar bending defect scrap", "Damage correction"),
        ("Paltan Bazaar, Dehradun", "Tile Adhesive", -2.0, date(2024, 12, 10), "Torn packaging write-off", "Damage correction"),
        ("Sahastradhara Road, Dehradun", "River Sand", -0.25, date(2024, 12, 28), "Rain erosion in open yard", "Damage correction"),
        ("Clement Town, Dehradun", "Clay Bricks", 0.10, date(2025, 1, 15), "Physical pallet count surplus", "Stock adjustment"),
        ("GMS Road, Dehradun", "Aggregate 20 mm", -0.40, date(2025, 2, 4), "Spillage cleanup write-off", "Damage correction"),
        ("ISBT-Transport Nagar, Dehradun", "OPC Cement", -4.0, date(2025, 2, 20), "Transit rain damage", "Damage correction"),
        ("Jakhan, Dehradun", "Binding Wire", 1.2, date(2025, 3, 12), "Physical bundle count surplus", "Stock adjustment"),
        ("Paltan Bazaar, Dehradun", "SBR Waterproofing Compound", -1.0, date(2025, 3, 29), "Container damage during stacking", "Damage correction"),
        ("Sahastradhara Road, Dehradun", "TMT Fe500D 8 mm", -14.0, date(2025, 4, 18), "Rust defect write-off", "Damage correction"),
        ("Clement Town, Dehradun", "M-sand", 0.50, date(2025, 5, 10), "Yard survey reconciliation", "Stock adjustment"),
        ("GMS Road, Dehradun", "TMT Fe500D 16 mm", -10.0, date(2025, 6, 2), "Offcut scrap write-off", "Damage correction"),
        ("ISBT-Transport Nagar, Dehradun", "Clay Bricks", -0.20, date(2025, 7, 14), "Pallet tipping breakage", "Damage correction"),
        ("Jakhan, Dehradun", "Aggregate 10 mm", 0.30, date(2025, 8, 20), "Audit count reconciliation", "Stock adjustment"),
        ("Paltan Bazaar, Dehradun", "PPC Cement", -2.0, date(2025, 9, 22), "Storage moisture hardening", "Damage correction"),
        ("Sahastradhara Road, Dehradun", "Tile Adhesive", 1.0, date(2025, 10, 18), "Unrecorded return reconciliation", "Stock adjustment"),
        ("Clement Town, Dehradun", "Binding Wire", -1.0, date(2025, 11, 12), "Spool tangle scrap", "Damage correction"),
        ("GMS Road, Dehradun", "River Sand", 0.40, date(2026, 1, 8), "Stock survey adjustment", "Stock adjustment"),
        ("ISBT-Transport Nagar, Dehradun", "SBR Waterproofing Compound", -1.0, date(2026, 2, 16), "Puncture leak write-off", "Damage correction"),
    ]
    
    assert len(ADJ_SAMPLES) == 28, f"Expected 28 adjustments, got {len(ADJ_SAMPLES)}"
    
    for i, (adj_site, adj_mat, adj_qty, adj_date, adj_notes, adj_cparty) in enumerate(ADJ_SAMPLES, 1):
        mat_info = MATERIAL_DICT[adj_mat]
        events.append({
            "date": adj_date,
            "site": adj_site,
            "material": adj_mat,
            "unit": mat_info[1],
            "quantity": adj_qty,
            "unit_price": mat_info[2],
            "unit_cost": round(mat_info[2] * (1.0 - mat_info[3]), 2),
            "document_reference": f"ADJ-{i:04d}",
            "counterparty": adj_cparty,
            "event_type": "adjustment",
        })
        
    events.extend(sales)
    
    # Sort order: (date, type_order, site, material, doc_ref)
    type_priority = {"opening_balance": 0, "purchase_receipt": 1, "adjustment": 2, "sale": 3}
    events.sort(key=lambda x: (x["date"], type_priority[x["event_type"]], x["site"], x["material"], x["document_reference"]))
    
    # Verify nonnegative running stock
    stock = defaultdict(float)
    for event in events:
        key = (event["site"], event["material"])
        if event["event_type"] in ("opening_balance", "purchase_receipt", "adjustment"):
            stock[key] += event["quantity"]
        elif event["event_type"] == "sale":
            stock[key] -= event["quantity"]
        if stock[key] < -1e-6:
            raise ValueError(f"Negative stock at {event['date']} {key}: {stock[key]}")
            
    FIELDS = ["event_id", "date", "site", "material", "unit", "quantity", "unit_price", "unit_cost", "document_reference", "counterparty", "event_type"]
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
        
    return {
        "rows": len(events),
        "start": min(x["date"] for x in events).isoformat(),
        "end": max(x["date"] for x in events).isoformat(),
        "sales": len(sales),
        "receipts": sum(x["event_type"] == "purchase_receipt" for x in events),
        "adjustments": 28,
        "revenue_inr": round(sum(x["quantity"] * x["unit_price"] for x in sales), 2),
    }

if __name__ == "__main__":
    print(build())
