#!/usr/bin/env python3
"""
Create a region-scoped ORGANIZATION LISTING for the Supply Chain 360 Native App.

organization_profile INTERNAL publishes to all internal org accounts. Scoping
access_regions to a SINGLE region avoids cross-region auto-fulfillment (each
region hosts its own governed install).

Prereqs (per account): package version registered + added to DEFAULT channel +
default release directive set (deploy_native_app.py does this).

Usage:
  python create_org_listing.py --target dfreriksdemo       --region PUBLIC.AWS_US_WEST_2
  python create_org_listing.py --target dfreriks_eu_demo   --region PUBLIC.AWS_EU_CENTRAL_1
  python create_org_listing.py --target dfreriks_apac_demo --region PUBLIC.AWS_AP_SOUTHEAST_2
"""
import argparse
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sf_conn import connect as _connect  # noqa: E402
import os

PKG = "SUPPLY_CHAIN_360_PKG"
LISTING = "SUPPLY_CHAIN_360_ORG"
CONTACT = os.environ.get("LISTING_CONTACT", "you@example.com")
DESC = ("Self-contained SAP Supply Chain 360 dashboard (React + Express on Snowpark "
        "Container Services) with bundled data and a Cortex Analyst 'Ask the Agent' "
        "page powered by the SAP_SC360_ANALYST_AGENT semantic model. No data setup required.")


def connect(conn_name, **kw):
    """connections.toml name, or None to use SNOWFLAKE_* env vars (see sf_conn.py)."""
    return _connect(conn_name, **kw)


def create(target, region, wh):
    manifest = f'''title: "SAP Supply Chain 360"
description: "{DESC}"
organization_profile: "INTERNAL"
organization_targets:
  access:
  - all_internal_accounts: true
  discovery:
  - all_internal_accounts: true
locations:
  access_regions:
  - name: "{region}"
approver_contact: "{CONTACT}"
support_contact: "{CONTACT}"
request_approval_type: "REQUEST_AND_APPROVE_OUTSIDE_SNOWFLAKE"
resharing:
  enabled: false
'''
    conn = connect(target, warehouse=wh)
    cur = conn.cursor()
    cur.execute(f"USE WAREHOUSE {wh}")
    cur.execute(f"CREATE ORGANIZATION LISTING {LISTING} APPLICATION PACKAGE {PKG} "
                f"AS $$\n{manifest}$$ PUBLISH=TRUE")
    print(target, "->", cur.fetchone()[0])
    cur.execute(f"SHOW LISTINGS LIKE '{LISTING}'")
    cols = [c[0] for c in cur.description]
    row = dict(zip(cols, cur.fetchall()[0]))
    print("  locator:", row.get("uniform_listing_locator"), "| state:", row.get("state"))
    cur.close(); conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--region", required=True, help="e.g. PUBLIC.AWS_US_WEST_2")
    ap.add_argument("--warehouse", default="COMPUTE_WH")
    a = ap.parse_args()
    create(a.target, a.region, a.warehouse)
