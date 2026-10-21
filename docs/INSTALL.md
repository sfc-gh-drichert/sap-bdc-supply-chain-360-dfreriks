# Install & Deploy — SAP BDC Supply Chain 360

Two ways to stand this up:

- **A. Build the data platform** (L0 → L2 → serving → semantic → agent) in a
  Snowflake account. This gives you the medallion architecture + the
  `SAP_SC360_ANALYST_AGENT` for Snowflake Intelligence.
- **B. Deploy the self-contained Native App** (React dashboard + Ask the Agent)
  and publish it as an organization listing — optionally across multiple regions.

B bundles its own data, so it does **not** require A to already exist in the
consumer account.

---

## Prerequisites

- Snowflake account with `ACCOUNTADMIN` (or equivalent) role
- The SAP BDC **Standard Data Products** mounted in `SAP_SUPPLY_CHAIN`
  (see [`sql/01_l0_sources.md`](../sql/01_l0_sources.md))
- For the Native App: Docker + `snow` CLI + a Snowflake **image repository**
  (e.g. `SC360_APP_PROVIDER.IMAGES.REPO`)
- Python 3.11+ with `snowflake-connector-python` and `cryptography`
- Key-pair connections in `~/.snowflake/connections.toml` (one per target account)

---

## A. Build the data platform

Run the SQL scripts in order as `ACCOUNTADMIN`:

```sql
-- 1. (reference) confirm the L0 SAP BDC products are mounted — see 01_l0_sources.md
-- 2. serving views (APP_REF)         -- sql/02_appref_serving_views.sql
-- 3. L2 analytics dynamic tables      -- sql/03_l2_analytics_dynamic_tables.sql  (needs LOAD_WH)
-- 4. semantic view                    -- sql/04_semantic_view.sql
-- 5. Cortex agent                     -- sql/05_cortex_agent.sql  (grant SNOWFLAKE.CORTEX_USER first)
```

> Run `03` (L2 dynamic tables) before `02` if your `APP_REF` views reference the
> ANALYTICS dynamic tables — the DDL in each file is idempotent
> (`CREATE OR REPLACE`), so re-run as needed to resolve ordering.

Verify + chat with `SAP_SC360_ANALYST_AGENT` in Snowflake Intelligence:

```sql
SELECT * FROM SEMANTIC_VIEW(
  SAP_SUPPLY_CHAIN.ANALYTICS.SAP_SUPPLY_CHAIN_360
  METRICS MANUFACTURING_KPI.OEE_PCT
  DIMENSIONS MANUFACTURING_KPI.PLANT
);
```

---

## B. Deploy the Native App

> **Recommended:** deploy A *and* B with GitHub Actions — works against any
> Snowflake account with SPCS, no local Docker or SAP BDC mount needed. See
> [`GITHUB_ACTIONS.md`](GITHUB_ACTIONS.md). The manual steps below remain for
> reference.

Example connections: `dfreriksdemo` (US), `dfreriks_eu_demo` (EMEA),
`dfreriks_apac_demo` (APAC).

### 1. Build & push the container image (once per region)

```bash
scripts/build_and_push.sh dfreriksdemo \
  sfsenorthamerica-dfreriks-aws1-w2.registry.snowflakecomputing.com
scripts/build_and_push.sh dfreriks_eu_demo \
  sfseeurope-dfreriks-eu-demo.registry.snowflakecomputing.com
scripts/build_and_push.sh dfreriks_apac_demo \
  sfseapac-sap-data-product-demo.registry.snowflakecomputing.com
```

### 2. Bundle the data into the application package (once per account)

```bash
python scripts/migrate_data.py --target dfreriksdemo --mode local
python scripts/migrate_data.py --source dfreriksdemo --target dfreriks_eu_demo   --mode remote
python scripts/migrate_data.py --source dfreriksdemo --target dfreriks_apac_demo --mode remote
```

Bundles 11 tables into `SUPPLY_CHAIN_360_PKG.SHARED_DATA`.

### 3. Deploy the app (once per account)

```bash
python scripts/deploy_native_app.py --target dfreriksdemo
python scripts/deploy_native_app.py --target dfreriks_eu_demo
python scripts/deploy_native_app.py --target dfreriks_apac_demo
```

Stages artifacts, registers version `v2` on the DEFAULT channel, creates
`SUPPLY_CHAIN_360_APP`, grants privileges, runs `version_init()`, and prints the
service status + app URL.

### 4. Publish the organization listing (once per account)

```bash
LISTING_CONTACT=you@snowflake.com python scripts/create_org_listing.py \
  --target dfreriksdemo       --region PUBLIC.AWS_US_WEST_2
LISTING_CONTACT=you@snowflake.com python scripts/create_org_listing.py \
  --target dfreriks_eu_demo   --region PUBLIC.AWS_EU_CENTRAL_1
LISTING_CONTACT=you@snowflake.com python scripts/create_org_listing.py \
  --target dfreriks_apac_demo --region PUBLIC.AWS_AP_SOUTHEAST_2
```

Region-scoped to avoid cross-region auto-fulfillment. Locator:
`ORGDATACLOUD$INTERNAL$SUPPLY_CHAIN_360_ORG`.

---

## Native App internals

| Artifact | Purpose |
|----------|---------|
| `app/manifest.yml` | Native App manifest v2 (image, endpoint `sc360`, privileges, version_initializer) |
| `app/setup.sql` | App roles, `APP_DATA` views over bundled `SHARED_DATA`, in-app `SAP_SUPPLY_CHAIN_360` semantic view, the SPCS service + lifecycle procs |
| `app/service_spec.yml` | SPCS container/endpoint spec (`sc360`, port 8080) |
| `app/snowflake.yml` | Snowflake CLI project (package `SUPPLY_CHAIN_360_PKG`, app `SUPPLY_CHAIN_360_APP`) |
| `service/app/` | React (Vite) client + Express server + Dockerfile (+ `sap_data_products_full.json` for the BDC Products page) |

## Cortex access

```sql
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO APPLICATION SUPPLY_CHAIN_360_APP;
```

## Teardown

```sql
DROP APPLICATION SUPPLY_CHAIN_360_APP CASCADE;
DROP APPLICATION PACKAGE SUPPLY_CHAIN_360_PKG;
DROP LISTING SUPPLY_CHAIN_360_ORG;
```
