#!/usr/bin/env python3
"""
Deploy the Supply Chain 360 Native App into one account (run once per region).

Assumes the container image is pushed (build_and_push.sh) and the package data
is bundled (migrate_data.py).

Steps: stage 4 app artifacts -> REGISTER VERSION v2 -> add to DEFAULT channel +
set release directive -> CREATE APPLICATION + grants -> version_init() ->
print service status + app URL.

Usage:
  python deploy_native_app.py --target dfreriksdemo
  python deploy_native_app.py --target dfreriks_eu_demo --warehouse COMPUTE_WH
"""
import argparse
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sf_conn import connect as _connect  # noqa: E402
import os
import time
import json

PKG = "SUPPLY_CHAIN_360_PKG"
APP = "SUPPLY_CHAIN_360_APP"
VERSION = "v2"
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
FILES = ["manifest.yml", "setup.sql", "service_spec.yml", "README.md"]


def connect(conn_name, **kw):
    """connections.toml name, or None to use SNOWFLAKE_* env vars (see sf_conn.py)."""
    return _connect(conn_name, **kw)


def deploy(target, wh):
    conn = connect(target, warehouse=wh)
    cur = conn.cursor()
    cur.execute(f"USE WAREHOUSE {wh}")

    cur.execute(f"CREATE STAGE IF NOT EXISTS {PKG}.PUBLIC.APP_STAGE "
                f"ENCRYPTION=(TYPE='SNOWFLAKE_SSE')")
    for f in FILES:
        p = os.path.abspath(os.path.join(APP_DIR, f))
        cur.execute(f"PUT 'file://{p}' @{PKG}.PUBLIC.APP_STAGE "
                    f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
    print(f"{target}: artifacts staged")

    cur.execute(f"ALTER APPLICATION PACKAGE {PKG} REGISTER VERSION {VERSION} "
                f"USING '@{PKG}.PUBLIC.APP_STAGE'")
    cur.execute(f"ALTER APPLICATION PACKAGE {PKG} MODIFY RELEASE CHANNEL DEFAULT ADD VERSION {VERSION}")
    cur.execute(f"ALTER APPLICATION PACKAGE {PKG} MODIFY RELEASE CHANNEL DEFAULT "
                f"SET DEFAULT RELEASE DIRECTIVE VERSION={VERSION} PATCH=0")
    print(f"{target}: version {VERSION} registered + directive set")

    cur.execute(f"CREATE APPLICATION {APP} FROM APPLICATION PACKAGE {PKG} USING VERSION {VERSION}")
    for g in [
        f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO APPLICATION {APP}",
        f"GRANT CREATE COMPUTE POOL ON ACCOUNT TO APPLICATION {APP}",
        f"GRANT CREATE WAREHOUSE ON ACCOUNT TO APPLICATION {APP}",
        f"GRANT BIND SERVICE ENDPOINT ON ACCOUNT TO APPLICATION {APP}",
    ]:
        cur.execute(g)
    print(f"{target}: application created + privileges granted")

    cur.execute(f"CALL {APP}.CORE.VERSION_INIT()")
    print(f"{target}: version_init ->", cur.fetchone()[0])

    for _ in range(30):
        time.sleep(15)
        cur.execute(f"CALL {APP}.CORE.GET_SERVICE_STATUS()")
        try:
            st = json.loads(cur.fetchone()[0])[0]["status"]
        except Exception:
            st = "PENDING"
        if st == "READY":
            break
    cur.execute(f"CALL {APP}.CORE.SELFTEST()")
    print(f"{target}: selftest ->", cur.fetchone()[0])
    cur.execute(f"CALL {APP}.CORE.APP_URL()")
    print(f"{target}: app url -> https://{cur.fetchone()[0]}")
    cur.close(); conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--warehouse", default="COMPUTE_WH")
    a = ap.parse_args()
    deploy(a.target, a.warehouse)
