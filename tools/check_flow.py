#!/usr/bin/env python3
"""Static end-to-end check of the deploy flow (no Snowflake connection needed).

Walks the same order as `ci_deploy.py platform` + `bundle` and verifies:
  1. every <DB>.<SCHEMA>.<OBJECT> a step reads was created by an earlier step;
  2. every column the L2 SQL reads from an L0 / OPS_EXT table exists in the seed;
  3. every table bundled into the package is exposed by app/setup.sql, and every
     APP_DATA object the server queries exists in setup.sql;
  4. the database name is consistent across SQL, scripts, server and workflow.

    python3 tools/check_flow.py
"""
import os
import re
import sys
from datetime import date, timedelta

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
DB = "SAP_SUPPLY_CHAIN_DF_V1"
errors = []


def read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


def strip_comments(sql):
    return re.sub(r"--[^\n]*", "", sql)


# ---------------------------------------------------------------- seed tables + columns
seed_src = read("tools/gen_l0_seed.py").split("# ---------------------------------------------------------------- write")[0]
seed_src = seed_src.replace("from snowflake.connector.pandas_tools import write_pandas", "") \
                   .replace("from sf_conn import connect  # noqa: E402", "")
g = {"__file__": os.path.join(ROOT, "tools/gen_l0_seed.py")}
exec(seed_src, g)
columns = {f"{DB}.{k}".upper(): [c.upper() for c in pd.DataFrame(v).columns] for k, v in g["rows"].items()}

# OPS_EXT: run the generator's data logic against the seed (in-memory SQLite stands in for Snowflake).
import sqlite3  # noqa: E402

lite = sqlite3.connect(":memory:")
for k, v in g["rows"].items():
    pd.DataFrame(v).to_sql(k.replace(".", "__"), lite)


def q(sql):
    sql = re.sub(r"\b([A-Z_]+)\.(A_[A-Z_]+)\b", r"\1__\2", sql)
    cur = lite.execute(sql)
    cols = [c[0] for c in cur.description]
    out = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in out:  # SQLite returns dates as text
        for c, val in r.items():
            if isinstance(val, str) and re.fullmatch(r"\d{4}-\d\d-\d\d.*", val):
                r[c] = date.fromisoformat(val[:10])
    return out


import random  # noqa: E402

ops_src = read("tools/gen_ops_ext.py")
body = "plants = q(" + ops_src.split("plants = q(", 1)[1].split("# ---------------------------------------------------------------- write")[0]
h = {"q": q, "pd": pd, "date": date, "timedelta": timedelta, "rnd": random.Random(20250901),
     "START": date(2025, 1, 1), "END": date(2025, 9, 30)}
exec(body, h)
ops_tables = re.search(r"tables = \{(.*?)\}", ops_src, re.S).group(1)
for name, var in re.findall(r'"(A_[A-Z_]+)": (\w+)', ops_tables):
    columns[f"{DB}.OPS_EXT.{name}"] = [c.upper() for c in pd.DataFrame(h[var]).columns]
print(f"seed: {len(columns)} L0/OPS_EXT tables generated")

created = set(columns)

# ---------------------------------------------------------------- SQL steps in deploy order
FQN = re.compile(rf"\b{DB}\.([A-Z_0-9]+)\.([A-Z_0-9]+)\b", re.I)
CREATE = re.compile(rf"create\s+(?:or\s+replace\s+)?(?:dynamic\s+table|table|view|semantic\s+view|agent)\s+"
                    rf"({DB}\.[A-Z_0-9]+\.[A-Z_0-9]+)", re.I)
order = ["sql/03_l2_analytics_dynamic_tables.sql", "sql/02_appref_serving_views.sql",
         "sql/06_ops_ext_dynamic_tables.sql", "sql/04_semantic_view.sql", "sql/05_cortex_agent.sql"]
for rel in order:
    sql = strip_comments(read(rel))
    if re.search(r"\bSAP_SUPPLY_CHAIN\b", sql):
        errors.append(f"{rel}: still references the old database name")
    for stmt in re.split(r";\s*\n", sql):
        m = CREATE.search(stmt)
        target = m.group(1).upper() if m else None
        # Objects with an explicit column list: record it, and for `AS SELECT * FROM src`
        # check it matches src's columns exactly (Snowflake: "Invalid column definition list").
        decl = re.search(rf"({DB}\.[A-Z_0-9]+\.[A-Z_0-9]+)\s*\(\s*((?:[A-Z_0-9]+\s*,\s*)*[A-Z_0-9]+)\s*\)\s*"
                         rf"(?:target_lag|comment|as\b)", stmt, re.I)
        if target and decl and decl.group(1).upper() == target:
            cols = [c.strip().upper() for c in decl.group(2).split(",")]
            star = re.search(rf"\bas\s+select\s+\*\s+from\s+({DB}\.[A-Z_0-9]+\.[A-Z_0-9]+)", stmt, re.I)
            if star and star.group(1).upper() in columns:
                src_cols = columns[star.group(1).upper()]
                if cols != src_cols:  # SELECT * maps by position: names and order must match
                    errors.append(f"{rel}: {target} declares {cols} but {star.group(1).upper()} has {src_cols}")
            columns[target] = cols
        for s, o in FQN.findall(stmt):
            ref = f"{DB}.{s}.{o}".upper()
            if ref != target and ref not in created:
                errors.append(f"{rel}: reads {ref} before it is created")
        if target:
            created.add(target)
        # column check: alias.COLUMN against seeded L0 / OPS_EXT tables
        aliases = {a.upper(): f"{DB}.{s}.{o}".upper()
                   for s, o, a in re.findall(rf"\b{DB}\.([A-Z_0-9]+)\.([A-Z_0-9]+)\s+([a-z]\w*)\b", stmt, re.I)
                   if a.upper() not in ("ON", "WHERE", "JOIN", "LEFT", "GROUP", "AS")}
        for a, col in re.findall(r"\b([a-z]\w{0,3})\.([A-Z_][A-Z_0-9]*)\b", stmt):
            fq = aliases.get(a.upper())
            if fq in columns and col.upper() not in columns[fq]:
                errors.append(f"{rel}: {a}.{col} — column missing from seeded {fq}")
    print(f"ok-so-far after {rel}: {len(created)} objects")

# ---------------------------------------------------------------- bundle -> app
from migrate_data import SOURCES  # noqa: E402

setup = read("app/setup.sql")
for name, src in SOURCES.items():
    if src.upper() not in created:
        errors.append(f"bundle: source {src} is never created")
    if f"shared_data.{name}" not in setup:
        errors.append(f"app/setup.sql: no view over shared_data.{name}")
views = set(re.findall(r"VIEW app_data\.(\w+)", setup, re.I))
server = "".join(read(os.path.join("service/app/server/src", p))
                 for p in ["routes/api.ts", "routes/ops.ts", "routes/lineage.ts", "services/analyst.ts"])
for obj in set(re.findall(r"(?:APP_DATA|\$\{DB\})\.([A-Z_0-9]+)", server)):
    if obj not in views and obj != "SAP_SUPPLY_CHAIN_360":
        errors.append(f"server queries APP_DATA.{obj}, not defined in app/setup.sql")
print(f"bundle: {len(SOURCES)} tables, app exposes {len(views)} views")

# ---------------------------------------------------------------- name consistency
for rel in ["scripts/ci_deploy.py", "tools/gen_l0_seed.py", "tools/gen_ops_ext.py", "scripts/migrate_data.py",
            "service/app/server/src/services/analyst.ts", ".github/workflows/deploy-demo.yml"]:
    txt = read(rel)
    if re.search(r"\bSAP_SUPPLY_CHAIN\b", txt):
        errors.append(f"{rel}: still references the old database name")
    if DB not in txt:
        errors.append(f"{rel}: does not mention {DB}")

if errors:
    print("\nFAILED:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"\nflow OK: seed -> sql/03 -> 02 -> 06 -> 04 -> 05 -> bundle -> app, database {DB}")
