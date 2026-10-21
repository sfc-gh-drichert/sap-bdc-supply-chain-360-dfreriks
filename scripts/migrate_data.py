#!/usr/bin/env python3
"""
Bundle the 18 Supply Chain 360 tables into the application package's
SHARED_DATA schema so the Native App is fully self-contained (no consumer
references).

Two modes:
  * Same-account  — CTAS directly from SAP_SUPPLY_CHAIN_DF_V1 into
                    SUPPLY_CHAIN_360_PKG.SHARED_DATA.
  * Cross-account — extract rows from a SOURCE account and load them into a
                    TARGET account (used to seed EMEA / APAC packages).

Auth uses key-pair connections in ~/.snowflake/connections.toml (names only;
no secrets stored here).

Usage:
  python migrate_data.py --target dfreriksdemo --mode local
  python migrate_data.py --source dfreriksdemo --target dfreriks_eu_demo --mode remote
"""
import argparse
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sf_conn import connect as _connect  # noqa: E402

# target_table -> source fully-qualified object
SOURCES = {
    "DT_MANUFACTURING_KPI":       "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_MANUFACTURING_KPI",
    "DT_PRODUCTION_ORDER_360":    "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_PRODUCTION_ORDER_360",
    "DT_BOM_EXPLOSION":           "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_BOM_EXPLOSION",
    "DT_INVENTORY_OVERVIEW":      "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_INVENTORY_OVERVIEW",
    "DT_DELIVERY_PERFORMANCE":    "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_DELIVERY_PERFORMANCE",
    "DT_WORK_CENTER_UTILIZATION": "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_WORK_CENTER_UTILIZATION",
    "DT_PROJECT_STATUS":          "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_PROJECT_STATUS",
    "DT_SUPPLY_CHAIN_GEO":        "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_SUPPLY_CHAIN_GEO",
    "DT_SUPPLIER_QUALITY":        "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_SUPPLIER_QUALITY",
    "A_SUPPLY_CHAIN_NODES":       "SAP_SUPPLY_CHAIN_DF_V1.MANUFACTURING_CODES.A_SUPPLY_CHAIN_NODES",
    "A_PLANT":                    "SAP_SUPPLY_CHAIN_DF_V1.PLANT.A_PLANT",
    # OPS_EXT demo enrichment (sql/06): fulfillment, loss tree, equipment, cover, genealogy
    "DT_ORDER_FULFILLMENT":       "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_ORDER_FULFILLMENT",
    "DT_OPERATING_RATE":          "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_OPERATING_RATE",
    "DT_EQUIPMENT_HEALTH":        "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_EQUIPMENT_HEALTH",
    "DT_EQUIPMENT_OUTAGE":        "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_EQUIPMENT_OUTAGE",
    "DT_COMPONENT_COVER":         "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_COMPONENT_COVER",
    "DT_SERIAL_GENEALOGY":        "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_SERIAL_GENEALOGY",
    "LINEAGE_COUNTS":             "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.LINEAGE_COUNTS",
}
PKG = "SUPPLY_CHAIN_360_PKG"


def connect(conn_name, **kw):
    """connections.toml name, or None to use SNOWFLAKE_* env vars (see sf_conn.py)."""
    return _connect(conn_name, **kw, paramstyle="qmark")


def ensure_package(cur):
    cur.execute(f"CREATE APPLICATION PACKAGE IF NOT EXISTS {PKG}")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {PKG}.SHARED_DATA")
    cur.execute(f"GRANT USAGE ON SCHEMA {PKG}.SHARED_DATA TO SHARE IN APPLICATION PACKAGE {PKG}")


def grant(cur, name):
    cur.execute(f"GRANT SELECT ON TABLE {PKG}.SHARED_DATA.{name} TO SHARE IN APPLICATION PACKAGE {PKG}")


def local_bundle(target, wh):
    conn = connect(target, warehouse=wh) if wh else connect(target)
    cur = conn.cursor()
    if wh:
        cur.execute(f"USE WAREHOUSE {wh}")
    ensure_package(cur)
    for name, src in SOURCES.items():
        cur.execute(f"CREATE OR REPLACE TABLE {PKG}.SHARED_DATA.{name} AS SELECT * FROM {src}")
        grant(cur, name)
        cur.execute(f"SELECT COUNT(*) FROM {PKG}.SHARED_DATA.{name}")
        print(f"  {target}/{name}: {cur.fetchone()[0]} rows")
    cur.close(); conn.close()


def remote_bundle(source, target, wh):
    s = connect(source); sc = s.cursor()
    extract = {}
    for name, src in SOURCES.items():
        sc.execute(f"DESCRIBE TABLE {src}")
        desc = sc.fetchall()
        coldefs = [(r[0], r[1]) for r in desc]
        cols = [r[0] for r in desc]
        sc.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in cols)} FROM {src}')
        extract[name] = (coldefs, cols, sc.fetchall())
        print(f"  extracted {name}: {len(extract[name][2])} rows")
    sc.close(); s.close()
    t = connect(target, warehouse=wh); tc = t.cursor()
    tc.execute(f"USE WAREHOUSE {wh}")
    ensure_package(tc)
    for name, (coldefs, cols, rows) in extract.items():
        col_sql = ", ".join(f'"{c}" {ty}' for c, ty in coldefs)
        tc.execute(f"CREATE OR REPLACE TABLE {PKG}.SHARED_DATA.{name} ({col_sql})")
        ph = "(" + ",".join(["?"] * len(cols)) + ")"
        collist = ", ".join('"'+c+'"' for c in cols)
        ins = f'INSERT INTO {PKG}.SHARED_DATA.{name} ({collist}) VALUES {ph}'
        for i in range(0, len(rows), 2000):
            tc.executemany(ins, rows[i:i+2000])
        grant(tc, name)
        tc.execute(f"SELECT COUNT(*) FROM {PKG}.SHARED_DATA.{name}")
        print(f"  {target}/{name}: {tc.fetchone()[0]} rows")
    tc.close(); t.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--target", required=True)
    ap.add_argument("--mode", choices=["local", "remote"], default="local")
    ap.add_argument("--warehouse", default="COMPUTE_WH")
    a = ap.parse_args()
    if a.mode == "local":
        local_bundle(a.target, a.warehouse)
    else:
        assert a.source, "--source required for remote mode"
        remote_bundle(a.source, a.target, a.warehouse)
    print("DONE")
