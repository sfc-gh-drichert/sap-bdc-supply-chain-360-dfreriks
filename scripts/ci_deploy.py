#!/usr/bin/env python3
"""
CI/CD deploy for the whole Supply Chain 360 demo — works against any Snowflake
account. Every step is idempotent, so the same workflow handles first installs
and upgrades.

Part 1 — data platform (database SAP_SUPPLY_CHAIN):
  platform  seed L0 (synthetic SAP BDC products) -> L2 dynamic tables (sql/03)
            -> APP_REF views (sql/02) -> OPS_EXT seed + DTs (sql/06)
            -> semantic view (sql/04) -> Cortex agent (sql/05).
            Skipped if a real (non-seed) SAP_SUPPLY_CHAIN already exists.

Part 2 — Native App (React dashboard on SPCS):
  provider  LOAD_WH + provider image repository; prints the registry URL
  bundle    copy 18 tables from SAP_SUPPLY_CHAIN into the package SHARED_DATA
  release   stage app/ artifacts, then REGISTER/ADD VERSION (first run) or ADD
            PATCH; optionally publish on the DEFAULT release channel
  install   CREATE APPLICATION or UPGRADE it, grant privileges, run
            version_init(), wait for the service, print the app URL

The container image must be pushed (step `provider` + docker push) before
`release`: a version/patch captures the image digest when it is created.

Auth: SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PRIVATE_KEY env vars (see
sf_conn.py), or --connection <name> from ~/.snowflake/connections.toml.

Usage:
  python scripts/ci_deploy.py all
  python scripts/ci_deploy.py release --publish --label "my change"
  python scripts/ci_deploy.py install --connection my_demo_account
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sf_conn import connect  # noqa: E402
from migrate_data import PKG, SOURCES, ensure_package, grant  # noqa: E402

APP = os.environ.get("SC360_APP_NAME", "SUPPLY_CHAIN_360_APP")
VERSION = os.environ.get("SC360_VERSION", "V2").upper()
SOURCE_DB = os.environ.get("SC360_SOURCE_DB", "SAP_SUPPLY_CHAIN")
LOAD_WH = "LOAD_WH"  # referenced by the dynamic tables in sql/03 and sql/06
# Must match the image path in app/manifest.yml and app/service_spec.yml.
IMAGE_DB, IMAGE_SCHEMA, IMAGE_REPO = "SC360_APP_PROVIDER", "IMAGES", "REPO"
APP_FILES = ["manifest.yml", "setup.sql", "service_spec.yml", "README.md"]
SEED_MARKER = "SC360_SEED"


def log(msg):
    print(f">> {msg}", flush=True)


def gh_output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{key}={value}\n")


def rows(cur, sql):
    cur.execute(sql)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def props(cur, sql):
    """DESCRIBE output as {property: value} (lower-cased keys)."""
    return {str(r[0]).lower(): r[1] for r in (cur.execute(sql) or cur).fetchall()}


# ------------------------------------------------------------------ provider
def step_provider(cur):
    cur.execute(f"CREATE WAREHOUSE IF NOT EXISTS {LOAD_WH} WAREHOUSE_SIZE = XSMALL "
                f"AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE")
    cur.execute(f"USE WAREHOUSE {LOAD_WH}")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {IMAGE_DB}")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {IMAGE_DB}.{IMAGE_SCHEMA}")
    cur.execute(f"CREATE IMAGE REPOSITORY IF NOT EXISTS {IMAGE_DB}.{IMAGE_SCHEMA}.{IMAGE_REPO}")
    repo = rows(cur, f"SHOW IMAGE REPOSITORIES LIKE '{IMAGE_REPO}' IN SCHEMA {IMAGE_DB}.{IMAGE_SCHEMA}")[0]
    url = repo["repository_url"]
    log(f"image repository: {url}")
    gh_output("repository_url", url)
    gh_output("registry_host", url.split("/")[0])
    return url


# ------------------------------------------------------------------ data
def run_sql_file(con, rel):
    with open(os.path.join(ROOT, rel)) as f:
        sql = f.read().replace("SAP_SUPPLY_CHAIN.", f"{SOURCE_DB}.")
    con.execute_string(sql, remove_comments=True)
    log(f"ran {rel}")


CONNECTION = None  # set from --connection; forwarded to the generator tools


def run_tool(script):
    env = dict(os.environ, SNOWFLAKE_WAREHOUSE=LOAD_WH, SC360_SOURCE_DB=SOURCE_DB)
    cmd = [sys.executable, os.path.join(ROOT, "tools", script)] + ([CONNECTION] if CONNECTION else [])
    subprocess.run(cmd, check=True, env=env)


def step_platform(con, cur):
    existing = rows(cur, f"SHOW DATABASES LIKE '{SOURCE_DB}'")
    if existing and SEED_MARKER not in (existing[0].get("comment") or ""):
        # A real SAP BDC source (mounted products + L2 built per docs/INSTALL.md A).
        # Never rebuild it from CI.
        log(f"{SOURCE_DB}: existing (non-seed) database found — data platform left untouched")
        return
    log(f"{SOURCE_DB}: building data platform from synthetic seed")
    run_tool("gen_l0_seed.py")                                   # L0 bronze
    run_sql_file(con, "sql/03_l2_analytics_dynamic_tables.sql")   # L2 gold
    run_sql_file(con, "sql/02_appref_serving_views.sql")          # serving views
    run_tool("gen_ops_ext.py")                                    # OPS_EXT enrichment
    run_sql_file(con, "sql/06_ops_ext_dynamic_tables.sql")
    run_sql_file(con, "sql/04_semantic_view.sql")                 # SAP_SUPPLY_CHAIN_360
    run_sql_file(con, "sql/05_cortex_agent.sql")                  # SAP_SC360_ANALYST_AGENT
    n = rows(cur, f"SELECT COUNT(*) AS n FROM {SOURCE_DB}.ANALYTICS.DT_MANUFACTURING_KPI")[0]["n"]
    log(f"data platform ready: DT_MANUFACTURING_KPI={n} rows, semantic view + agent in {SOURCE_DB}.ANALYTICS")


def step_bundle(cur):
    ensure_package(cur)
    for name, src in SOURCES.items():
        src = src.replace("SAP_SUPPLY_CHAIN.", f"{SOURCE_DB}.", 1)
        cur.execute(f"CREATE OR REPLACE TABLE {PKG}.SHARED_DATA.{name} AS SELECT * FROM {src}")
        grant(cur, name)
        n = rows(cur, f"SELECT COUNT(*) AS n FROM {PKG}.SHARED_DATA.{name}")[0]["n"]
        log(f"bundled {name}: {n} rows")


# ------------------------------------------------------------------ release
def release_channels_enabled(cur):
    p = props(cur, f"DESCRIBE APPLICATION PACKAGE {PKG}")
    return str(p.get("release_channels", "")).upper() in ("ENABLED", "TRUE")


def latest_patch(cur):
    vs = [r for r in rows(cur, f"SHOW VERSIONS IN APPLICATION PACKAGE {PKG}")
          if str(r["version"]).upper() == VERSION]
    return max(int(r["patch"]) for r in vs) if vs else None


def step_release(cur, label, publish):
    ensure_package(cur)
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {PKG}.PUBLIC")
    cur.execute(f"CREATE STAGE IF NOT EXISTS {PKG}.PUBLIC.APP_STAGE ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')")
    for f in APP_FILES:
        p = os.path.join(ROOT, "app", f)
        cur.execute(f"PUT 'file://{p}' @{PKG}.PUBLIC.APP_STAGE AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
    log("app artifacts staged")

    stage = f"@{PKG}.PUBLIC.APP_STAGE"
    modern = release_channels_enabled(cur)
    safe_label = label.replace("'", "''")[:250]
    if latest_patch(cur) is None:
        verb = "REGISTER" if modern else "ADD"
        cur.execute(f"ALTER APPLICATION PACKAGE {PKG} {verb} VERSION {VERSION} USING '{stage}' LABEL = '{safe_label}'")
        log(f"{verb} VERSION {VERSION}")
    else:
        cur.execute(f"ALTER APPLICATION PACKAGE {PKG} ADD PATCH FOR VERSION {VERSION} USING '{stage}' LABEL = '{safe_label}'")
    patch = latest_patch(cur)
    log(f"version {VERSION} patch {patch} (release channels {'enabled' if modern else 'disabled'})")
    gh_output("version", VERSION)
    gh_output("patch", patch)

    if publish:
        if modern:
            chan = rows(cur, f"SHOW RELEASE CHANNELS IN APPLICATION PACKAGE {PKG}")
            default = next((c for c in chan if str(c["name"]).upper() == "DEFAULT"), {})
            if VERSION not in str(default.get("versions", "")).upper():
                cur.execute(f"ALTER APPLICATION PACKAGE {PKG} MODIFY RELEASE CHANNEL DEFAULT ADD VERSION {VERSION}")
            cur.execute(f"ALTER APPLICATION PACKAGE {PKG} MODIFY RELEASE CHANNEL DEFAULT "
                        f"SET DEFAULT RELEASE DIRECTIVE VERSION = {VERSION} PATCH = {patch}")
        else:
            cur.execute(f"ALTER APPLICATION PACKAGE {PKG} SET DEFAULT RELEASE DIRECTIVE "
                        f"VERSION = {VERSION} PATCH = {patch}")
        log(f"default release directive -> {VERSION}.{patch}")
    return patch


# ------------------------------------------------------------------ install
def step_install(cur, patch):
    if patch is None:
        patch = latest_patch(cur)
    if patch is None:
        raise SystemExit(f"No version {VERSION} in {PKG}; run the release step first.")

    if not rows(cur, f"SHOW APPLICATIONS LIKE '{APP}'"):
        cur.execute(f"CREATE APPLICATION {APP} FROM APPLICATION PACKAGE {PKG} "
                    f"USING VERSION {VERSION} PATCH {patch}")
        log(f"created {APP} at {VERSION}.{patch}")
    else:
        d = props(cur, f"DESCRIBE APPLICATION {APP}")
        if str(d.get("version", "")).upper() == "UNVERSIONED":
            raise SystemExit(f"{APP} is a dev-mode (stage) install; drop it or upgrade it manually.")
        if d.get("release_channel_name"):
            cur.execute(f"ALTER APPLICATION {APP} UPGRADE")  # follows the channel's directive
        else:
            cur.execute(f"ALTER APPLICATION {APP} UPGRADE USING VERSION {VERSION} PATCH {patch}")
        log(f"upgraded {APP}")

    for g in ["GRANT CREATE COMPUTE POOL ON ACCOUNT TO APPLICATION {a}",
              "GRANT CREATE WAREHOUSE ON ACCOUNT TO APPLICATION {a}",
              "GRANT BIND SERVICE ENDPOINT ON ACCOUNT TO APPLICATION {a}",
              "GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO APPLICATION {a}"]:
        cur.execute(g.format(a=APP))
    cur.execute(f"CALL {APP}.CORE.VERSION_INIT()")
    log(f"version_init -> {cur.fetchone()[0]}")

    status = "PENDING"
    for _ in range(40):
        cur.execute(f"CALL {APP}.CORE.GET_SERVICE_STATUS()")
        try:
            status = json.loads(cur.fetchone()[0])[0]["status"]
        except Exception:
            status = "PENDING"
        if status == "READY":
            break
        time.sleep(15)
    log(f"service status: {status}")
    cur.execute(f"CALL {APP}.CORE.SELFTEST()")
    log(f"selftest -> {cur.fetchone()[0]}")
    url = None
    for _ in range(20):  # the public endpoint is provisioned shortly after READY
        cur.execute(f"CALL {APP}.CORE.APP_URL()")
        url = cur.fetchone()[0]
        if url and "progress" not in url.lower():
            break
        time.sleep(15)
    log(f"app url: https://{url}")
    gh_output("app_url", f"https://{url}")
    if status != "READY":
        raise SystemExit(f"service not READY ({status}); see CALL {APP}.CORE.GET_SERVICE_LOGS('0','sc360')")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["platform", "provider", "bundle", "release", "install", "all"])
    ap.add_argument("--connection", help="connections.toml name (default: SNOWFLAKE_* env vars)")
    ap.add_argument("--label", default=os.environ.get("SC360_LABEL", "CI deploy"))
    ap.add_argument("--publish", action="store_true",
                    help="set the DEFAULT release directive to the new patch (upgrades channel consumers)")
    a = ap.parse_args()

    global CONNECTION
    CONNECTION = a.connection
    con = connect(a.connection)
    cur = con.cursor()
    cur.execute(f"CREATE WAREHOUSE IF NOT EXISTS {LOAD_WH} WAREHOUSE_SIZE = XSMALL "
                f"AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE")
    cur.execute(f"USE WAREHOUSE {LOAD_WH}")
    patch = None
    if a.step in ("platform", "all"):
        step_platform(con, cur)
    if a.step in ("provider", "all"):
        step_provider(cur)
    if a.step in ("bundle", "all"):
        step_bundle(cur)
    if a.step in ("release", "all"):
        patch = step_release(cur, a.label, a.publish)
    if a.step in ("install", "all"):
        step_install(cur, patch)
    cur.close()
    con.close()


if __name__ == "__main__":
    main()
