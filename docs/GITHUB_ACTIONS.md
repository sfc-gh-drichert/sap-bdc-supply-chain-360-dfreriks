# Deploy with GitHub Actions — the whole demo, any Snowflake account

The workflow **Deploy SC360 demo (data platform + Native App)**
(`.github/workflows/deploy-demo.yml`) deploys the complete demo into **any**
Snowflake account. Each target account is a **GitHub Environment** holding that
account's credentials; you pick the environment when you run the workflow.

## What a run builds

### Part 1 — Data platform (input `data_platform`)

`ci_deploy.py platform` builds database `SAP_SUPPLY_CHAIN_DF_V1`, in this order:

| # | Source | Creates |
|---|--------|---------|
| 1 | `tools/gen_l0_seed.py` | L0 bronze: the 21 SAP BDC Standard Data Product tables (synthetic seed, see `sql/01_l0_sources.md`) |
| 2 | `sql/03_l2_analytics_dynamic_tables.sql` | L2 gold: `ANALYTICS.DT_*` dynamic tables + `LINEAGE_COUNTS` |
| 3 | `sql/02_appref_serving_views.sql` | `APP_REF` serving views |
| 4 | `tools/gen_ops_ext.py` + `sql/06_ops_ext_dynamic_tables.sql` | `OPS_EXT` enrichment (orders, equipment, component cover, genealogy) + its dynamic tables |
| 5 | `sql/04_semantic_view.sql` | Semantic view `ANALYTICS.SAP_SUPPLY_CHAIN_360` |
| 6 | `sql/05_cortex_agent.sql` | Cortex agent `ANALYTICS.SAP_SC360_ANALYST_AGENT` (chat with it in Snowflake Intelligence) |

Also creates warehouse `LOAD_WH`, which the dynamic tables use.

### Part 2 — Native App (input `native_app`)

| Step | Creates |
|------|---------|
| Image repository | `SC360_APP_PROVIDER.IMAGES.REPO` |
| Build + push | React/Express container `supply_chain_360:latest` (+ `:<sha>`) |
| Bundle | 18 tables copied from `SAP_SUPPLY_CHAIN_DF_V1` into `SUPPLY_CHAIN_360_PKG.SHARED_DATA` (the app is self-contained and has its own in-app semantic view) |
| Version / patch | First run registers version `V2`; later runs add a patch. Input `publish` also sets the DEFAULT release directive |
| Install | `SUPPLY_CHAIN_360_APP` created or upgraded, privileges + `CORTEX_USER` granted, service started, URL printed in the job summary |

Part 2 bundles from `SAP_SUPPLY_CHAIN_DF_V1`, so on a fresh account run Part 1 first, or
in the same run (the default).

**Existing SAP BDC data is never overwritten.** If `SAP_SUPPLY_CHAIN_DF_V1` already
exists and was *not* created by the seed (no `SC360_SEED` comment), Part 1 is
skipped entirely, and Part 2 bundles that data as-is. Its L2 tables must already
exist in that case (`docs/INSTALL.md`, section A).

Seed values are synthetic and deterministic, so every account gets the same
numbers. They are representative, not a copy of the original reference deployment.

## One-time setup per target account

### 1. Service user (run in the target account as ACCOUNTADMIN)

Generate a key pair locally:

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out sc360_ci.p8 -nocrypt
openssl rsa -in sc360_ci.p8 -pubout -out sc360_ci.pub
```

```sql
CREATE USER IF NOT EXISTS SC360_CI
  TYPE = SERVICE
  DEFAULT_ROLE = ACCOUNTADMIN
  RSA_PUBLIC_KEY = '<contents of sc360_ci.pub without the BEGIN/END lines>';
GRANT ROLE ACCOUNTADMIN TO USER SC360_CI;
```

The workflow defaults to `ACCOUNTADMIN`: it creates an application package,
databases, a warehouse and an image repository, and it grants account-level
privileges (`CREATE COMPUTE POOL`, `BIND SERVICE ENDPOINT`, `CREATE WAREHOUSE`,
`SNOWFLAKE.CORTEX_USER`) to the app. To use a narrower role, set the `SNOWFLAKE_ROLE`
environment variable. That role needs those privileges with grant option, plus
`CREATE APPLICATION PACKAGE`, `CREATE APPLICATION`, `CREATE DATABASE` and
`CREATE WAREHOUSE` on the account. Only the ACCOUNTADMIN path is expected to work
out of the box.

If the account has a network policy, allow the GitHub-hosted runner IPs or use
self-hosted runners.

### 2. GitHub Environment

Repo → **Settings → Environments → New environment** (e.g. `us-demo`, `eu-demo`):

| Kind | Name | Value |
|------|------|-------|
| Secret | `SNOWFLAKE_ACCOUNT` | Account identifier, e.g. `myorg-myaccount` |
| Secret | `SNOWFLAKE_USER` | `SC360_CI` |
| Secret | `SNOWFLAKE_PRIVATE_KEY` | Full contents of `sc360_ci.p8` (PEM, including BEGIN/END lines) |
| Secret *(optional)* | `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` | Only if the key is encrypted |
| Variable *(optional)* | `SNOWFLAKE_ROLE` | Defaults to `ACCOUNTADMIN` |

Add environment protection rules (required reviewers) if you want manual approval
before deploying to a given account.

## Running

**Actions → Deploy SC360 demo (data platform + Native App) → Run workflow**, then set:

- `environment` — e.g. `us-demo`
- `data_platform` — Part 1; leave on for the first deploy, turn off for app-only changes
- `native_app` — Part 2; turn off to deploy only the database, semantic view and agent
- `publish` — set the DEFAULT release directive (upgrades org-listing consumers
  automatically; leave off unless you mean to release)

From the CLI:

```bash
gh workflow run deploy-demo.yml -f environment=us-demo
gh workflow run deploy-demo.yml -f environment=eu-demo -f data_platform=false -f label="UI fix"
```

To deploy to several accounts, run the workflow once per environment.

## Requirements and limits

- The target account must support **Snowpark Container Services**. Trial
  accounts and some regions don't.
- A version holds up to 130 patches. Once `V2` is full, set `SC360_VERSION` (env
  in the workflow) to a new version name.
- The app is installed with `USING VERSION`. An existing **dev-mode** install
  (`snow app run`) is not upgraded; drop it first.
- Publishing an org listing is still manual (`scripts/create_org_listing.py`) after
  a run with `publish` on.

## Running the same steps locally

```bash
pip install -r requirements-ci.txt
python scripts/ci_deploy.py platform --connection my_conn   # Part 1
python scripts/ci_deploy.py provider --connection my_conn   # Part 2 from here
scripts/build_and_push.sh my_conn <registry_host>
python scripts/ci_deploy.py bundle  --connection my_conn
python scripts/ci_deploy.py release --connection my_conn
python scripts/ci_deploy.py install --connection my_conn
```

## Teardown

```sql
DROP APPLICATION IF EXISTS SUPPLY_CHAIN_360_APP CASCADE;  -- also drops its pool, warehouse, service
DROP APPLICATION PACKAGE IF EXISTS SUPPLY_CHAIN_360_PKG;
DROP DATABASE IF EXISTS SC360_APP_PROVIDER;
DROP DATABASE IF EXISTS SAP_SUPPLY_CHAIN_DF_V1;  -- only if it was created by the seed
```
