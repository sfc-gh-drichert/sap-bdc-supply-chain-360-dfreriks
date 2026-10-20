#!/usr/bin/env python3
"""Generate the OPS_EXT demo-enrichment schema for SAP Supply Chain 360.

Every row is keyed to existing SAP master data in SAP_SUPPLY_CHAIN (plants, work
centers, finished-goods materials, BOM components, suppliers, shipping points), so
the new pages join cleanly to the BDC-sourced tables. Values are synthetic and
deterministic (fixed seed) so US, EU and APAC builds are identical.

Causal model (patterned on fulfillment loss trees):
  nameplate capacity -> planned downtime, equipment outages, component shortages,
  rate loss -> produced units. Lost units push FIFO-scheduled customer orders late;
  each late order carries its root cause and a late cost
  (penalty 0.5%/day of order value, capped at 5%, plus expedite freight).

    python3 gen_ops_ext.py [connection_name]   (SNOWFLAKE_* env vars when omitted)
"""
import os
import random
import sys
from datetime import date, timedelta

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from sf_conn import connect  # noqa: E402

CONN = sys.argv[1] if len(sys.argv) > 1 else None
DB, SCHEMA = os.environ.get("SC360_SOURCE_DB", "SAP_SUPPLY_CHAIN"), "OPS_EXT"
rnd = random.Random(20250901)
START, END = date(2025, 1, 1), date(2025, 9, 30)

con = connect(CONN, database=DB, warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "LOAD_WH"))
cur = con.cursor()


def q(sql):
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


plants = q("SELECT PLANT, PLANT_NAME FROM PLANT.A_PLANT ORDER BY 1")
wcs = q("SELECT WORK_CENTER, WORK_CENTER_DESC, PLANT, AVAILABLE_CAPACITY_HRS FROM WORK_CENTER.A_WORK_CENTER ORDER BY 1")
ships = q("SELECT SHIPPING_POINT, PLANT FROM SHIPPING_POINT.A_SHIPPING_POINT ORDER BY 1")
fgs = q("SELECT DISTINCT MATERIAL, MATERIAL_DESC FROM DELIVERY_MGMT_CONFIG.A_DELIVERY ORDER BY 1")
bom = q("SELECT PARENT_MATERIAL, COMPONENT_MATERIAL, COMPONENT_DESC, COMPONENT_QTY, COMPONENT_COST "
        "FROM BILL_OF_MATERIAL.A_BOM_ITEM WHERE BOM_LEVEL = 0 ORDER BY 1, 2")
supq = q("SELECT DISTINCT SUPPLIER, SUPPLIER_NAME, MATERIAL FROM MANUFACTURING_CODES.A_SUPPLIER_QUALITY")
pmap = {p["PLANT"]: p["PLANT_NAME"] for p in plants}
ship_by_plant = {}
for s in ships:
    ship_by_plant.setdefault(s["PLANT"], []).append(s["SHIPPING_POINT"])

# Supplier for each top-level component: real supplier where SAP has one, else a
# deterministic pick from the same supplier pool (flagged in SUPPLIER_SOURCE).
suppliers = sorted({(r["SUPPLIER"], r["SUPPLIER_NAME"]) for r in supq})
real_sup = {r["MATERIAL"]: (r["SUPPLIER"], r["SUPPLIER_NAME"]) for r in supq}
comp_sup = {}
for b in bom:
    c = b["COMPONENT_MATERIAL"]
    comp_sup[c] = (*real_sup[c], "SAP") if c in real_sup else (*suppliers[sum(map(ord, c)) % len(suppliers)], "DEMO")

# Which plants build which system (from production orders) and system list price.
built = q("SELECT DISTINCT MATERIAL, PLANT FROM PRODUCTION_ORDER_CONFIRM.A_PROD_ORD_CONFIRMATION")
plants_for = {}
for r in built:
    plants_for.setdefault(r["MATERIAL"], []).append(r["PLANT"])
bom_cost = {}
for b in bom:
    bom_cost[b["PARENT_MATERIAL"]] = bom_cost.get(b["PARENT_MATERIAL"], 0) + float(b["COMPONENT_QTY"]) * float(b["COMPONENT_COST"])
list_price = {m: round(c * 2.4, -3) for m, c in bom_cost.items()}
margin_per_unit = {m: round(list_price[m] - bom_cost[m] * 1.15, -2) for m in bom_cost}
fg_desc = {f["MATERIAL"]: f["MATERIAL_DESC"] for f in fgs}

months = pd.date_range(START, END, freq="MS").date
days = [START + timedelta(d) for d in range((END - START).days + 1)]

# ---------------------------------------------------------------- equipment & health
TOOL_TYPES = {"Lithography": ["Stepper", "Track"], "Etching": ["Plasma Etcher"],
              "Thin Film Deposition": ["CVD Chamber", "PVD Chamber"], "Inspection & Metrology": ["Metrology Cell"],
              "Assembly": ["Robotic Assembly Cell"], "Packaging": ["Crating Line"], "Testing": ["Final Test Bay"]}
equip = []
for w in wcs:
    for k, t in enumerate(TOOL_TYPES.get(w["WORK_CENTER_DESC"], ["Tool"])):
        equip.append(dict(EQUIPMENT_ID=f"EQ-{w['WORK_CENTER'][3:]}-{k + 1}", EQUIPMENT_NAME=f"{t} {w['WORK_CENTER'][3:]}-{k + 1}",
                          EQUIPMENT_TYPE=t, WORK_CENTER=w["WORK_CENTER"], PLANT=w["PLANT"],
                          CRITICALITY=rnd.choice(["A", "A", "B", "C"]) if "Litho" in w["WORK_CENTER_DESC"] or "Etch" in w["WORK_CENTER_DESC"] else rnd.choice(["B", "C"]),
                          INSTALL_YEAR=rnd.randint(2016, 2023), REPAIR_COST_PER_HR=rnd.choice([1800, 2400, 3200, 4500])))
# Two scripted degradation stories: a stepper in Austin and the Singapore assembly cell.
STORY = {"EQ-LIT2-1": date(2025, 9, 18), "EQ-ASM4-1": date(2025, 9, 25)}
health, outages = [], []
for e in equip:
    base_v, base_t = rnd.uniform(1.2, 2.2), rnd.uniform(38, 46)
    for d in days:
        drift = 0.0
        if e["EQUIPMENT_ID"] in STORY:
            dd = (d - (STORY[e["EQUIPMENT_ID"]] - timedelta(10))).days
            drift = max(0, dd) * 0.09
        v = base_v * (1 + drift) + rnd.gauss(0, 0.08)
        t = base_t + drift * 14 + rnd.gauss(0, 0.6)
        p = min(0.95, max(0.01, 0.02 + drift * 0.24 + rnd.uniform(0, 0.015)))
        health.append(dict(EQUIPMENT_ID=e["EQUIPMENT_ID"], READING_DATE=d, VIBRATION_MM_S=round(v, 3),
                           TEMPERATURE_C=round(t, 2), FAILURE_PROB_48H=round(p, 4), ANOMALY_FLAG=p > 0.35))
    # Historical outages (random) plus a cross-site repeat pattern on steppers.
    for _ in range(rnd.randint(0, 3)):
        d = rnd.choice(days[:-20])
        hrs = round(rnd.choice([4, 6, 8, 12, 18, 26, 38]) * rnd.uniform(0.8, 1.2), 1)
        outages.append(dict(EQUIPMENT_ID=e["EQUIPMENT_ID"], PLANT=e["PLANT"], WORK_CENTER=e["WORK_CENTER"], START_DATE=d,
                            DOWNTIME_HRS=hrs, EVENT_TYPE=rnd.choice(["Failure", "Corrective", "Corrective", "Planned PM"]),
                            ROOT_CAUSE=rnd.choice(["Bearing wear", "Vacuum leak", "Laser power drift", "Controller fault",
                                                   "Stage encoder error", "Coolant flow loss"])))
outages.append(dict(EQUIPMENT_ID="EQ-LITHO-1", PLANT="1000", WORK_CENTER="WC-LITHO", START_DATE=date(2025, 8, 12),
                    DOWNTIME_HRS=38.0, EVENT_TYPE="Failure",
                    ROOT_CAUSE="Stage encoder error after 5 days of rising vibration (same pattern now on EQ-LIT2-1)"))
for i, o in enumerate(outages):
    e = next(x for x in equip if x["EQUIPMENT_ID"] == o["EQUIPMENT_ID"])
    o["OUTAGE_ID"] = f"OUT-{i + 1:04d}"
    o["REPAIR_COST_USD"] = round(o["DOWNTIME_HRS"] * e["REPAIR_COST_PER_HR"], 0) if o["EVENT_TYPE"] != "Planned PM" else 0

# ---------------------------------------------------------------- component lots, cover
lots = []
for b in bom:
    c = b["COMPONENT_MATERIAL"]
    sid, sname, src = comp_sup[c]
    for k in range(rnd.randint(4, 7)):
        rec = rnd.choice(days[:-5])
        res = rnd.choices(["Accepted", "Accepted with deviation", "Rejected"], [0.82, 0.12, 0.06])[0]
        lots.append(dict(LOT_ID=f"CL-{c[5:]}-{k + 1:02d}", COMPONENT_MATERIAL=c, COMPONENT_DESC=b["COMPONENT_DESC"],
                         SUPPLIER=sid, SUPPLIER_NAME=sname, SUPPLIER_SOURCE=src, RECEIVED_DATE=rec,
                         QTY=rnd.randint(4, 30), UNIT_COST=float(b["COMPONENT_COST"]),
                         INSPECTION_RESULT=res, DEVIATION_NOTE=None if res == "Accepted" else rnd.choice(
                             ["Wavelength stability outside tolerance", "Surface contamination on optics",
                              "Encoder resolution below spec", "Missing CoC documentation", "Vacuum seal leak rate high"])))
cover = []
for p in plants:
    for b in bom:
        if p["PLANT"] not in plants_for.get(b["PARENT_MATERIAL"], []):
            continue
        dc = round(rnd.choice([3, 6, 9, 14, 21, 28, 35, 45]) * rnd.uniform(0.8, 1.2), 1)
        cover.append(dict(PLANT=p["PLANT"], COMPONENT_MATERIAL=b["COMPONENT_MATERIAL"], COMPONENT_DESC=b["COMPONENT_DESC"],
                          SUPPLIER=comp_sup[b["COMPONENT_MATERIAL"]][0], ON_HAND_QTY=rnd.randint(1, 24),
                          DAILY_USAGE=round(rnd.uniform(0.2, 1.4), 2), DAYS_OF_COVER=dc,
                          SUPPLIER_LEAD_TIME_DAYS=rnd.choice([14, 21, 28, 42, 56]),
                          OPEN_PO_QTY=rnd.randint(0, 20), STATUS="Critical" if dc < 7 else "Watch" if dc < 15 else "OK"))

# ---------------------------------------------------------------- operating-rate loss tree
oprate, lost_units = [], {}
for p in plants:
    for m in months:
        nameplate = rnd.randint(18, 34)
        planned = round(nameplate * rnd.uniform(0.02, 0.06), 1)
        eq_hrs = sum(o["DOWNTIME_HRS"] for o in outages if o["PLANT"] == p["PLANT"] and o["START_DATE"].replace(day=1) == m
                     and o["EVENT_TYPE"] != "Planned PM")
        equip_loss = round(min(nameplate * 0.25, eq_hrs / 24 * nameplate / 30 * 3.2), 1)
        short = sum(1 for c in cover if c["PLANT"] == p["PLANT"] and c["STATUS"] == "Critical")
        mat_loss = round(nameplate * rnd.uniform(0.0, 0.05) * (1 + short) * (2.2 if m.month >= 7 and p["PLANT"] in ("2000", "4000") else 1), 1)
        perf = round(nameplate * rnd.uniform(0.02, 0.07), 1)
        prod = round(max(0, nameplate - planned - equip_loss - mat_loss - perf), 1)
        oprate.append(dict(PLANT=p["PLANT"], PLANT_NAME=p["PLANT_NAME"], PERIOD_DATE=m, NAMEPLATE_UNITS=nameplate,
                           PLANNED_DOWNTIME_UNITS=planned, EQUIPMENT_LOSS_UNITS=equip_loss, MATERIAL_SHORTAGE_UNITS=mat_loss,
                           PERFORMANCE_LOSS_UNITS=perf, PRODUCED_UNITS=prod, OPERATING_RATE_PCT=round(100 * prod / nameplate, 1)))
        lost_units[(p["PLANT"], m)] = (equip_loss, mat_loss, perf)

# ---------------------------------------------------------------- customer orders
# Customers are the KG Customer nodes (SAP_SUPPLY_CHAIN.ONTOLOGY.KG_NODE), so
# orders link into the ontology by name.
CUSTOMERS = ["TSMC", "Samsung Semiconductor", "Intel Fab", "GlobalFoundries", "Micron Technology", "SK Hynix",
             "Infineon Technologies", "Texas Instruments"]
orders = []
for i in range(420):
    mat = rnd.choice(list(list_price))
    plant = rnd.choice(plants_for.get(mat, ["1000"]))
    req = rnd.choice(days[10:])
    m = req.replace(day=1)
    eq, mt, pf = lost_units.get((plant, m), (0, 0, 0))
    risk = (eq + mt + pf) / 30
    late_p = min(0.6, 0.06 + risk)
    late = rnd.random() < late_p
    cause, delay = None, 0
    if late:
        w = [eq + 0.1, mt + 0.1, pf * 0.5 + 0.1, 0.6, 0.4]
        cause = rnd.choices(["EQUIPMENT", "MATERIAL_SHORTAGE", "PERFORMANCE", "QUALITY_HOLD", "LOGISTICS"], w)[0]
        delay = rnd.randint(2, 6) if cause in ("LOGISTICS", "PERFORMANCE") else rnd.randint(3, 19)
    qty = rnd.choice([1, 1, 1, 2, 2, 3])
    val = list_price[mat] * qty
    penalty = round(val * min(0.05, 0.005 * delay), 0)
    expedite = round(rnd.choice([0, 0, 8500, 14000, 22000]) if late else 0, 0)
    ship = rnd.choice(ship_by_plant.get(plant, ["SP01"]))
    actual = req + timedelta(delay) if req + timedelta(delay) <= END else None
    status = "Shipped" if actual else ("Open - at risk" if late else "Open")
    orders.append(dict(SALES_ORDER=f"SO-{4500100 + i}", ITEM=10, SOLD_TO=rnd.choice(CUSTOMERS), MATERIAL=mat,
                       MATERIAL_DESC=fg_desc.get(mat, mat), PLANT=plant, SHIPPING_POINT=ship, ORDER_QTY=qty,
                       NET_VALUE_USD=val, REQUESTED_SHIP_DATE=req, ACTUAL_SHIP_DATE=actual,
                       ON_TIME=not late, IN_FULL=not (late and rnd.random() < 0.3), DELAY_DAYS=delay,
                       LATE_CAUSE=cause, PENALTY_USD=penalty, EXPEDITE_USD=expedite, LATE_COST_USD=penalty + expedite,
                       ORDER_STATUS=status, MARGIN_PER_UNIT_USD=margin_per_unit[mat]))

# ---------------------------------------------------------------- serial genealogy & final test
geno, tests = [], []
lots_by_comp = {}
for l in lots:
    lots_by_comp.setdefault(l["COMPONENT_MATERIAL"], []).append(l)
for o in [x for x in orders if x["ACTUAL_SHIP_DATE"]][:260]:
    for u in range(o["ORDER_QTY"]):
        serial = f"SN-{o['MATERIAL'][4:]}-{o['SALES_ORDER'][-4:]}{u}"
        bad = False
        for b in [b for b in bom if b["PARENT_MATERIAL"] == o["MATERIAL"]]:
            cand = [l for l in lots_by_comp[b["COMPONENT_MATERIAL"]] if l["RECEIVED_DATE"] <= o["REQUESTED_SHIP_DATE"]] \
                   or lots_by_comp[b["COMPONENT_MATERIAL"]]
            lot = rnd.choice(cand)
            bad |= lot["INSPECTION_RESULT"] != "Accepted"
            geno.append(dict(SERIAL_NO=serial, MATERIAL=o["MATERIAL"], PLANT=o["PLANT"], SALES_ORDER=o["SALES_ORDER"],
                             COMPONENT_MATERIAL=b["COMPONENT_MATERIAL"], LOT_ID=lot["LOT_ID"]))
        res = rnd.choices(["PASS", "PASS_AFTER_REWORK", "FAIL"], [0.65, 0.25, 0.10] if bad else [0.93, 0.06, 0.01])[0]
        tests.append(dict(SERIAL_NO=serial, MATERIAL=o["MATERIAL"], PLANT=o["PLANT"],
                          TEST_DATE=o["ACTUAL_SHIP_DATE"] - timedelta(rnd.randint(1, 4)), RESULT=res,
                          DEFECT_CODE=None if res == "PASS" else rnd.choice(["OPT-ALIGN", "STAGE-REPEAT", "LASER-PWR", "SENSOR-NOISE"]),
                          REWORK_HRS=0 if res == "PASS" else round(rnd.uniform(2, 30), 1),
                          SENSITIVITY_NM=round(rnd.gauss(18 if not bad else 21, 1.2), 2)))

# ---------------------------------------------------------------- write
cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DB}.{SCHEMA} COMMENT = "
            "'Demo enrichment keyed to SAP master data: orders, equipment, component lots, genealogy. Synthetic.'")
tables = {"A_SALES_ORDER_ITEM": orders, "A_EQUIPMENT": equip, "A_EQUIPMENT_HEALTH_DAILY": health,
          "A_EQUIPMENT_OUTAGE": outages, "A_OPERATING_RATE": oprate, "A_COMPONENT_LOT": lots,
          "A_COMPONENT_COVER": cover, "A_SERIAL_GENEALOGY": geno, "A_FINAL_TEST": tests}
for name, rows in tables.items():
    df = pd.DataFrame(rows)
    write_pandas(con, df, name, database=DB, schema=SCHEMA, auto_create_table=True, overwrite=True,
                 quote_identifiers=False, use_logical_type=True)
    # overwrite recreates the table; re-enable change tracking for the L2 dynamic tables.
    cur.execute(f"ALTER TABLE {DB}.{SCHEMA}.{name} SET CHANGE_TRACKING = TRUE")
    print(f"{name}: {len(df)} rows")
con.close()
