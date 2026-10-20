# Deploy with GitHub Actions — any Snowflake account

`.github/workflows/deploy-native-app.yml` deploys the Supply Chain 360 Native App
(React + Express on SPCS) into **any** Snowflake account. Each target account is a
**GitHub Environment** holding that account's credentials; you pick the
environment when you run the workflow.

## What a run does

| Step | Script | Result in the target account |
|------|--------|------------------------------|
| Provider objects | `ci_deploy.py provider` | `LOAD_WH`, image repo `SC360_APP_PROVIDER.IMAGES.REPO` |
| Image | `docker buildx … --push` | `supply_chain_360:latest` (+ `:<sha>`) pushed to that repo |
| Data *(input `data`)* | `ci_deploy.py data` | `SAP_SUPPLY_CHAIN` built from the synthetic seed (`tools/gen_l0_seed.py` → `sql/03` → `sql/02` → `tools/gen_ops_ext.py` → `sql/06`), then 18 tables bundled into `SUPPLY_CHAIN_360_PKG.SHARED_DATA` |
| Release | `ci_deploy.py release` | First run: version `V2` registered. Later runs: a new patch on `V2`. Input `publish` also sets the DEFAULT release directive |
| Install *(input `install`)* | `ci_deploy.py install` | `SUPPLY_CHAIN_360_APP` created or upgraded, privileges + `CORTEX_USER` granted, `version_init()` run, service waited on, URL printed in the job summary |

**Existing SAP BDC data is never overwritten.** If `SAP_SUPPLY_CHAIN` already
exists and was *not* created by the seed (no `SC360_SEED` comment), the data step
skips the build and bundles that data as-is. The L2 tables (`sql/03`, `sql/06`)
must already exist in that case.

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

**Actions → Deploy Native App → Run workflow**, then set:

- `environment` — e.g. `us-demo`
- `data` — leave on for the first deploy; turn off for app-only changes (faster)
- `install` — create or upgrade `SUPPLY_CHAIN_360_APP` in the same account
- `publish` — set the DEFAULT release directive (upgrades org-listing consumers
  automatically; leave off unless you mean to release)

From the CLI:

```bash
gh workflow run deploy-native-app.yml -f environment=us-demo
gh workflow run deploy-native-app.yml -f environment=eu-demo -f data=false -f label="UI fix"
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
python scripts/ci_deploy.py provider --connection my_conn
scripts/build_and_push.sh my_conn <registry_host>
python scripts/ci_deploy.py data    --connection my_conn
python scripts/ci_deploy.py release --connection my_conn
python scripts/ci_deploy.py install --connection my_conn
```

## Teardown

```sql
DROP APPLICATION IF EXISTS SUPPLY_CHAIN_360_APP CASCADE;  -- also drops its pool, warehouse, service
DROP APPLICATION PACKAGE IF EXISTS SUPPLY_CHAIN_360_PKG;
DROP DATABASE IF EXISTS SC360_APP_PROVIDER;
DROP DATABASE IF EXISTS SAP_SUPPLY_CHAIN;  -- only if it was created by the seed
```
