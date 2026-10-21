# Architecture — SAP BDC Supply Chain 360

Supply Chain 360 is built on a **medallion architecture** that sits entirely
inside Snowflake and reads SAP data via **SAP Business Data Cloud (BDC)
zero-copy shares**. No ETL pipelines, no data extraction, full SAP business
context preserved.

```
 SAP S/4HANA                SAP Business Data Cloud
 (source of record)   ─────  Standard Data Products  ─────►  Snowflake
                                (governed, zero-copy)
                                                                │
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  L0  BRONZE  — SAP BDC Standard Data Products (raw A_* objects)            │
 │      21 products across domain schemas: PLANT, WORK_CENTER, PROJECT,       │
 │      BILL_OF_MATERIAL, MANUFACTURING_CODES, DELIVERY_MGMT_CONFIG,          │
 │      PRODUCTION_ORDER_CONFIRM, STORAGE_LOCATION, ... (see 01_l0_sources.md)│
 └──────────────────────────────────────────────────────────────────────────┘
                                                                │  (dynamic tables)
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  L2  GOLD  — SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS (joined/enriched/aggregated) │
 │      DT_MANUFACTURING_KPI · DT_PRODUCTION_ORDER_360 · DT_BOM_EXPLOSION     │
 │      DT_INVENTORY_OVERVIEW · DT_DELIVERY_PERFORMANCE                       │
 │      DT_WORK_CENTER_UTILIZATION · DT_PROJECT_STATUS                        │
 │      DT_SUPPLY_CHAIN_GEO · DT_SUPPLIER_QUALITY                             │
 └──────────────────────────────────────────────────────────────────────────┘
                                                                │  (views)
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  SERVING — SAP_SUPPLY_CHAIN_DF_V1.APP_REF (stable app-facing views)       │
 │      1:1 views over the L2 dynamic tables + A_PLANT, A_SUPPLY_CHAIN_NODES  │
 └──────────────────────────────────────────────────────────────────────────┘
                                                                │
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  SEMANTIC — SAP_SUPPLY_CHAIN_360 semantic view                            │
 │      facts / dimensions / metrics + verified join relationships           │
 └──────────────────────────────────────────────────────────────────────────┘
              │                                        │
              ▼                                        ▼
   SAP_SC360_ANALYST_AGENT                  Native App "Ask the Agent"
   (Snowflake Intelligence)                 (Cortex Analyst in-app)
                                                        │
                                            React + Express on SPCS
                                            (self-contained Native App)
```

## Layer detail

### L0 — Bronze (SAP BDC Standard Data Products)
21 governed supply-chain data products shared from SAP BDC into Snowflake with
**zero copy**, one per domain schema (`A_*` objects). Treated as immutable.
See [`sql/01_l0_sources.md`](../sql/01_l0_sources.md).

### L2 — Gold (`ANALYTICS`)
Analytics-ready **dynamic tables** that join and aggregate L0 into the shapes the
dashboard and semantic model need (`TARGET_LAG` auto-refresh). Coverage:

| L2 object | Business content |
|-----------|------------------|
| `DT_MANUFACTURING_KPI` | Monthly plant KPIs — OEE, scrap rate, throughput, on-time delivery, turns |
| `DT_PRODUCTION_ORDER_360` | Production orders — planned/confirmed/scrap/yield, cycle time |
| `DT_BOM_EXPLOSION` | Multi-level bill of materials with component costs |
| `DT_INVENTORY_OVERVIEW` | Stock positions, days of inventory, turnover, obsolescence |
| `DT_DELIVERY_PERFORMANCE` | Outbound deliveries, on-time %, delay analysis |
| `DT_WORK_CENTER_UTILIZATION` | Work center capacity vs used hours (bottlenecks) |
| `DT_PROJECT_STATUS` | Project budget variance and completion % |
| `DT_SUPPLY_CHAIN_GEO` | Geographic flows supplier→plant→customer (map) |
| `DT_SUPPLIER_QUALITY` | Supplier defect rates and composite quality scores |

DDL: [`sql/03_l2_analytics_dynamic_tables.sql`](../sql/03_l2_analytics_dynamic_tables.sql).

### Serving (`APP_REF`)
Stable, app-facing views over the L2 dynamic tables (plus `A_PLANT`,
`A_SUPPLY_CHAIN_NODES`). This decouples the dashboard/Native App from the
physical analytics objects.
DDL: [`sql/02_appref_serving_views.sql`](../sql/02_appref_serving_views.sql).

> Unlike Finance 360 (which has an explicit `SAP_BDC_L1` silver layer), Supply
> Chain 360 collapses L1 into the raw L0 objects — the dynamic tables read the
> `A_*` products directly, and `APP_REF` is the serving layer.

### Semantic + Agent
- **`SAP_SUPPLY_CHAIN_360`** semantic view — facts, dimensions, metrics and
  verified join relationships over the L2 gold tables.
  DDL: [`sql/04_semantic_view.sql`](../sql/04_semantic_view.sql).
- **`SAP_SC360_ANALYST_AGENT`** — account-level Cortex Agent.
  DDL: [`sql/05_cortex_agent.sql`](../sql/05_cortex_agent.sql).

## Native App packaging

For distribution, the app is packaged as a **self-contained Snowflake Native
App**: the 11 tables the UI needs are **bundled** into the application package's
`SHARED_DATA` schema (no consumer references), and an in-app copy of the
`SAP_SUPPLY_CHAIN_360` semantic view powers the Cortex Analyst page. The React
client + Express server run on **Snowpark Container Services**. See
[`app/`](../app) and [`INSTALL.md`](INSTALL.md).
