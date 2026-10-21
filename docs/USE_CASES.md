# Use Cases — SAP BDC Supply Chain 360

> Plan-make-deliver visibility across production, inventory, logistics, suppliers and projects, with an ontology layer.

- **App:** supply_chain_dashboard_react (React, server 3001 / client 5174); legacy Streamlit supply_chain_dashboard (8504)
- **Semantic view:** `SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SUPPLY_CHAIN_360`
- **Analytics tables:** DT_MANUFACTURING_KPI, DT_PRODUCTION_ORDER_360, DT_BOM_EXPLOSION, DT_WORK_CENTER_UTILIZATION, DT_INVENTORY_OVERVIEW, DT_DELIVERY_PERFORMANCE, DT_SUPPLIER_QUALITY, DT_PROJECT_STATUS, DT_SUPPLY_CHAIN_GEO
- **Catalog audited:** 2026-09-28. Each use case maps to an existing app page and to fields in the semantic view or API.

| # | Use case | Persona | App page |
|---|---|---|---|
| 1 | Plant OEE and yield | Plant manager | Production; Overview |
| 2 | Bottleneck work centers | Production planner | Work Center |
| 3 | Inventory health and obsolescence | Inventory / materials manager | Inventory |
| 4 | On-time delivery | Logistics manager | Logistics; Geography |
| 5 | Supplier quality | Procurement / quality engineer | Overview; Analyst |
| 6 | BOM cost drivers | Cost engineer | BOM |
| 7 | Capital project control | Project controller | Projects |
| 8 | Demand forecasting and optimization | S&OP planner | Forecasting; Optimization |

## 1. Plant OEE and yield

- **Persona:** Plant manager
- **Business question:** How is OEE trending by plant, and where is yield lost?
- **Where in the app:** Production; Overview
- **Data used:** OEE_PCT, YIELD_QTY, SCRAP_RATE_PCT, DEFECT_RATE_PCT, PLANT
- **Ask the agent:**
  - "What is the monthly OEE trend by plant?"
  - "What is the production yield rate by product?"
- **Value:** Focuses improvement on the plants and products with the biggest losses.

## 2. Bottleneck work centers

- **Persona:** Production planner
- **Business question:** Which work centers are over-utilized?
- **Where in the app:** Work Center
- **Data used:** UTILIZATION_PCT, USED_CAPACITY_HRS, AVAILABLE_CAPACITY_HRS, WORK_CENTER
- **Ask the agent:**
  - "Which work centers have the highest utilization and may be bottlenecks?"
- **Value:** Rebalances load before bottlenecks cause late orders.

## 3. Inventory health and obsolescence

- **Persona:** Inventory / materials manager
- **Business question:** How much stock is slow-moving or obsolete?
- **Where in the app:** Inventory
- **Data used:** STOCK_VALUE, OBSOLETE_FLAG, DAYS_OF_INVENTORY, INVENTORY_TURNOVER, LAST_MOVEMENT_DATE
- **Ask the agent:**
  - "What is the breakdown of inventory items and value by obsolete status?"
- **Value:** Frees working capital tied up in excess and obsolete stock.

## 4. On-time delivery

- **Persona:** Logistics manager
- **Business question:** Are we delivering on time, and where are delays?
- **Where in the app:** Logistics; Geography
- **Data used:** ON_TIME_DELIVERY_PCT, ON_TIME_FLAG, DELAY_DAYS, SHIPPING_POINT, source/target geography
- **Ask the agent:**
  - "What is the overall on-time delivery rate?"
- **Value:** Protects customer service levels; pinpoints lanes to fix.

## 5. Supplier quality

- **Persona:** Procurement / quality engineer
- **Business question:** Which suppliers deliver the best and worst quality?
- **Where in the app:** Overview; Analyst
- **Data used:** QUALITY_SCORE, DEFECT_QTY, SUPPLIER_NAME
- **Ask the agent:**
  - "How do suppliers rank by quality score?"
- **Value:** Feeds supplier reviews and dual-sourcing decisions.

## 6. BOM cost drivers

- **Persona:** Cost engineer
- **Business question:** Which components drive product cost?
- **Where in the app:** BOM
- **Data used:** COMPONENT_COST, COMPONENT_MATERIAL, BOM_LEVEL, PARENT_MATERIAL
- **Ask the agent:**
  - "What are the most expensive components across all BOMs?"
- **Value:** Targets value-engineering and should-cost negotiations.

## 7. Capital project control

- **Persona:** Project controller
- **Business question:** Which projects are over budget or behind?
- **Where in the app:** Projects
- **Data used:** BUDGET_VARIANCE_PCT, COMPLETION_PCT, PLANNED_COST, ACTUAL_COST, PROJECT_STATUS
- **Ask the agent:**
  - "Which projects are over budget?"
- **Value:** Early warning on cost overruns.

## 8. Demand forecasting and optimization

- **Persona:** S&OP planner
- **Business question:** What volume should we plan for, and how should supply be allocated?
- **Where in the app:** Forecasting; Optimization
- **Data used:** MONTHLY_VOLUME, MONTHLY_VALUE, THROUGHPUT, PERIOD_DATE
- **Ask the agent:**
  - "What is the monthly volume trend by material category?"
- **Value:** Aligns production and inventory to expected demand.

---
Example agent questions are suggested prompts; validate answers in the app before customer demos.
