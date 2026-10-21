// Shared builder for GET /api/lineage — Supply Chain 360's own BDC sources and
// medallion lineage. `c` holds lower-cased row counts (live COUNT(*) locally,
// APP_DATA.LINEAGE_COUNTS in the Native App).

export const LINEAGE_COUNT_COLUMNS = [
  "PLANT", "WORK_CENTER", "WC_CAPACITY", "MFG_KPI", "MATERIAL_STOCK", "SUPPLIER_QUALITY",
  "SC_FLOWS", "SC_NODES", "BOM_ITEM", "BOM_GROUP", "DELIVERY", "PROD_CONF", "PROD_VERSION",
  "PROJECT", "PROJECT_CONFIG", "PROJECT_WBS", "SALES_BOM", "SHIPPING_POINT", "STORAGE_LOCATION",
  "CHANGE_MASTER", "CHANGE_RECORD", "DT_PROD_ORDER", "DT_MFG_KPI", "DT_BOM", "DT_INVENTORY",
  "DT_DELIVERY", "DT_WC_UTIL", "DT_PROJECT", "DT_SUPPLIER_QUALITY", "DT_SC_GEO",
] as const;

export function buildLineage(c: Record<string, unknown>, database: string) {
  const L0 = "SAP_SUPPLY_CHAIN_DF_V1";
  const p = (sapSystem: string, dataProduct: string, l0Object: string, l1Object: string, rows: unknown, usage: string) =>
    ({ sapSystem, dataProduct, l0Object: `${L0}.${l0Object}`, l1Object, rows, usage });
  return {
    app: "SAP BDC Supply Chain 360",
    database,
    sourceSystems: [
      "SAP S/4HANA Manufacturing (PP) & Logistics (MM / LE)",
      "SAP S/4HANA Project System (PS)",
      "SAP S/4HANA Engineering Change Management",
    ],
    summary:
      "Supply chain master and transactional data is modelled on the SAP BDC Standard Data Products for S/4HANA " +
      "(Plant, Work Center, Bill of Material, Production Order Confirmation, Project, Shipping Point, Storage Location, " +
      "Change Master/Record, …). Each product lands as an A_* object in its own domain schema of SAP_SUPPLY_CHAIN_DF_V1 (L0), " +
      "is curated into dynamic tables and a semantic view in ANALYTICS (L2), and is served to this app through APP_REF " +
      "views (L1) and to the SAP Supply Chain 360 Analyst agent. A supply chain ontology / knowledge graph sits on top.",
    products: [
      p("S/4HANA Manufacturing", "Plant (sap-s4com-Plant-v1)", "PLANT.A_PLANT", "APP_REF.A_PLANT", c.plant, "Plant master, filters & map"),
      p("S/4HANA Manufacturing", "Work Center (sap-s4com-WorkCenter-v1)", "WORK_CENTER.A_WORK_CENTER", "ANALYTICS.DT_WORK_CENTER_UTILIZATION", c.work_center, "Work center master"),
      p("S/4HANA Manufacturing", "Work Center (sap-s4com-WorkCenter-v1)", "WORK_CENTER.A_WORK_CENTER_CAPACITY", "ANALYTICS.DT_WORK_CENTER_UTILIZATION", c.wc_capacity, "Capacity & utilization"),
      p("S/4HANA Manufacturing", "Production Order Confirmation (sap-s4com-ProductionOrderConfirmation-v1)", "PRODUCTION_ORDER_CONFIRM.A_PROD_ORD_CONFIRMATION", "ANALYTICS.DT_PRODUCTION_ORDER_360", c.prod_conf, "Production orders, yield & scrap"),
      p("S/4HANA Manufacturing", "Production Version (sap-s4com-ProductionVersion-v1)", "PRODUCTION_VERSION.A_PRODUCTION_VERSION", "—", c.prod_version, "Production version reference"),
      p("S/4HANA Manufacturing", "Bill Of Material (sap-s4com-BillOfMaterial-v1)", "BILL_OF_MATERIAL.A_BOM_ITEM", "ANALYTICS.DT_BOM_EXPLOSION", c.bom_item, "BOM explosion & component cost"),
      p("S/4HANA Manufacturing", "Bill Of Material Group (sap-s4pce-BillOfMaterialGroup-v1)", "BOM_GROUP.A_BOM_GROUP", "ANALYTICS.DT_BOM_EXPLOSION", c.bom_group, "BOM group headers"),
      p("S/4HANA Sales", "Sales Bill Of Material (sap-s4com-SalesBillOfMaterial-v1)", "SALES_BOM.A_SALES_BOM", "—", c.sales_bom, "Sales BOM reference"),
      p("S/4HANA Logistics", "Delivery Mgmt Configuration Data (sap-s4com-DeliveryMgmtConfigurationData-v1)", "DELIVERY_MGMT_CONFIG.A_DELIVERY", "ANALYTICS.DT_DELIVERY_PERFORMANCE", c.delivery, "Outbound deliveries & on-time"),
      p("S/4HANA Logistics", "Shipping Point (sap-s4com-ShippingPoint-v1)", "SHIPPING_POINT.A_SHIPPING_POINT", "ANALYTICS.DT_DELIVERY_PERFORMANCE", c.shipping_point, "Shipping point master"),
      p("S/4HANA Logistics", "Storage Location (sap-s4com-StorageLocation-v1)", "STORAGE_LOCATION.A_STORAGE_LOCATION", "ANALYTICS.DT_INVENTORY_OVERVIEW", c.storage_location, "Storage location master"),
      p("S/4HANA Project System", "Project (sap-s4pce-Project-v1)", "PROJECT.A_PROJECT", "ANALYTICS.DT_PROJECT_STATUS", c.project, "Project master & budget"),
      p("S/4HANA Project System", "Project Configuration Data (sap-s4pce-ProjectConfigurationData-v1)", "PROJECT_CONFIG_DATA.A_PROJECT_CONFIG", "—", c.project_config, "Project configuration"),
      p("S/4HANA Project System", "Project Network (sap-s4pce-ProjectNetwork-v1)", "PROJECT_NETWORK.A_PROJECT_WBS", "ANALYTICS.DT_PROJECT_STATUS", c.project_wbs, "WBS elements & completion"),
      p("S/4HANA Engineering", "Change Master (sap-s4com-ChangeMaster-v1)", "CHANGE_MASTER.A_CHANGE_MASTER", "—", c.change_master, "Engineering change master"),
      p("S/4HANA Engineering", "Change Record (sap-s4pce-ChangeRecord-v1)", "CHANGE_RECORD.A_CHANGE_RECORD", "—", c.change_record, "Engineering change records"),
      p("Demo extension", "— (no BDC standard product; modelled)", "MANUFACTURING_CODES.A_MANUFACTURING_KPI", "ANALYTICS.DT_MANUFACTURING_KPI", c.mfg_kpi, "OEE, throughput, scrap KPIs"),
      p("Demo extension", "— (no BDC standard product; modelled)", "MANUFACTURING_CODES.A_MATERIAL_STOCK", "ANALYTICS.DT_INVENTORY_OVERVIEW", c.material_stock, "Stock positions"),
      p("Demo extension", "— (no BDC standard product; modelled)", "MANUFACTURING_CODES.A_SUPPLIER_QUALITY", "ANALYTICS.DT_SUPPLIER_QUALITY", c.supplier_quality, "Supplier quality scores"),
      p("Demo extension", "— (no BDC standard product; modelled)", "MANUFACTURING_CODES.A_SUPPLY_CHAIN_FLOWS", "ANALYTICS.DT_SUPPLY_CHAIN_GEO", c.sc_flows, "Material flows (map)"),
      p("Demo extension", "— (no BDC standard product; modelled)", "MANUFACTURING_CODES.A_SUPPLY_CHAIN_NODES", "APP_REF.A_SUPPLY_CHAIN_NODES", c.sc_nodes, "Supply chain nodes (map)"),
    ],
    curated: [
      { object: "ANALYTICS.DT_PRODUCTION_ORDER_360", rows: c.dt_prod_order },
      { object: "ANALYTICS.DT_MANUFACTURING_KPI", rows: c.dt_mfg_kpi },
      { object: "ANALYTICS.DT_BOM_EXPLOSION", rows: c.dt_bom },
      { object: "ANALYTICS.DT_INVENTORY_OVERVIEW", rows: c.dt_inventory },
      { object: "ANALYTICS.DT_DELIVERY_PERFORMANCE", rows: c.dt_delivery },
      { object: "ANALYTICS.DT_WORK_CENTER_UTILIZATION", rows: c.dt_wc_util },
      { object: "ANALYTICS.DT_PROJECT_STATUS", rows: c.dt_project },
      { object: "ANALYTICS.DT_SUPPLIER_QUALITY", rows: c.dt_supplier_quality },
      { object: "ANALYTICS.DT_SUPPLY_CHAIN_GEO", rows: c.dt_sc_geo },
    ],
    layers: [
      { name: "SAP Source Systems", tone: "sap", objects: ["SAP S/4HANA Manufacturing (PP)", "SAP S/4HANA Logistics (MM / LE)", "SAP S/4HANA Project System (PS)", "SAP Engineering Change Mgmt"] },
      { name: "L0 — Bronze (BDC-shaped data products)", tone: "bronze", objects: ["PLANT.A_PLANT", "WORK_CENTER.A_WORK_CENTER(_CAPACITY)", "BILL_OF_MATERIAL.A_BOM_ITEM", "PRODUCTION_ORDER_CONFIRM.A_PROD_ORD_CONFIRMATION", "PROJECT_NETWORK.A_PROJECT_WBS", "MANUFACTURING_CODES.A_*", "+11 more"] },
      { name: "L1 — Silver (APP_REF serving views)", tone: "silver", objects: ["APP_REF.DT_* (9 serving views)", "APP_REF.A_PLANT", "APP_REF.A_SUPPLY_CHAIN_NODES"] },
      { name: "L2 — Gold (Dynamic Tables + Semantic View)", tone: "gold", objects: ["ANALYTICS.DT_PRODUCTION_ORDER_360", "ANALYTICS.DT_MANUFACTURING_KPI", "ANALYTICS.DT_BOM_EXPLOSION", "ANALYTICS.DT_INVENTORY_OVERVIEW", "ANALYTICS.DT_DELIVERY_PERFORMANCE", "+4 more DT_*", "ANALYTICS.SAP_SUPPLY_CHAIN_360 (Semantic View)"] },
      { name: "AI + Application", tone: "ai", objects: ["ANALYTICS.SAP_SC360_ANALYST_AGENT (Cortex Agent)", "ONTOLOGY schema — knowledge graph (see Supply Chain Ontology page)", "SAP BDC Supply Chain 360 (React)"] },
    ],
    note:
      "Honesty note: the L0 objects are modelled BDC-shaped native tables in SAP_SUPPLY_CHAIN_DF_V1 that follow the SAP BDC " +
      "Standard Data Product structures — they are not mounted BDC zero-copy shares in this account. The MANUFACTURING_CODES " +
      "objects (KPIs, stock, supplier quality, flows, nodes) have no BDC standard product and are demo enrichment. There is no " +
      "separate SAP_BDC_L1 passthrough layer; APP_REF serving views play the L1 role.",
  };
}
