#!/usr/bin/env python3
"""Seed the SAP BDC L0 (bronze) layer of SAP_SUPPLY_CHAIN_DF_V1 with representative data.

Used when the target account does not have the SAP BDC Standard Data Products
mounted (e.g. a fresh demo account deployed from GitHub Actions). Creates the
same 21 L0 objects listed in sql/01_l0_sources.md with the same columns the L2
dynamic tables (sql/03) and tools/gen_ops_ext.py read. Values are synthetic and
deterministic (fixed seed) so every account gets an identical dataset.

Keys line up with gen_ops_ext.py: plants 1000-5000, work centers WC-LITHO (San
Jose), WC-LIT2 (Austin) and WC-ASM4 (Singapore) carry the scripted equipment
stories.

    python3 tools/gen_l0_seed.py [connection_name]   (env vars when omitted)
"""
import os
import random
import sys
from datetime import date, timedelta

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from sf_conn import connect  # noqa: E402

DB = os.environ.get("SC360_SOURCE_DB", "SAP_SUPPLY_CHAIN_DF_V1")
rnd = random.Random(20250101)

# ---------------------------------------------------------------- master data
PLANTS = [  # plant, name, city, country, lat, lon
    ("1000", "San Jose HQ", "San Jose", "US", 37.3382, -121.8863),
    ("2000", "Austin Fab", "Austin", "US", 30.2672, -97.7431),
    ("3000", "Dresden Fab", "Dresden", "DE", 51.0504, 13.7373),
    ("4000", "Singapore Hub", "Singapore", "SG", 1.3521, 103.8198),
    ("5000", "Penang Assembly", "Penang", "MY", 5.4141, 100.3288),
]
PNAME = {p[0]: p[1] for p in PLANTS}

WORK_CENTERS = [  # work center, description, plant, monthly available hrs
    ("WC-LITHO", "Lithography", "1000", 620), ("WC-ETCH", "Etching", "1000", 560),
    ("WC-TEST", "Testing", "1000", 480), ("WC-LIT2", "Lithography", "2000", 640),
    ("WC-ETC2", "Etching", "2000", 580), ("WC-TFD2", "Thin Film Deposition", "2000", 600),
    ("WC-TFD3", "Thin Film Deposition", "3000", 590), ("WC-MET3", "Inspection & Metrology", "3000", 520),
    ("WC-ASM3", "Assembly", "3000", 540), ("WC-ASM4", "Assembly", "4000", 660),
    ("WC-TST4", "Testing", "4000", 500), ("WC-PKG4", "Packaging", "4000", 460),
    ("WC-ASM5", "Assembly", "5000", 640), ("WC-PKG5", "Packaging", "5000", 440),
    ("WC-TST5", "Testing", "5000", 480),
]

# Finished goods: inspection & metrology systems, and the plants that build them.
FG = {
    "FG-WI-100": ("Wafer Inspection System WI-100", ["1000", "2000"]),
    "FG-RI-200": ("Reticle Inspection System RI-200", ["2000", "3000"]),
    "FG-MS-300": ("Overlay Metrology System MS-300", ["3000", "4000"]),
    "FG-DR-400": ("Defect Review SEM DR-400", ["4000", "5000"]),
}
# Level-0 components per system (unique per parent so lot ids stay unique).
COMPONENTS = {
    "FG-WI-100": [("CMP-CCD-WI", "High-Res CCD Array", 1, 185000), ("CMP-LAS-WI", "DUV Laser Source", 1, 240000),
                  ("CMP-STG-WI", "Precision Wafer Stage", 1, 160000), ("CMP-OPT-WI", "Inspection Optics Module", 1, 210000),
                  ("CMP-CTL-WI", "Image Processing Computer", 2, 42000)],
    "FG-RI-200": [("CMP-CCD-RI", "TDI Sensor Array", 1, 205000), ("CMP-LAS-RI", "193nm Laser Source", 1, 310000),
                  ("CMP-STG-RI", "Reticle Stage", 1, 145000), ("CMP-OPT-RI", "Reticle Optics Module", 1, 260000),
                  ("CMP-ENC-RI", "Linear Encoder Set", 4, 18000)],
    "FG-MS-300": [("CMP-OPT-MS", "Overlay Optics Module", 1, 175000), ("CMP-STG-MS", "Metrology Stage", 1, 130000),
                  ("CMP-CCD-MS", "Metrology Camera", 2, 64000), ("CMP-CTL-MS", "Metrology Controller", 1, 52000),
                  ("CMP-VIB-MS", "Active Vibration Isolation", 1, 88000)],
    "FG-DR-400": [("CMP-EBC-DR", "Electron Beam Column", 1, 395000), ("CMP-VAC-DR", "Vacuum Chamber", 1, 120000),
                  ("CMP-STG-DR", "SEM Wafer Stage", 1, 150000), ("CMP-DET-DR", "Secondary Electron Detector", 2, 58000),
                  ("CMP-CTL-DR", "SEM Control Computer", 1, 46000)],
}
SUBCOMPONENTS = [  # parent component, material, desc, qty, cost
    ("CMP-LAS-WI", "SUB-LDIODE-01", "Laser Diode Pack", 2, 14000), ("CMP-LAS-RI", "SUB-LDIODE-01", "Laser Diode Pack", 3, 14000),
    ("CMP-STG-WI", "SUB-MOTOR-01", "Linear Motor", 2, 9500), ("CMP-STG-RI", "SUB-MOTOR-01", "Linear Motor", 2, 9500),
    ("CMP-STG-MS", "SUB-MOTOR-01", "Linear Motor", 2, 9500), ("CMP-STG-DR", "SUB-MOTOR-01", "Linear Motor", 2, 9500),
    ("CMP-OPT-WI", "SUB-LENS-01", "Fused Silica Lens", 6, 4200), ("CMP-OPT-RI", "SUB-LENS-01", "Fused Silica Lens", 8, 4200),
    ("CMP-EBC-DR", "SUB-EGUN-01", "Field Emission Gun", 1, 68000), ("CMP-VAC-DR", "SUB-PUMP-01", "Turbo Molecular Pump", 2, 11000),
]
SUPPLIERS = [("100100", "Zeiss Precision Optics"), ("100200", "Coherent Lasers Inc"), ("100300", "Hamamatsu Photonics"),
             ("100400", "PI Motion Systems"), ("100500", "Edwards Vacuum"), ("100600", "Heidenhain Encoders")]
SUPPLIED = [  # material -> supplier (the SAP supplier-quality scorecard covers these six)
    ("CMP-OPT-WI", "100100"), ("CMP-LAS-WI", "100200"), ("CMP-CCD-WI", "100300"),
    ("CMP-STG-RI", "100400"), ("CMP-VAC-DR", "100500"), ("CMP-ENC-RI", "100600"),
]
SHIPPING_POINTS = [("SP01", "San Jose Shipping", "1000"), ("SP02", "Austin Shipping", "2000"),
                   ("SP03", "Dresden Shipping", "3000"), ("SP04", "Singapore Sea Freight", "4000"),
                   ("SP05", "Penang Shipping", "5000"), ("SP06", "Singapore Air Hub", "4000")]

MONTHS = [date(2025, m, 1) for m in range(1, 10)]  # Jan..Sep 2025


def money(x):
    return round(x, 2)


rows = {}
rows["PLANT.A_PLANT"] = [dict(PLANT=p, PLANT_NAME=n, CITY=c, COUNTRY=k, COMPANY_CODE="1000" if k == "US" else p,
                              LATITUDE=la, LONGITUDE=lo) for p, n, c, k, la, lo in PLANTS]
rows["WORK_CENTER.A_WORK_CENTER"] = [dict(WORK_CENTER=w, WORK_CENTER_DESC=d, PLANT=p, AVAILABLE_CAPACITY_HRS=h)
                                     for w, d, p, h in WORK_CENTERS]
rows["WORK_CENTER.A_WORK_CENTER_CAPACITY"] = [
    dict(WORK_CENTER=w, PLANT=p, PERIOD_DATE=m, AVAILABLE_CAPACITY_HRS=h,
         USED_CAPACITY_HRS=round(h * rnd.uniform(0.62, 0.97 if d in ("Lithography", "Assembly") else 0.88), 1))
    for w, d, p, h in WORK_CENTERS for m in MONTHS[3:]]  # Apr..Sep -> 90 rows

kpi = []
for p, n, *_ in PLANTS:
    base = rnd.uniform(72, 84)
    for i, m in enumerate(MONTHS):
        dip = 6 if (p in ("2000", "4000") and m.month >= 7) else 0
        kpi.append(dict(PLANT=p, PERIOD_DATE=m, OEE_PCT=round(base + rnd.gauss(0, 1.8) - dip, 1),
                        CYCLE_TIME_AVG=round(rnd.uniform(18, 34), 1), THROUGHPUT=rnd.randint(14, 32),
                        SCRAP_RATE_PCT=round(rnd.uniform(0.6, 3.2) + dip * 0.15, 2),
                        ON_TIME_DELIVERY_PCT=round(rnd.uniform(86, 97) - dip, 1),
                        INVENTORY_TURNOVER=round(rnd.uniform(3.5, 7.5), 2)))
rows["MANUFACTURING_CODES.A_MANUFACTURING_KPI"] = kpi

bom, bom_no = [], 0
for parent, comps in COMPONENTS.items():
    bom_no += 1
    for c, d, q, cost in comps:
        bom.append(dict(PARENT_MATERIAL=parent, PARENT_DESC=FG[parent][0], BOM_NUMBER=f"{bom_no:08d}", BOM_LEVEL=0,
                        COMPONENT_MATERIAL=c, COMPONENT_DESC=d, COMPONENT_QTY=q, COMPONENT_UOM="EA", BASE_QTY=1,
                        ITEM_CATEGORY="Stock", COMPONENT_COST=cost))
desc = {c: d for comps in COMPONENTS.values() for c, d, *_ in comps}
for parent, c, d, q, cost in SUBCOMPONENTS:
    bom.append(dict(PARENT_MATERIAL=parent, PARENT_DESC=desc[parent], BOM_NUMBER=f"{100 + len(bom):08d}", BOM_LEVEL=1,
                    COMPONENT_MATERIAL=c, COMPONENT_DESC=d, COMPONENT_QTY=q, COMPONENT_UOM="EA", BASE_QTY=1,
                    ITEM_CATEGORY="Non-Stock" if c.startswith("SUB-LENS") else "Stock", COMPONENT_COST=cost))
rows["BILL_OF_MATERIAL.A_BOM_ITEM"] = bom  # 30 rows
rows["BOM_GROUP.A_BOM_GROUP"] = [dict(BOM_GROUP=f"BG{i + 1:02d}", BOM_NUMBER=f"{i + 1:08d}", MATERIAL=m,
                                      DESCRIPTION=FG[m][0], BOM_USAGE="1")
                                 for i, m in enumerate(FG)] + [
    dict(BOM_GROUP="BG05", BOM_NUMBER="00000100", MATERIAL="CMP-LAS-WI", DESCRIPTION="Laser sub-assembly", BOM_USAGE="1")]
rows["SALES_BOM.A_SALES_BOM"] = [dict(SALES_BOM=f"SB{i + 1:02d}", MATERIAL=m, COMPONENT=c, QUANTITY=1)
                                 for i, (m, c) in enumerate([(m, f"SVC-{m[3:]}") for m in FG] +
                                                            [(m, f"KIT-{m[3:]}") for m in FG] + [("FG-WI-100", "SW-ANALYTICS")])]

# Storage locations (13) and stock (23).
sloc = [(p, f"{p[0]}{s:03d}", n) for p in PNAME for s, n in [(1, "Finished Goods"), (2, "Components"), (3, "Cleanroom Stores")]][:13]
rows["STORAGE_LOCATION.A_STORAGE_LOCATION"] = [dict(PLANT=p, STORAGE_LOCATION=s, STORAGE_LOCATION_NAME=n) for p, s, n in sloc]
stock = []
for mat, (d, plants) in FG.items():
    for p in plants:
        q = rnd.randint(1, 4)
        stock.append((mat, d, p, f"{p[0]}001", q, q * sum(c[2] * c[3] for c in COMPONENTS[mat]) * 1.15))
for parent, comps in COMPONENTS.items():
    p = FG[parent][1][0]
    for c, d, _, cost in comps[:4] if parent != "FG-DR-400" else comps[:3]:
        q = rnd.randint(2, 18)
        stock.append((c, d, p, f"{p[0]}002", q, q * cost))
stock = stock[:23]
rows["MANUFACTURING_CODES.A_MATERIAL_STOCK"] = [
    dict(MATERIAL=m, MATERIAL_DESC=d, PLANT=p, STORAGE_LOCATION=s, STOCK_QTY=q, STOCK_VALUE=money(v),
         DAYS_OF_INVENTORY=rnd.randint(8, 210), TURNOVER_RATE=round(rnd.uniform(1.2, 9.0), 2),
         LAST_MOVEMENT_DATE=date(2025, 9, 30) - timedelta(rnd.randint(1, 240)),
         OBSOLETE_FLAG="Y" if i in (7, 15, 21) else "N")
    for i, (m, d, p, s, q, v) in enumerate(stock)]

sq = []
sname = dict(SUPPLIERS)
for mat, sup in SUPPLIED:
    for qd in (date(2025, 1, 1), date(2025, 4, 1), date(2025, 7, 1)):
        total = rnd.randint(20, 120)
        defects = rnd.randint(0, max(1, total // 12))
        otd = round(rnd.uniform(78, 99), 1)
        rate = round(100 * defects / total, 2)
        sq.append(dict(SUPPLIER=sup, SUPPLIER_NAME=sname[sup], MATERIAL=mat, MATERIAL_DESC=desc[mat],
                       TOTAL_DELIVERED=total, DEFECT_QTY=defects, DEFECT_RATE_PCT=rate, ON_TIME_DELIVERY_PCT=otd,
                       QUALITY_SCORE=round(max(40, 100 - rate * 4 - (100 - otd) * 0.8), 1), PERIOD_DATE=qd))
rows["MANUFACTURING_CODES.A_SUPPLIER_QUALITY"] = sq  # 18 rows

# Supply-chain network: 5 plants + 6 suppliers + 3 DCs + 5 customers = 19 nodes.
nodes = [dict(NODE_ID=f"N-PL-{p}", NODE_NAME=n, NODE_TYPE="Plant", CITY=c, COUNTRY=k, LATITUDE=la, LONGITUDE=lo, PLANT=p)
         for p, n, c, k, la, lo in PLANTS]
for (sid, sn), (c, k, la, lo) in zip(SUPPLIERS, [("Oberkochen", "DE", 48.7833, 10.1000), ("Santa Clara", "US", 37.3541, -121.9552),
                                                  ("Hamamatsu", "JP", 34.7108, 137.7261), ("Karlsruhe", "DE", 49.0069, 8.4037),
                                                  ("Burgess Hill", "GB", 50.9545, -0.1287), ("Traunreut", "DE", 47.9625, 12.5936)]):
    nodes.append(dict(NODE_ID=f"N-SU-{sid}", NODE_NAME=sn, NODE_TYPE="Supplier", CITY=c, COUNTRY=k, LATITUDE=la, LONGITUDE=lo, PLANT=None))
for i, (n, c, k, la, lo) in enumerate([("Americas DC", "Reno", "US", 39.5296, -119.8138),
                                       ("EMEA DC", "Rotterdam", "NL", 51.9244, 4.4777),
                                       ("APAC DC", "Hsinchu", "TW", 24.8138, 120.9675)]):
    nodes.append(dict(NODE_ID=f"N-DC-{i + 1}", NODE_NAME=n, NODE_TYPE="Distribution Center", CITY=c, COUNTRY=k,
                      LATITUDE=la, LONGITUDE=lo, PLANT=None))
for i, (n, c, k, la, lo) in enumerate([("TSMC", "Hsinchu", "TW", 24.7736, 121.0138),
                                       ("Samsung Semiconductor", "Pyeongtaek", "KR", 36.9921, 127.1129),
                                       ("Intel Fab", "Chandler", "US", 33.3062, -111.8413),
                                       ("GlobalFoundries", "Malta", "US", 42.9717, -73.7926),
                                       ("Infineon Technologies", "Dresden", "DE", 51.1230, 13.7150)]):
    nodes.append(dict(NODE_ID=f"N-CU-{i + 1}", NODE_NAME=n, NODE_TYPE="Customer", CITY=c, COUNTRY=k,
                      LATITUDE=la, LONGITUDE=lo, PLANT=None))
rows["MANUFACTURING_CODES.A_SUPPLY_CHAIN_NODES"] = nodes

flows = []
def flow(ftype, cat, src, tgt, vol, val):
    flows.append(dict(FLOW_ID=f"FL-{len(flows) + 1:03d}", FLOW_TYPE=ftype, MATERIAL_CATEGORY=cat, SOURCE_NODE=src,
                      TARGET_NODE=tgt, MONTHLY_VOLUME=vol, MONTHLY_VALUE=val))
for (sid, _), plants in zip(SUPPLIERS, [["1000", "2000", "3000"], ["1000", "2000"], ["1000", "4000"],
                                        ["2000", "3000", "5000"], ["4000", "5000"], ["2000", "3000"]]):
    for p in plants:  # 14 procurement lanes
        flow("Procurement", "Components", f"N-SU-{sid}", f"N-PL-{p}", rnd.randint(8, 60), rnd.randint(400, 4800) * 1000)
for a, b in [("3000", "4000"), ("2000", "1000"), ("5000", "4000")]:
    flow("Manufacturing", "Sub-assemblies", f"N-PL-{a}", f"N-PL-{b}", rnd.randint(4, 20), rnd.randint(900, 3200) * 1000)
for p, dc in [("1000", 1), ("2000", 1), ("3000", 2), ("4000", 3), ("5000", 3)]:
    flow("Distribution", "Finished Goods", f"N-PL-{p}", f"N-DC-{dc}", rnd.randint(3, 12), rnd.randint(6000, 22000) * 1000)
for dc, cu in [(3, 1), (3, 2), (1, 3), (1, 4), (2, 5)]:
    flow("Distribution", "Finished Goods", f"N-DC-{dc}", f"N-CU-{cu}", rnd.randint(2, 8), rnd.randint(5000, 18000) * 1000)
flow("Returns", "Finished Goods", "N-CU-1", "N-DC-3", 1, 950000)
flow("Returns", "Components", "N-PL-4000", "N-SU-100300", 2, 320000)
rows["MANUFACTURING_CODES.A_SUPPLY_CHAIN_FLOWS"] = flows[:27]

rows["SHIPPING_POINT.A_SHIPPING_POINT"] = [dict(SHIPPING_POINT=s, SHIPPING_POINT_DESC=d, PLANT=p) for s, d, p in SHIPPING_POINTS]
ship_by_plant = {}
for s, _, p in SHIPPING_POINTS:
    ship_by_plant.setdefault(p, []).append(s)

deliveries = []
for i in range(25):
    mat = list(FG)[i % 4]
    p = FG[mat][1][i % 2]
    planned = date(2025, 1, 15) + timedelta(rnd.randint(0, 250))
    delay = 0 if rnd.random() < 0.72 else rnd.randint(1, 12)
    actual = planned + timedelta(delay)
    deliveries.append(dict(DELIVERY_ID=f"80{1000 + i:06d}", SHIPPING_POINT=rnd.choice(ship_by_plant[p]), MATERIAL=mat,
                           MATERIAL_DESC=FG[mat][0], DELIVERY_QTY=rnd.choice([1, 1, 2, 3]), PLANNED_DELIVERY_DATE=planned,
                           ACTUAL_DELIVERY_DATE=actual, ON_TIME_FLAG="Y" if delay == 0 else "N", DELAY_DAYS=delay,
                           DELIVERY_MONTH=actual.replace(day=1)))
rows["DELIVERY_MGMT_CONFIG.A_DELIVERY"] = deliveries

wc_by_plant = {}
for w, d, p, _ in WORK_CENTERS:
    wc_by_plant.setdefault(p, []).append(w)
orders = []
for i in range(20):
    mat = list(FG)[i % 4]
    p = FG[mat][1][(i // 4) % 2]
    created = date(2025, 1, 6) + timedelta(rnd.randint(0, 230))
    start = created + timedelta(rnd.randint(2, 10))
    finish = start + timedelta(rnd.randint(18, 40))
    planned = rnd.choice([2, 3, 4, 5])
    status = "Delivered" if finish < date(2025, 9, 1) else rnd.choice(["Released", "Created"])
    confirmed = planned if status == "Delivered" else (rnd.randint(0, planned) if status == "Released" else 0)
    scrap = 1 if confirmed and rnd.random() < 0.2 else 0
    orders.append(dict(PRODUCTION_ORDER=f"{1000040000 + i:012d}", ORDER_TYPE="PP02" if i in (6, 13) else "PP01", PLANT=p,
                       MATERIAL=mat, MATERIAL_DESC=FG[mat][0], PLANNED_QTY=planned, CONFIRMED_QTY=confirmed,
                       SCRAP_QTY=scrap, YIELD_QTY=confirmed - scrap, WORK_CENTER=rnd.choice(wc_by_plant[p]),
                       CYCLE_TIME_DAYS=(finish - start).days if status == "Delivered" else None,
                       CREATED_DATE=created, BASIC_START_DATE=start, BASIC_FINISH_DATE=finish, ORDER_STATUS=status))
rows["PRODUCTION_ORDER_CONFIRM.A_PROD_ORD_CONFIRMATION"] = orders
rows["PRODUCTION_VERSION.A_PRODUCTION_VERSION"] = [
    dict(MATERIAL=m, PLANT=p, PRODUCTION_VERSION=f"{k + 1:04d}", DESCRIPTION=f"{FG[m][0]} @ {PNAME[p]}",
         VALID_FROM=date(2024, 1, 1), VALID_TO=date(9999, 12, 31))
    for m in FG for k, p in enumerate(FG[m][1])]  # 8 rows

PROJECTS = [("PRJ-1001", "Austin Fab Capacity Expansion", "2000", "Active", 12.5e6),
            ("PRJ-1002", "Dresden Cleanroom Upgrade", "3000", "Active", 8.2e6),
            ("PRJ-1003", "Singapore Hub Automation", "4000", "Active", 5.6e6),
            ("PRJ-1004", "Penang Assembly Line 3", "5000", "Planned", 4.1e6),
            ("PRJ-1005", "San Jose R&D Lab Refresh", "1000", "Completed", 2.9e6),
            ("PRJ-1006", "MES Rollout Wave 2", "2000", "Active", 3.4e6),
            ("PRJ-1007", "EUV Readiness Program", "1000", "Active", 15.8e6),
            ("PRJ-1008", "Penang Solar Retrofit", "5000", "Completed", 1.7e6)]
proj = []
for pid, n, p, st, cost in PROJECTS:
    var = rnd.uniform(-8, 18)
    comp = 100 if st == "Completed" else (0 if st == "Planned" else rnd.randint(25, 85))
    actual = cost * (1 + var / 100) * (comp / 100 if st != "Completed" else 1)
    start = date(2024, rnd.randint(1, 12), 1)
    proj.append(dict(PROJECT_ID=pid, PROJECT_NAME=n, PLANT=p, PROJECT_STATUS=st, PLANNED_COST=money(cost),
                     ACTUAL_COST=money(actual), BUDGET_VARIANCE_PCT=round(var, 1), START_DATE=start,
                     END_DATE=start + timedelta(rnd.randint(300, 720)), COMPLETION_PCT=comp))
rows["PROJECT.A_PROJECT"] = proj
WBS = ["Engineering", "Procurement", "Installation"]
rows["PROJECT_NETWORK.A_PROJECT_WBS"] = [dict(PROJECT_ID=pid, WBS_ELEMENT=f"{pid}-{k + 1:02d}", WBS_DESCRIPTION=w)
                                         for pid, *_ in PROJECTS for k, w in enumerate(WBS)][:18]
rows["PROJECT_CONFIG_DATA.A_PROJECT_CONFIG"] = [
    dict(PROJECT_PROFILE=f"PP{k + 1:02d}", DESCRIPTION=d, PLANNING_METHOD=m)
    for k, (d, m) in enumerate([("Capital project", "Bottom-up"), ("Facility upgrade", "Top-down"),
                                ("IT rollout", "Bottom-up"), ("R&D program", "Bottom-up"),
                                ("Sustainability", "Top-down"), ("Customer project", "Bottom-up")])]
rows["CHANGE_MASTER.A_CHANGE_MASTER"] = [
    dict(CHANGE_NUMBER=f"ECN-25{k + 1:03d}", DESCRIPTION=d, VALID_FROM=date(2025, k * 2 + 1, 1), STATUS="Released")
    for k, d in enumerate(["CCD array firmware rev C", "Laser source supplier change", "Stage encoder upgrade",
                           "Vacuum seal material change"])]
rows["CHANGE_RECORD.A_CHANGE_RECORD"] = [
    dict(CHANGE_RECORD=f"CR-{k + 1:05d}", CHANGE_NUMBER=f"ECN-25{k + 1:03d}", MATERIAL=m, STATUS=s)
    for k, (m, s) in enumerate([("CMP-CCD-WI", "Completed"), ("CMP-LAS-RI", "In Process"),
                                ("CMP-ENC-RI", "Completed"), ("CMP-VAC-DR", "Open")])]

# ---------------------------------------------------------------- write
con = connect(sys.argv[1] if len(sys.argv) > 1 else None,
              warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "LOAD_WH"))
cur = con.cursor()
cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB} COMMENT = 'SC360_SEED: synthetic SAP BDC L0 for Supply Chain 360'")
for fq, data in rows.items():
    schema, table = fq.split(".")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DB}.{schema}")
    df = pd.DataFrame(data)
    write_pandas(con, df, table, database=DB, schema=schema, auto_create_table=True, overwrite=True,
                 quote_identifiers=False, use_logical_type=True)
    cur.execute(f"ALTER TABLE {DB}.{schema}.{table} SET CHANGE_TRACKING = TRUE")
    print(f"{fq}: {len(df)} rows")
con.close()
