-- =====================================================================
-- Semantic layer — SAP_SUPPLY_CHAIN_360 semantic view
-- Powers both the Native App "Ask the Agent" page and the account-level
-- SAP_SC360_ANALYST_AGENT Cortex Agent (see 05_cortex_agent.sql).
-- =====================================================================

create or replace semantic view SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SUPPLY_CHAIN_360
	tables (
		MANUFACTURING_KPI as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_MANUFACTURING_KPI comment='Monthly manufacturing performance metrics by plant including OEE, throughput, scrap rate, on-time delivery, and inventory turnover.',
		PRODUCTION_ORDER as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_PRODUCTION_ORDER_360 primary key (PRODUCTION_ORDER) comment='Production orders with planning, confirmation, yield, and scrap data. Includes cycle time and order status tracking across plants and work centers.',
		BOM_EXPLOSION as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_BOM_EXPLOSION comment='Multi-level bill of materials showing parent-component relationships, quantities, units of measure, and costs for all manufactured products.',
		WORK_CENTER_UTILIZATION as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_WORK_CENTER_UTILIZATION comment='Monthly work center capacity and utilization data. Tracks available vs used hours to identify production bottlenecks across plants.',
		INVENTORY_OVERVIEW as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_INVENTORY_OVERVIEW primary key (MATERIAL) unique (MATERIAL,PLANT) comment='Current stock positions by material, plant, and storage location. Includes days of inventory, turnover rates, and obsolescence flags.',
		DELIVERY_PERFORMANCE as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_DELIVERY_PERFORMANCE primary key (DELIVERY_ID) comment='Outbound delivery tracking with on-time performance, delay analysis, and shipping point metrics for logistics monitoring.',
		SUPPLIER_QUALITY as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_SUPPLIER_QUALITY comment='Quarterly supplier performance scoring including defect rates, on-time delivery percentages, and composite quality scores per material.',
		PROJECT_STATUS as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_PROJECT_STATUS comment='Capital and operational project tracking with budget variance, completion percentage, and WBS element breakdown.',
		SUPPLY_CHAIN_GEO as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_SUPPLY_CHAIN_GEO comment='Geographic supply chain flow data showing material movements between suppliers, plants, and distribution centers with coordinates for map visualization.',
    ORDER_FULFILLMENT as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_ORDER_FULFILLMENT primary key (SALES_ORDER) comment='Customer sales order lines with on-time-in-full (OTIF), delay days, root cause of lateness and late cost (penalty plus expedite). Demo enrichment keyed to SAP plants and materials.',
    OPERATING_RATE as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_OPERATING_RATE comment='Monthly operating-rate loss tree per plant in system units: nameplate split into planned downtime, equipment outage loss, component shortage loss, performance loss and produced units. Demo enrichment.',
    EQUIPMENT_HEALTH as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_EQUIPMENT_HEALTH comment='Daily health readings per production tool (vibration, temperature, 48-hour failure probability, anomaly flag). Demo enrichment keyed to SAP work centers.',
    EQUIPMENT_OUTAGE as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_EQUIPMENT_OUTAGE primary key (OUTAGE_ID) comment='Equipment outage events with downtime hours, root cause and repair cost. Demo enrichment.',
    COMPONENT_COVER as SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_COMPONENT_COVER comment='Component days of cover versus supplier lead time per plant, with open PO quantity and status (Critical/Watch/OK). Demo enrichment keyed to the SAP BOM.'
  )
	relationships (
		DT_PRODUCTION_ORDER_360_TO_DT_INVENTORY_OVERVIEW as PRODUCTION_ORDER(MATERIAL,PLANT) references INVENTORY_OVERVIEW(MATERIAL,PLANT),
		DT_DELIVERY_PERFORMANCE_TO_DT_INVENTORY_OVERVIEW as DELIVERY_PERFORMANCE(MATERIAL) references INVENTORY_OVERVIEW(MATERIAL),
		DT_SUPPLIER_QUALITY_TO_DT_INVENTORY_OVERVIEW as SUPPLIER_QUALITY(MATERIAL) references INVENTORY_OVERVIEW(MATERIAL)
	)
	facts (
		MANUFACTURING_KPI.OEE_PCT as OEE_PCT comment='Overall Equipment Effectiveness percentage — composite of availability, performance, and quality. Higher is better; world-class is 85%+.',
		MANUFACTURING_KPI.CYCLE_TIME_AVG as CYCLE_TIME_AVG comment='Average manufacturing cycle time in days from order start to completion.',
		MANUFACTURING_KPI.SCRAP_RATE_PCT as SCRAP_RATE_PCT comment='Percentage of production scrapped or rejected due to quality defects.',
		MANUFACTURING_KPI.ON_TIME_DELIVERY_PCT as ON_TIME_DELIVERY_PCT comment='Percentage of orders delivered on or before the planned delivery date.',
		MANUFACTURING_KPI.INVENTORY_TURNOVER as INVENTORY_TURNOVER comment='Number of times inventory is consumed and replenished per period. Higher values indicate leaner inventory.',
		PRODUCTION_ORDER.PLANNED_QTY as PLANNED_QTY comment='Planned production quantity for the order in the base unit of measure.',
		PRODUCTION_ORDER.CONFIRMED_QTY as CONFIRMED_QTY comment='Quantity confirmed as completed and posted to inventory.',
		PRODUCTION_ORDER.SCRAP_QTY as SCRAP_QTY comment='Quantity scrapped or rejected during production operations.',
		PRODUCTION_ORDER.YIELD_QTY as YIELD_QTY comment='Good output quantity after accounting for scrap (confirmed minus scrap).',
		PRODUCTION_ORDER.CYCLE_TIME_DAYS as CYCLE_TIME_DAYS comment='Actual cycle time in days from order start to confirmed completion.',
		BOM_EXPLOSION.COMPONENT_QTY as COMPONENT_QTY comment='Required quantity of the component per base quantity of the parent material.',
		BOM_EXPLOSION.BASE_QTY as BASE_QTY comment='Quantity of the parent material to which the component quantity ratio applies.',
		BOM_EXPLOSION.COMPONENT_COST as COMPONENT_COST comment='Standard cost of the component in USD used for BOM cost rollup.',
		WORK_CENTER_UTILIZATION.AVAILABLE_CAPACITY_HRS as AVAILABLE_CAPACITY_HRS comment='Total available machine or labor hours for the work center in the period.',
		WORK_CENTER_UTILIZATION.USED_CAPACITY_HRS as USED_CAPACITY_HRS comment='Actual hours consumed by production orders at the work center.',
		WORK_CENTER_UTILIZATION.UTILIZATION_PCT as UTILIZATION_PCT comment='Utilization rate as percentage of available capacity (used / available * 100). Values above 85% indicate potential bottlenecks.',
		INVENTORY_OVERVIEW.STOCK_QTY as STOCK_QTY comment='Current unrestricted-use stock quantity in the base unit of measure.',
		INVENTORY_OVERVIEW.STOCK_VALUE as STOCK_VALUE comment='Current stock value in USD calculated at standard cost.',
		INVENTORY_OVERVIEW.TURNOVER_RATE as TURNOVER_RATE comment='Annual inventory turnover rate. Higher values indicate faster-moving stock.',
		DELIVERY_PERFORMANCE.DELIVERY_QTY as DELIVERY_QTY comment='Quantity of material delivered in the delivery unit of measure.',
		SUPPLIER_QUALITY.DEFECT_RATE_PCT as DEFECT_RATE_PCT comment='Defect rate as a percentage of total units delivered. Lower is better.',
		SUPPLIER_QUALITY.ON_TIME_DELIVERY_PCT as ON_TIME_DELIVERY_PCT comment='Percentage of supplier deliveries received on or before the agreed purchase order delivery date.',
		SUPPLIER_QUALITY.QUALITY_SCORE as QUALITY_SCORE comment='Composite supplier quality score from 0 to 100. Higher is better.',
		PROJECT_STATUS.PLANNED_COST as PLANNED_COST comment='Total planned budget for the project in USD.',
		PROJECT_STATUS.ACTUAL_COST as ACTUAL_COST comment='Total actual costs incurred to date against the project in USD.',
		PROJECT_STATUS.BUDGET_VARIANCE_PCT as BUDGET_VARIANCE_PCT comment='Budget variance as a percentage of planned cost. Positive = over budget, negative = under budget.',
		PROJECT_STATUS.COMPLETION_PCT as COMPLETION_PCT comment='Percentage of total project scope completed to date (0-100).',
		SUPPLY_CHAIN_GEO.MONTHLY_VALUE as MONTHLY_VALUE comment='Average monthly value of goods flowing between source and target in USD.',
		SUPPLY_CHAIN_GEO.SOURCE_LAT as SOURCE_LAT comment='Latitude coordinate of the source location for map visualization.',
		SUPPLY_CHAIN_GEO.SOURCE_LON as SOURCE_LON comment='Longitude coordinate of the source location for map visualization.',
		SUPPLY_CHAIN_GEO.TARGET_LAT as TARGET_LAT comment='Latitude coordinate of the target location for map visualization.',
		SUPPLY_CHAIN_GEO.TARGET_LON as TARGET_LON comment='Longitude coordinate of the target location for map visualization.',
    ORDER_FULFILLMENT.ORDER_QTY as ORDER_QTY comment='Systems ordered on the sales order line.',
    ORDER_FULFILLMENT.NET_VALUE_USD as NET_VALUE_USD comment='Net order value in USD.',
    ORDER_FULFILLMENT.DELAY_DAYS as DELAY_DAYS comment='Days the order shipped after the requested ship date (0 if on time).',
    ORDER_FULFILLMENT.PENALTY_USD as PENALTY_USD comment='Late-delivery penalty: 0.5% of order value per day late, capped at 5%.',
    ORDER_FULFILLMENT.EXPEDITE_USD as EXPEDITE_USD comment='Expedite freight paid to recover a late order.',
    ORDER_FULFILLMENT.LATE_COST_USD as LATE_COST_USD comment='Total late cost = penalty + expedite.',
    OPERATING_RATE.NAMEPLATE_UNITS as NAMEPLATE_UNITS comment='Nameplate capacity in systems for the plant-month.',
    OPERATING_RATE.PLANNED_DOWNTIME_UNITS as PLANNED_DOWNTIME_UNITS comment='Capacity lost to planned maintenance.',
    OPERATING_RATE.EQUIPMENT_LOSS_UNITS as EQUIPMENT_LOSS_UNITS comment='Capacity lost to unplanned equipment outages.',
    OPERATING_RATE.MATERIAL_SHORTAGE_UNITS as MATERIAL_SHORTAGE_UNITS comment='Capacity lost to component shortages.',
    OPERATING_RATE.PERFORMANCE_LOSS_UNITS as PERFORMANCE_LOSS_UNITS comment='Capacity lost to running below planned rate with no outage.',
    OPERATING_RATE.PRODUCED_UNITS as PRODUCED_UNITS comment='Systems actually produced.',
    OPERATING_RATE.OPERATING_RATE_PCT as OPERATING_RATE_PCT comment='Produced / nameplate x 100.',
    EQUIPMENT_HEALTH.VIBRATION_MM_S as VIBRATION_MM_S comment='Vibration velocity in mm/s; rising values precede bearing and stage failures.',
    EQUIPMENT_HEALTH.TEMPERATURE_C as TEMPERATURE_C comment='Tool temperature in degrees C.',
    EQUIPMENT_HEALTH.FAILURE_PROB_48H as FAILURE_PROB_48H comment='Modelled probability of failure within 48 hours (0-1).',
    EQUIPMENT_OUTAGE.DOWNTIME_HRS as DOWNTIME_HRS comment='Hours the tool was down.',
    EQUIPMENT_OUTAGE.REPAIR_COST_USD as REPAIR_COST_USD comment='Repair cost in USD.',
    COMPONENT_COVER.ON_HAND_QTY as ON_HAND_QTY comment='Component units on hand at the plant.',
    COMPONENT_COVER.DAILY_USAGE as DAILY_USAGE comment='Average component units consumed per day.',
    COMPONENT_COVER.DAYS_OF_COVER as DAYS_OF_COVER comment='On-hand quantity / daily usage, in days.',
    COMPONENT_COVER.SUPPLIER_LEAD_TIME_DAYS as SUPPLIER_LEAD_TIME_DAYS comment='Supplier replenishment lead time in days. Cover below lead time means a shortage is locked in.',
    COMPONENT_COVER.OPEN_PO_QTY as OPEN_PO_QTY comment='Open purchase order quantity for the component.'
  )
	dimensions (
		MANUFACTURING_KPI.PLANT as PLANT comment='SAP plant code (e.g. SJ01=San Jose, AU01=Austin, DR01=Dresden, SG01=Singapore, PN01=Penang).',
		MANUFACTURING_KPI.PLANT_NAME as PLANT_NAME comment='Full plant name (San Jose HQ, Austin Fab, Dresden Fab, Singapore Hub, Penang Assembly).',
		MANUFACTURING_KPI.THROUGHPUT as THROUGHPUT comment='Total units produced at the plant in the reporting period.',
		MANUFACTURING_KPI.PERIOD_DATE as PERIOD_DATE comment='Monthly reporting period date. Use for time-series trend analysis.',
		PRODUCTION_ORDER.PRODUCTION_ORDER as PRODUCTION_ORDER comment='Unique SAP production order number (12-digit identifier).',
		PRODUCTION_ORDER.ORDER_TYPE as ORDER_TYPE comment='SAP order type code (PP01=standard production, PP02=rework order).',
		PRODUCTION_ORDER.PLANT as PLANT comment='SAP plant code where the production order is being executed.',
		PRODUCTION_ORDER.PLANT_NAME as PLANT_NAME comment='Full name of the manufacturing plant executing the order.',
		PRODUCTION_ORDER.MATERIAL as MATERIAL comment='SAP material number for the item being produced.',
		PRODUCTION_ORDER.MATERIAL_DESC as MATERIAL_DESC comment='Material description — the product or component name being manufactured.',
		PRODUCTION_ORDER.WORK_CENTER as WORK_CENTER comment='SAP work center code where production operations are performed.',
		PRODUCTION_ORDER.ORDER_STATUS as ORDER_STATUS comment='Current lifecycle status of the order (Created, Released, Delivered).',
		PRODUCTION_ORDER.CREATED_DATE as CREATED_DATE comment='Date the production order was created in SAP.',
		PRODUCTION_ORDER.BASIC_START_DATE as BASIC_START_DATE comment='Planned start date for production operations.',
		PRODUCTION_ORDER.BASIC_FINISH_DATE as BASIC_FINISH_DATE comment='Planned completion date for the production order.',
		BOM_EXPLOSION.PARENT_MATERIAL as PARENT_MATERIAL comment='SAP material number of the parent assembly or finished good.',
		BOM_EXPLOSION.PARENT_DESC as PARENT_DESC comment='Description of the parent material or top-level assembly.',
		BOM_EXPLOSION.BOM_NUMBER as BOM_NUMBER comment='SAP Bill of Materials header number.',
		BOM_EXPLOSION.BOM_LEVEL as BOM_LEVEL comment='Hierarchy level in the BOM structure (0=top-level, 1=sub-assembly, 2+=components).',
		BOM_EXPLOSION.COMPONENT_MATERIAL as COMPONENT_MATERIAL comment='SAP material number of the component or sub-assembly.',
		BOM_EXPLOSION.COMPONENT_DESC as COMPONENT_DESC comment='Description of the component material used in the assembly.',
		BOM_EXPLOSION.COMPONENT_UOM as COMPONENT_UOM comment='Unit of measure for the component quantity (EA=each, KG=kilogram, M=meter).',
		BOM_EXPLOSION.ITEM_CATEGORY as ITEM_CATEGORY comment='BOM item category (Stock=warehouse-managed, Non-Stock=direct procurement).',
		WORK_CENTER_UTILIZATION.WORK_CENTER as WORK_CENTER comment='SAP work center code (e.g. WC001=Lithography, WC002=Etching).',
		WORK_CENTER_UTILIZATION.WORK_CENTER_DESC as WORK_CENTER_DESC comment='Work center description (Lithography, Etching, Assembly, Test, Packaging).',
		WORK_CENTER_UTILIZATION.PLANT as PLANT comment='SAP plant code where the work center is located.',
		WORK_CENTER_UTILIZATION.PLANT_NAME as PLANT_NAME comment='Full name of the plant where the work center operates.',
		WORK_CENTER_UTILIZATION.PERIOD_DATE as PERIOD_DATE comment='Monthly period for capacity and utilization reporting.',
		INVENTORY_OVERVIEW.MATERIAL as MATERIAL comment='SAP material number — primary identifier for the stocked item.',
		INVENTORY_OVERVIEW.MATERIAL_DESC as MATERIAL_DESC comment='Description of the material held in inventory.',
		INVENTORY_OVERVIEW.PLANT as PLANT comment='SAP plant code where the stock is physically held.',
		INVENTORY_OVERVIEW.PLANT_NAME as PLANT_NAME comment='Full name of the plant holding the inventory.',
		INVENTORY_OVERVIEW.STORAGE_LOCATION as STORAGE_LOCATION comment='SAP storage location code within the plant.',
		INVENTORY_OVERVIEW.DAYS_OF_INVENTORY as DAYS_OF_INVENTORY comment='Number of days of supply based on current stock and average daily consumption.',
		INVENTORY_OVERVIEW.OBSOLETE_FLAG as OBSOLETE_FLAG comment='Indicates whether the material is flagged as obsolete (Y=obsolete, N=active).',
		INVENTORY_OVERVIEW.LAST_MOVEMENT_DATE as LAST_MOVEMENT_DATE comment='Date of the most recent inventory movement.',
		DELIVERY_PERFORMANCE.DELIVERY_ID as DELIVERY_ID comment='SAP outbound delivery document number (unique per shipment).',
		DELIVERY_PERFORMANCE.SHIPPING_POINT as SHIPPING_POINT comment='SAP shipping point code — the organizational unit from which the delivery originates.',
		DELIVERY_PERFORMANCE.SHIPPING_POINT_DESC as SHIPPING_POINT_DESC comment='Description of the shipping point.',
		DELIVERY_PERFORMANCE.MATERIAL as MATERIAL comment='SAP material number of the item included in the delivery.',
		DELIVERY_PERFORMANCE.MATERIAL_DESC as MATERIAL_DESC comment='Description of the delivered material.',
		DELIVERY_PERFORMANCE.ON_TIME_FLAG as ON_TIME_FLAG comment='Indicates whether the delivery met the planned date (Y=on-time, N=late).',
		DELIVERY_PERFORMANCE.DELAY_DAYS as DELAY_DAYS comment='Number of calendar days the delivery was late. Zero for on-time deliveries.',
		DELIVERY_PERFORMANCE.PLANNED_DELIVERY_DATE as PLANNED_DELIVERY_DATE comment='Originally planned delivery date.',
		DELIVERY_PERFORMANCE.ACTUAL_DELIVERY_DATE as ACTUAL_DELIVERY_DATE comment='Actual date the delivery was completed.',
		DELIVERY_PERFORMANCE.DELIVERY_MONTH as DELIVERY_MONTH comment='First day of the delivery month — used for monthly period aggregations.',
		SUPPLIER_QUALITY.SUPPLIER as SUPPLIER comment='SAP supplier (vendor) account number.',
		SUPPLIER_QUALITY.SUPPLIER_NAME as SUPPLIER_NAME comment='Full registered name of the supplier.',
		SUPPLIER_QUALITY.MATERIAL as MATERIAL comment='SAP material number of the item procured from this supplier.',
		SUPPLIER_QUALITY.MATERIAL_DESC as MATERIAL_DESC comment='Description of the material supplied.',
		SUPPLIER_QUALITY.TOTAL_DELIVERED as TOTAL_DELIVERED comment='Total units delivered by the supplier in the reporting period.',
		SUPPLIER_QUALITY.DEFECT_QTY as DEFECT_QTY comment='Number of defective or non-conforming units received from the supplier.',
		SUPPLIER_QUALITY.PERIOD_DATE as PERIOD_DATE comment='Quarterly reporting period date for supplier quality measurement.',
		PROJECT_STATUS.PROJECT_ID as PROJECT_ID comment='Unique SAP project definition identifier.',
		PROJECT_STATUS.PROJECT_NAME as PROJECT_NAME comment='Full descriptive name of the project.',
		PROJECT_STATUS.PLANT as PLANT comment='SAP plant associated with the project.',
		PROJECT_STATUS.PROJECT_STATUS as PROJECT_STATUS comment='Current lifecycle status of the project (Active, Completed, Planned).',
		PROJECT_STATUS.WBS_ELEMENT as WBS_ELEMENT comment='Work Breakdown Structure element code.',
		PROJECT_STATUS.WBS_DESCRIPTION as WBS_DESCRIPTION comment='Description of the WBS element (Engineering, Procurement, Installation, etc.).',
		PROJECT_STATUS.START_DATE as START_DATE comment='Planned start date for the project.',
		PROJECT_STATUS.END_DATE as END_DATE comment='Planned end date or completion deadline for the project.',
		SUPPLY_CHAIN_GEO.FLOW_ID as FLOW_ID comment='Unique identifier for the supply chain flow lane between a source and target location.',
		SUPPLY_CHAIN_GEO.FLOW_TYPE as FLOW_TYPE comment='Type of supply chain flow (Procurement, Manufacturing, Distribution, Returns).',
		SUPPLY_CHAIN_GEO.MATERIAL_CATEGORY as MATERIAL_CATEGORY comment='Category of materials transported in this flow (Raw Materials, Components, Finished Goods).',
		SUPPLY_CHAIN_GEO.MONTHLY_VOLUME as MONTHLY_VOLUME comment='Average monthly unit volume flowing between the source and target locations.',
		SUPPLY_CHAIN_GEO.SOURCE_NAME as SOURCE_NAME comment='Name of the source location (supplier name, plant name, or distribution center).',
		SUPPLY_CHAIN_GEO.SOURCE_TYPE as SOURCE_TYPE comment='Type of source location (Supplier, Plant, Distribution Center).',
		SUPPLY_CHAIN_GEO.SOURCE_CITY as SOURCE_CITY comment='City where the source location is based.',
		SUPPLY_CHAIN_GEO.SOURCE_COUNTRY as SOURCE_COUNTRY comment='Country where the source location is based.',
		SUPPLY_CHAIN_GEO.SOURCE_PLANT as SOURCE_PLANT comment='SAP plant code of the source location (if a plant).',
		SUPPLY_CHAIN_GEO.TARGET_NAME as TARGET_NAME comment='Name of the target or destination location.',
		SUPPLY_CHAIN_GEO.TARGET_TYPE as TARGET_TYPE comment='Type of target location (Plant, Distribution Center, Customer).',
		SUPPLY_CHAIN_GEO.TARGET_CITY as TARGET_CITY comment='City where the target location is based.',
		SUPPLY_CHAIN_GEO.TARGET_COUNTRY as TARGET_COUNTRY comment='Country where the target location is based.',
		SUPPLY_CHAIN_GEO.TARGET_PLANT as TARGET_PLANT comment='SAP plant code of the target location (if a plant).',
    ORDER_FULFILLMENT.SALES_ORDER as SALES_ORDER comment='SAP sales order number.',
    ORDER_FULFILLMENT.SOLD_TO as SOLD_TO comment='Customer (sold-to party), e.g. TSMC, Samsung Foundry, Intel.',
    ORDER_FULFILLMENT.MATERIAL_DESC as MATERIAL_DESC comment='Inspection system ordered.',
    ORDER_FULFILLMENT.PLANT_NAME as PLANT_NAME comment='Plant that builds and ships the order.',
    ORDER_FULFILLMENT.REQUESTED_SHIP_DATE as REQUESTED_SHIP_DATE comment='Customer requested ship date.',
    ORDER_FULFILLMENT.ACTUAL_SHIP_DATE as ACTUAL_SHIP_DATE comment='Actual ship date (null if still open).',
    ORDER_FULFILLMENT.SHIP_MONTH as SHIP_MONTH comment='Month of the requested ship date.',
    ORDER_FULFILLMENT.OTIF as OTIF comment='TRUE when the order shipped on time and in full.',
    ORDER_FULFILLMENT.ON_TIME as ON_TIME comment='TRUE when the order shipped on or before the requested date.',
    ORDER_FULFILLMENT.LATE_CAUSE_LABEL as LATE_CAUSE_LABEL comment='Root cause of lateness: Component shortage, Equipment outage, Quality hold, Rate below plan, Logistics / carrier, or On time.',
    ORDER_FULFILLMENT.ORDER_STATUS as ORDER_STATUS comment='Shipped, Open, or Open - at risk.',
    OPERATING_RATE.PLANT_NAME as PLANT_NAME comment='Plant name for the loss tree.',
    OPERATING_RATE.PERIOD_DATE as PERIOD_DATE comment='Month of the loss tree.',
    OPERATING_RATE.BINDING_CONSTRAINT as BINDING_CONSTRAINT comment='Whether Equipment or Components cost more capacity that month.',
    EQUIPMENT_HEALTH.EQUIPMENT_ID as EQUIPMENT_ID comment='Tool identifier, e.g. EQ-LIT2-1.',
    EQUIPMENT_HEALTH.EQUIPMENT_NAME as EQUIPMENT_NAME comment='Tool name, e.g. Stepper LIT2-1.',
    EQUIPMENT_HEALTH.EQUIPMENT_TYPE as EQUIPMENT_TYPE comment='Tool type (Stepper, Plasma Etcher, CVD Chamber, ...).',
    EQUIPMENT_HEALTH.WORK_CENTER_DESC as WORK_CENTER_DESC comment='Work center the tool belongs to.',
    EQUIPMENT_HEALTH.PLANT_NAME as PLANT_NAME comment='Plant where the tool is installed.',
    EQUIPMENT_HEALTH.CRITICALITY as CRITICALITY comment='Asset criticality A (highest) to C.',
    EQUIPMENT_HEALTH.READING_DATE as READING_DATE comment='Date of the health reading. Use the latest date for current risk.',
    EQUIPMENT_HEALTH.ANOMALY_FLAG as ANOMALY_FLAG comment='TRUE when the reading is anomalous (failure probability above 35%).',
    EQUIPMENT_OUTAGE.OUTAGE_ID as OUTAGE_ID comment='Outage event id.',
    EQUIPMENT_OUTAGE.EQUIPMENT_NAME as EQUIPMENT_NAME comment='Tool that went down.',
    EQUIPMENT_OUTAGE.PLANT_NAME as PLANT_NAME comment='Plant of the outage.',
    EQUIPMENT_OUTAGE.START_DATE as START_DATE comment='Date the outage started.',
    EQUIPMENT_OUTAGE.EVENT_TYPE as EVENT_TYPE comment='Failure, Corrective, or Planned PM.',
    EQUIPMENT_OUTAGE.ROOT_CAUSE as ROOT_CAUSE comment='Root cause recorded for the outage.',
    COMPONENT_COVER.PLANT_NAME as PLANT_NAME comment='Plant holding the component.',
    COMPONENT_COVER.COMPONENT_DESC as COMPONENT_DESC comment='Component description, e.g. High-Res CCD Array.',
    COMPONENT_COVER.SUPPLIER_NAME as SUPPLIER_NAME comment='Supplier of the component.',
    COMPONENT_COVER.STATUS as STATUS comment='Critical (<7 days), Watch (<15 days) or OK.'
  )
	comment='Unified semantic model for SAP Supply Chain analytics covering production planning, bill of materials, work center capacity, inventory management, logistics delivery performance, supplier quality, project management, and manufacturing KPIs. Built from 16 SAP BDC Supply Chain data products with 177 entities.'
	ai_sql_generation 'This semantic view covers SAP supply chain data across 14 tables. Use MANUFACTURING_KPI for OEE, cycle time, scrap rate, and plant-level KPI trends. Use PRODUCTION_ORDER for order-level yield, scrap, and cycle time by material or work center. Use BOM_EXPLOSION for component cost rollup and bill-of-materials analysis. Use WORK_CENTER_UTILIZATION to identify bottlenecks (utilization > 85%). Use INVENTORY_OVERVIEW as the hub table for material/plant-level stock, value, and turnover. INVENTORY_OVERVIEW is linked to PRODUCTION_ORDER, DELIVERY_PERFORMANCE, and SUPPLIER_QUALITY via MATERIAL (and PLANT where applicable). Use DELIVERY_PERFORMANCE for on-time delivery rates and delay analysis. Use SUPPLIER_QUALITY for supplier scorecards and defect trends. Use PROJECT_STATUS for budget variance and project completion. Use SUPPLY_CHAIN_GEO for geographic flow visualization. Use ORDER_FULFILLMENT for customer OTIF, late orders, late cause and late cost. Use OPERATING_RATE for the capacity loss tree and the binding constraint per plant. Use EQUIPMENT_HEALTH (latest READING_DATE per tool) for failure risk; EQUIPMENT_OUTAGE for downtime history and repair cost. Use COMPONENT_COVER for component shortages and days of cover vs lead time. Order, equipment and component tables are representative demo enrichment.'
	ai_verified_queries (
    OTIF_BY_LATE_CAUSE AS (
QUESTION 'What is driving late customer orders and what does it cost?'
VERIFIED_AT 1791504000
VERIFIED_BY '(source=ops_ext)'
ONBOARDING_QUESTION true
SQL 'SELECT LATE_CAUSE_LABEL, COUNT(*) AS ORDERS, SUM(LATE_COST_USD) AS LATE_COST_USD FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_ORDER_FULFILLMENT WHERE NOT ON_TIME GROUP BY LATE_CAUSE_LABEL ORDER BY LATE_COST_USD DESC'),
    TOOLS_AT_RISK AS (
QUESTION 'Which tools have the highest failure risk right now?'
VERIFIED_AT 1791504000
VERIFIED_BY '(source=ops_ext)'
ONBOARDING_QUESTION true
SQL 'SELECT EQUIPMENT_NAME, PLANT_NAME, FAILURE_PROB_48H, ANOMALY_FLAG FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_EQUIPMENT_HEALTH QUALIFY ROW_NUMBER() OVER (PARTITION BY EQUIPMENT_ID ORDER BY READING_DATE DESC) = 1 ORDER BY FAILURE_PROB_48H DESC LIMIT 10'),
    CRITICAL_COMPONENTS AS (
QUESTION 'Which components are below supplier lead time on cover?'
VERIFIED_AT 1791504000
VERIFIED_BY '(source=ops_ext)'
ONBOARDING_QUESTION false
SQL 'SELECT PLANT_NAME, COMPONENT_DESC, SUPPLIER_NAME, DAYS_OF_COVER, SUPPLIER_LEAD_TIME_DAYS FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_COMPONENT_COVER WHERE DAYS_OF_COVER < SUPPLIER_LEAD_TIME_DAYS ORDER BY DAYS_OF_COVER'),
    OPERATING_RATE_BY_PLANT AS (
QUESTION 'What is the operating rate and binding constraint by plant?'
VERIFIED_AT 1791504000
VERIFIED_BY '(source=ops_ext)'
ONBOARDING_QUESTION false
SQL 'SELECT PLANT_NAME, ROUND(100 * SUM(PRODUCED_UNITS) / SUM(NAMEPLATE_UNITS), 1) AS OPERATING_RATE_PCT, SUM(EQUIPMENT_LOSS_UNITS) AS EQUIPMENT_LOSS, SUM(MATERIAL_SHORTAGE_UNITS) AS COMPONENT_LOSS FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_OPERATING_RATE GROUP BY PLANT_NAME ORDER BY OPERATING_RATE_PCT'),
		MONTHLY_OEE_BY_PLANT AS ( 
QUESTION 'What is the monthly OEE trend by plant?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT PLANT_NAME, PERIOD_DATE, OEE_PCT FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_MANUFACTURING_KPI ORDER BY PLANT_NAME, PERIOD_DATE'),
		PRODUCTION_YIELD_BY_PRODUCT AS ( 
QUESTION 'What is the production yield rate by product?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT MATERIAL_DESC, ROUND(100.0 * SUM(YIELD_QTY) / NULLIF(SUM(PLANNED_QTY), 0), 1) AS YIELD_PCT FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_PRODUCTION_ORDER_360 GROUP BY MATERIAL_DESC ORDER BY YIELD_PCT DESC'),
		WORK_CENTER_BOTTLENECKS AS ( 
QUESTION 'Which work centers have the highest utilization and may be bottlenecks?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT WORK_CENTER_DESC, PLANT_NAME, ROUND(AVG(UTILIZATION_PCT), 1) AS AVG_UTILIZATION FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_WORK_CENTER_UTILIZATION GROUP BY WORK_CENTER_DESC, PLANT_NAME HAVING AVG(UTILIZATION_PCT) > 85 ORDER BY AVG_UTILIZATION DESC'),
		ON_TIME_DELIVERY_RATE AS ( 
QUESTION 'What is the overall on-time delivery rate?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT ROUND(100.0 * SUM(CASE WHEN ON_TIME_FLAG = ''Y'' THEN 1 ELSE 0 END) / COUNT(*), 1) AS OTD_PCT, COUNT(*) AS TOTAL_DELIVERIES FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_DELIVERY_PERFORMANCE'),
		INVENTORY_OBSOLESCENCE AS ( 
QUESTION 'What is the breakdown of inventory items and value by obsolete status?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT OBSOLETE_FLAG, COUNT(*) AS ITEMS, SUM(STOCK_VALUE) AS TOTAL_VALUE FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_INVENTORY_OVERVIEW GROUP BY OBSOLETE_FLAG'),
		TOP_BOM_COST_COMPONENTS AS ( 
QUESTION 'What are the most expensive components across all BOMs?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT COMPONENT_DESC, SUM(COMPONENT_COST) AS TOTAL_COST FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_BOM_EXPLOSION GROUP BY COMPONENT_DESC ORDER BY TOTAL_COST DESC LIMIT 10'),
		SUPPLIER_QUALITY_RANKING AS ( 
QUESTION 'How do suppliers rank by quality score?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT SUPPLIER_NAME, ROUND(AVG(QUALITY_SCORE), 1) AS AVG_QUALITY, ROUND(AVG(DEFECT_RATE_PCT), 2) AS AVG_DEFECT_RATE, ROUND(AVG(ON_TIME_DELIVERY_PCT), 1) AS AVG_OTD FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_SUPPLIER_QUALITY GROUP BY SUPPLIER_NAME ORDER BY AVG_QUALITY DESC'),
		PROJECTS_OVER_BUDGET AS ( 
QUESTION 'Which projects are over budget?' 
VERIFIED_AT 1774984280
VERIFIED_BY '(source=existing_sv)'
ONBOARDING_QUESTION false
SQL 'SELECT DISTINCT PROJECT_NAME, PROJECT_STATUS, PLANNED_COST, ACTUAL_COST, BUDGET_VARIANCE_PCT, COMPLETION_PCT FROM SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.DT_PROJECT_STATUS WHERE BUDGET_VARIANCE_PCT > 0 ORDER BY BUDGET_VARIANCE_PCT DESC')
	);
