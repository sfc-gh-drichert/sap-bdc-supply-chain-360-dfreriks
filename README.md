# SAP BDC Supply Chain 360

A reference implementation showing how to turn **SAP Business Data Cloud (BDC)
Standard Data Products** into a live, AI-powered supply-chain analytics app on
Snowflake — using a **medallion architecture**, a governed **semantic view**, a
**Cortex Agent**, and a self-contained **Snowflake Native App** (React + Express
on Snowpark Container Services), deployable across multiple regions.

Zero ETL. Zero copy. Full SAP business context preserved.

---

## What's in here

```
sap-bdc-supply-chain-360/
├── sql/                 Medallion + semantic + agent
│   ├── 01_l0_sources.md            L0 bronze — SAP BDC Standard Data Products (21)
│   ├── 02_appref_serving_views.sql Serving — APP_REF app-facing views
│   ├── 03_l2_analytics_dynamic_tables.sql  L2 gold — ANALYTICS dynamic tables
│   ├── 04_semantic_view.sql        SAP_SUPPLY_CHAIN_360 semantic view
│   ├── 05_cortex_agent.sql         SAP_SC360_ANALYST_AGENT
│   └── 06_ops_ext_dynamic_tables.sql  L2 gold — OPS_EXT demo enrichment (fulfillment, loss tree, equipment, cover, genealogy)
├── app/                 Native App package (manifest, setup.sql, spec, snowflake.yml)
├── service/app/         React (Vite) client + Express server + Dockerfile
├── tools/               gen_l0_seed.py (synthetic L0) · gen_ops_ext.py (seeds OPS_EXT) · presales kit + deck generators
├── scripts/             ci_deploy.py (GitHub Actions) · sf_conn · build_and_push · migrate_data · deploy_native_app · create_org_listing
├── .github/workflows/   deploy-demo.yml (whole demo, any account) · validate.yml (PR checks)
└── docs/                ARCHITECTURE.md · INSTALL.md · GITHUB_ACTIONS.md · DEMO_GUIDE.md · demo deck (.pptx)
```

## Architecture at a glance

`SAP BDC Standard Data Products (L0)` → `ANALYTICS dynamic tables (L2)` →
`APP_REF serving views` → `SAP_SUPPLY_CHAIN_360 semantic view` →
`SAP_SC360_ANALYST_AGENT` + Native App "Ask the Agent".

Full detail (diagram + per-table content): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quick start

- **Build the data platform + agent:** run `sql/02` → `sql/06` as (seed `OPS_EXT` first with
  `python3 tools/gen_ops_ext.py`)
  `ACCOUNTADMIN`, then chat with `SAP_SC360_ANALYST_AGENT` in Snowflake
  Intelligence.
- **Deploy the whole demo to any account (recommended):** add a GitHub Environment with
  the account's key-pair secrets and run the **Deploy SC360 demo (data platform + Native App)**
  workflow. Part 1 builds `SAP_SUPPLY_CHAIN` (seeded data, dynamic tables, semantic view,
  Cortex agent); Part 2 builds, packages and installs the Native App.
  See [`docs/GITHUB_ACTIONS.md`](docs/GITHUB_ACTIONS.md).
- **Deploy the Native App manually:** `build_and_push.sh` → `migrate_data.py` →
  `deploy_native_app.py` → `create_org_listing.py`.

Step-by-step runbook: [`docs/INSTALL.md`](docs/INSTALL.md).

## The app

A React dashboard covering **production, inventory, logistics, work centers,
projects, supplier quality and a live supply-chain map**, plus an **Ask the
Agent** page (Cortex Analyst over the bundled `SAP_SUPPLY_CHAIN_360` semantic
view).

Three pages run on the **OPS_EXT** demo enrichment — synthetic but keyed to the
SAP plants, work centers, BOM and suppliers, so they join cleanly to the BDC data:

| Page | What it shows |
|---|---|
| Order Fulfillment | OTIF by plant and month, late orders by root cause, and the late cost (0.5%/day penalty capped at 5%, plus expedite) |
| Equipment Health | 48-hour failure probability, vibration and temperature trends, the outage log and repair cost |
| Components | Days of cover against supplier lead time; cover below lead time means the shortage is already locked in |

Most pages also carry **Ask Cortex**: `SNOWFLAKE.CORTEX.COMPLETE` over SQL facts
for the view on screen, so the answer quotes the numbers shown. The OPS_EXT
figures are representative, not customer data — say so when demoing them.

## Live reference deployment

Deployed as a region-scoped organization listing
(`ORGDATACLOUD$INTERNAL$SUPPLY_CHAIN_360_ORG`) in three regions:

| Region | App URL |
|--------|---------|
| North America | https://arzht4-sfsenorthamerica-dfreriks-aws1-w2.snowflakecomputing.app |
| EMEA | https://ea3ite-sfseeurope-dfreriks-eu-demo.snowflakecomputing.app |
| APAC | https://eahbbd-sfseapac-sap-data-product-demo.snowflakecomputing.app |

> URLs are for the internal reference deployment; consumers get their own URL
> on install.

## Demo

See [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md) and the slide deck
[`docs/SAP_Supply_Chain_360_Demo_Guide.pptx`](docs/SAP_Supply_Chain_360_Demo_Guide.pptx)
(15 slides + presenter notes).

## Presales kit

A set of deliverables aimed at a Snowflake SE rather than a customer, published to
the SAP Partnership Compass page on Seismic. Seismic has no API, so the generators
write a local folder and the upload is manual.

```bash
python3 tools/build_presales_kit.py   # four Word documents
python3 tools/build_presales_deck.py  # ten-slide deck, screenshots from the video
```

Both write to `~/Documents/SAP/Supply_Chain_360_Presales_Kit/`.

| File | Contents |
|---|---|
| `00_START_HERE.docx` | The demo in eight numbers, which file to open, the two demo routes |
| `03_SE_Quick_Start.docx` | Positioning, a ten-minute path, all 13 pages, the 8 agent questions, discovery questions, objections |
| `05_Architecture_and_Install.docx` | The medallion stack, the 9 gold tables, build order, refresh caveat |
| `06_Setup_and_Access.docx` | Both listings, the three region URLs, object inventory |
| `00_Presales_Overview.pptx` | Ten slides — problem, architecture, objects, app, AI, routes, regions, real-vs-demo, the ask |

`docx_kit.py` is vendored here (shared with the supply-chain-ontology project) so
this repo can generate its own documents without an external dependency.

### Figures are verified, not copied

Several existing docs disagreed with each other, so the generators state counts
that were checked against the account on 2026-09-21:

| Figure | Source of truth |
|---|---|
| 16 domain schemas, 21 `A_*` objects, 398 L0 rows | `INFORMATION_SCHEMA.TABLES` |
| 9 L2 dynamic tables, 11 `APP_REF` views | `SHOW DYNAMIC TABLES` / `INFORMATION_SCHEMA` |
| 32 facts, 75 dimensions, 8 verified queries | `DESCRIBE SEMANTIC VIEW` |
| 13 app pages | `service/app/client/src/components/Sidebar.tsx` |

Two apparent contradictions in the older docs are not contradictions: **16 vs 21
products** is 21 `A_*` objects across 16 schemas, and **9 vs 11 tables** is 9
dynamic tables plus `A_PLANT` and `A_SUPPLY_CHAIN_NODES` in the serving layer.
Both numbers are right; they count different things.

### The data window

The bundled dataset is a fixed synthetic snapshot covering **January to September
2025**. Every kit document says so, because an SE who claims the data is current
gets caught by a date axis. Both marketplace listings carry the same statement and
are set to `refresh_rate: STATIC`.

Note also that the nine dynamic tables use `TARGET_LAG = DOWNSTREAM` with nothing
downstream declaring a lag, so they do not refresh on a schedule. That is moot for
the demo — the L0 data is fixed, so a refresh would not move any date — but set an
explicit `TARGET_LAG` if you point this stack at live BDC data products.

### Screenshots

`build_presales_deck.py` pulls frames from the narrated walkthrough with ffmpeg,
cached in `tools/.presales_shots/`. Two things to know:

- The raw frames include a personal bookmarks bar and a `localhost` URL, so every
  frame is cropped. Do not add an uncropped frame.
- The walkthrough is mostly slides and Snowsight; only a few frames show the app
  rendered rather than loading. The Snowflake Intelligence frame is a mid-load
  state and is deliberately **not** used — that slide is text instead.

Check the deck renders before shipping it; an overflowing text box is invisible in
the XML:

```bash
soffice --headless --convert-to pdf 00_Presales_Overview.pptx --outdir /tmp/deckchk
pdftoppm -png -r 70 /tmp/deckchk/00_Presales_Overview.pdf /tmp/deckchk/p
```

## Security notes

- No credentials are committed. Scripts read key-pair connections from
  `~/.snowflake/connections.toml` by connection name; `.gitignore` excludes
  `*.p8`, `.env`, and `connections.toml`.
- L0 SAP BDC products are read-only zero-copy shares; the medallion only reads
  from them.

## Sibling projects

Same pattern, other SAP domains:
`sap-bdc-finance-360` · `sap-bdc-people-360` · `sap-bdc-sales-360`
