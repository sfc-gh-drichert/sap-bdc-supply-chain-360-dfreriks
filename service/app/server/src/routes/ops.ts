// Operations extension: fulfillment & constraints, equipment health, component
// cover, serial digital thread — plus "Ask Cortex", which grounds
// SNOWFLAKE.CORTEX.COMPLETE in live SQL facts for the analysis on screen.
//
// Ask Cortex runs as a background job (POST returns a job id, the client polls)
// so a 20-40s LLM call never blocks a request or times out a proxy.
import { Router, type Request, type Response } from "express";
import crypto from "node:crypto";
import { runQuery } from "../services/snowflake.js";

const router = Router();
const DB = process.env.SC_DB_PREFIX ?? "APP_DATA";
// In the Native App the bundled plant master sits beside the DT_ views in APP_DATA.
const PLANT_TABLE = process.env.SC_PLANT_TABLE ?? "APP_DATA.A_PLANT";
// Model availability varies by account/region and names get retired, so try a list in order.
// CORTEX_MODEL may be a single model or a comma-separated list.
const MODELS = (process.env.CORTEX_MODEL ?? "claude-sonnet-4-5,claude-3-7-sonnet,llama3.3-70b,mistral-large2")
  .split(",").map((m) => m.trim()).filter(Boolean);
const MODEL_UNAVAILABLE = /unknown model|not available|unavailable|not supported|does not exist/i;

// Plant filter by name (matches the sidebar). Bound, never interpolated.
function plantFilter(req: Request, col = "PLANT_NAME"): { sql: string; binds: string[] } {
  const raw = typeof req.query.plants === "string" ? req.query.plants : "";
  const plants = raw.split(",").map((p) => p.trim()).filter(Boolean);
  if (!plants.length) return { sql: "1=1", binds: [] };
  return { sql: `${col} IN (${plants.map(() => "?").join(",")})`, binds: plants };
}

function send(fn: (req: Request) => Promise<unknown>) {
  return async (req: Request, res: Response) => {
    try {
      res.json(await fn(req));
    } catch (err) {
      console.error(req.path, err);
      res.status(500).json({ error: String(err) });
    }
  };
}

// ---------------------------------------------------------------- fulfillment
export async function fulfillmentData(req: Request) {
  const f = plantFilter(req);
  const w = `WHERE ${f.sql}`;
  const [kpi, byCause, byPlant, trend, orders, oprate] = await Promise.all([
    runQuery(`SELECT COUNT(*) AS orders, COUNT_IF(OTIF) AS otif_orders,
                     ROUND(100 * COUNT_IF(OTIF) / NULLIF(COUNT(*), 0), 1) AS otif_pct,
                     COUNT_IF(NOT ON_TIME) AS late_orders, SUM(LATE_COST_USD) AS late_cost_usd,
                     SUM(IFF(NOT ON_TIME, NET_VALUE_USD, 0)) AS late_value_usd,
                     COUNT_IF(ORDER_STATUS = 'Open - at risk') AS open_at_risk,
                     ROUND(AVG(IFF(DELAY_DAYS > 0, DELAY_DAYS, NULL)), 1) AS avg_delay_days
                FROM ${DB}.DT_ORDER_FULFILLMENT ${w}`, f.binds),
    runQuery(`SELECT LATE_CAUSE, LATE_CAUSE_LABEL, COUNT(*) AS orders, SUM(LATE_COST_USD) AS late_cost_usd,
                     SUM(DELAY_DAYS) AS delay_days
                FROM ${DB}.DT_ORDER_FULFILLMENT ${w} AND LATE_CAUSE <> 'ON_TIME'
               GROUP BY 1, 2 ORDER BY late_cost_usd DESC`, f.binds),
    runQuery(`SELECT PLANT_NAME, COUNT(*) AS orders, ROUND(100 * COUNT_IF(OTIF) / COUNT(*), 1) AS otif_pct,
                     SUM(LATE_COST_USD) AS late_cost_usd,
                     SUM(IFF(LATE_CAUSE = 'EQUIPMENT', LATE_COST_USD, 0)) AS equipment_cost,
                     SUM(IFF(LATE_CAUSE = 'MATERIAL_SHORTAGE', LATE_COST_USD, 0)) AS material_cost
                FROM ${DB}.DT_ORDER_FULFILLMENT ${w} GROUP BY 1 ORDER BY 1`, f.binds),
    runQuery(`SELECT SHIP_MONTH, ROUND(100 * COUNT_IF(OTIF) / COUNT(*), 1) AS otif_pct,
                     SUM(LATE_COST_USD) AS late_cost_usd
                FROM ${DB}.DT_ORDER_FULFILLMENT ${w} GROUP BY 1 ORDER BY 1`, f.binds),
    runQuery(`SELECT SALES_ORDER, SOLD_TO, MATERIAL_DESC, PLANT_NAME, ORDER_QTY, NET_VALUE_USD,
                     REQUESTED_SHIP_DATE, ACTUAL_SHIP_DATE, DELAY_DAYS, LATE_CAUSE_LABEL, LATE_COST_USD, ORDER_STATUS
                FROM ${DB}.DT_ORDER_FULFILLMENT ${w} AND NOT ON_TIME
               ORDER BY LATE_COST_USD DESC LIMIT 60`, f.binds),
    runQuery(`SELECT PLANT_NAME, SUM(NAMEPLATE_UNITS) AS nameplate, SUM(PLANNED_DOWNTIME_UNITS) AS planned,
                     SUM(EQUIPMENT_LOSS_UNITS) AS equipment, SUM(MATERIAL_SHORTAGE_UNITS) AS material,
                     SUM(PERFORMANCE_LOSS_UNITS) AS performance, SUM(PRODUCED_UNITS) AS produced,
                     ROUND(100 * SUM(PRODUCED_UNITS) / SUM(NAMEPLATE_UNITS), 1) AS operating_rate_pct,
                     IFF(SUM(EQUIPMENT_LOSS_UNITS) >= SUM(MATERIAL_SHORTAGE_UNITS), 'Equipment', 'Components') AS binding_constraint
                FROM ${DB}.DT_OPERATING_RATE ${w} GROUP BY 1 ORDER BY operating_rate_pct`, f.binds),
  ]);
  return { kpi: kpi[0] ?? {}, byCause, byPlant, trend, orders, oprate };
}
router.get("/api/fulfillment", send(fulfillmentData));

// ---------------------------------------------------------------- equipment
export async function equipmentData(req: Request) {
  const f = plantFilter(req);
  const w = `WHERE ${f.sql}`;
  const [latest, outages, trend] = await Promise.all([
    runQuery(`SELECT EQUIPMENT_ID, EQUIPMENT_NAME, EQUIPMENT_TYPE, WORK_CENTER_DESC, PLANT_NAME, CRITICALITY,
                     FAILURE_PROB_48H, ANOMALY_FLAG, VIBRATION_MM_S, TEMPERATURE_C, READING_DATE, REPAIR_COST_PER_HR
                FROM ${DB}.DT_EQUIPMENT_HEALTH ${w}
              QUALIFY ROW_NUMBER() OVER (PARTITION BY EQUIPMENT_ID ORDER BY READING_DATE DESC) = 1
               ORDER BY FAILURE_PROB_48H DESC`, f.binds),
    runQuery(`SELECT OUTAGE_ID, EQUIPMENT_NAME, PLANT_NAME, START_DATE, EVENT_TYPE, DOWNTIME_HRS, ROOT_CAUSE, REPAIR_COST_USD
                FROM ${DB}.DT_EQUIPMENT_OUTAGE ${w} ORDER BY START_DATE DESC`, f.binds),
    // 30-day sensor trend for the five tools with the highest current risk.
    runQuery(`WITH h AS (SELECT * FROM ${DB}.DT_EQUIPMENT_HEALTH ${w}),
                   mx AS (SELECT MAX(READING_DATE) AS d FROM h),
                   top5 AS (SELECT EQUIPMENT_ID FROM h, mx WHERE READING_DATE = mx.d
                             ORDER BY FAILURE_PROB_48H DESC LIMIT 5)
              SELECT h.EQUIPMENT_ID, h.EQUIPMENT_NAME, h.READING_DATE, h.VIBRATION_MM_S, h.TEMPERATURE_C, h.FAILURE_PROB_48H
                FROM h JOIN top5 USING (EQUIPMENT_ID), mx
               WHERE h.READING_DATE >= DATEADD('day', -30, mx.d)
               ORDER BY 1, 3`, f.binds),
  ]);
  // Value at risk next 48h: P(failure) x 38h typical outage x (repair rate + lost margin/hr).
  const varRows = latest.map((e: any) => {
    const exposure = 38 * (Number(e.repair_cost_per_hr) + 9500);
    return { ...e, value_at_risk_usd: Math.round(Number(e.failure_prob_48h) * exposure) };
  });
  return {
    latest: varRows,
    outages,
    trend,
    kpi: {
      high_risk: varRows.filter((e: any) => e.failure_prob_48h >= 0.3).length,
      anomalies: varRows.filter((e: any) => e.anomaly_flag).length,
      value_at_risk_usd: varRows.reduce((s: number, e: any) => s + e.value_at_risk_usd, 0),
      downtime_hrs: outages.reduce((s: number, o: any) => s + Number(o.downtime_hrs), 0),
      repair_cost_usd: outages.reduce((s: number, o: any) => s + Number(o.repair_cost_usd), 0),
    },
  };
}
router.get("/api/equipment", send(equipmentData));

// ---------------------------------------------------------------- components
export async function componentsData(req: Request) {
  const f = plantFilter(req);
  const [cover, lots] = await Promise.all([
    runQuery(`SELECT PLANT_NAME, COMPONENT_MATERIAL, COMPONENT_DESC, SUPPLIER_NAME, ON_HAND_QTY, DAILY_USAGE,
                     DAYS_OF_COVER, SUPPLIER_LEAD_TIME_DAYS, OPEN_PO_QTY, STATUS, COVER_BELOW_LEAD_TIME
                FROM ${DB}.DT_COMPONENT_COVER WHERE ${f.sql} ORDER BY DAYS_OF_COVER`, f.binds),
    runQuery(`SELECT SUPPLIER_NAME, COUNT(DISTINCT LOT_ID) AS lots,
                     COUNT(DISTINCT IFF(INSPECTION_RESULT <> 'Accepted', LOT_ID, NULL)) AS deviating_lots,
                     COUNT(DISTINCT SERIAL_NO) AS serials,
                     COUNT(DISTINCT IFF(FINAL_TEST_RESULT <> 'PASS', SERIAL_NO, NULL)) AS serials_not_first_pass
                FROM ${DB}.DT_SERIAL_GENEALOGY GROUP BY 1 ORDER BY deviating_lots DESC`),
  ]);
  return { cover, lots };
}
router.get("/api/components", send(componentsData));

// ---------------------------------------------------------------- digital thread
router.get("/api/thread/serials", send(async (req) => {
  const f = plantFilter(req, "p.PLANT_NAME");
  return runQuery(`SELECT g.SERIAL_NO, g.MATERIAL, ANY_VALUE(g.SOLD_TO) AS sold_to, ANY_VALUE(p.PLANT_NAME) AS plant_name,
                          ANY_VALUE(g.FINAL_TEST_RESULT) AS final_test_result,
                          COUNT_IF(g.INSPECTION_RESULT <> 'Accepted') AS deviating_components
                     FROM ${DB}.DT_SERIAL_GENEALOGY g JOIN ${PLANT_TABLE} p ON p.PLANT = g.PLANT
                    WHERE ${f.sql}
                    GROUP BY 1, 2 ORDER BY deviating_components DESC, 1 LIMIT 120`, f.binds);
}));

export async function threadData(serial: string) {
  const rows = await runQuery(`SELECT * FROM ${DB}.DT_SERIAL_GENEALOGY WHERE SERIAL_NO = ? ORDER BY COMPONENT_MATERIAL`, [serial]);
  if (!rows.length) return null;
  const order = await runQuery(`SELECT SALES_ORDER, SOLD_TO, PLANT_NAME, REQUESTED_SHIP_DATE, ACTUAL_SHIP_DATE, DELAY_DAYS,
                                       LATE_CAUSE_LABEL, LATE_COST_USD
                                  FROM ${DB}.DT_ORDER_FULFILLMENT WHERE SALES_ORDER = ?`, [rows[0].sales_order as string]);
  return { serial, components: rows, order: order[0] ?? null };
}
router.get("/api/thread/:serial", send(async (req) => threadData(String(req.params.serial))));

// ================================================================ Ask Cortex
// Each topic is a set of SQL "facts" the model must treat as authoritative.
type Facts = (args: Record<string, string>) => Promise<Record<string, unknown>>;
const T = (sql: string, binds: string[] = []) => runQuery(sql, binds);

const TOPICS: Record<string, { title: string; facts: Facts }> = {
  overview: { title: "executive supply chain overview", facts: async () => ({
    plant_kpis: await T(`SELECT PLANT_NAME, ROUND(AVG(OEE_PCT),1) oee, ROUND(AVG(SCRAP_RATE_PCT),2) scrap, ROUND(AVG(ON_TIME_DELIVERY_PCT),1) otd FROM ${DB}.DT_MANUFACTURING_KPI GROUP BY 1`),
    fulfillment: (await T(`SELECT ROUND(100*COUNT_IF(OTIF)/COUNT(*),1) otif_pct, SUM(LATE_COST_USD) late_cost FROM ${DB}.DT_ORDER_FULFILLMENT`))[0],
    top_equipment_risk: await T(`SELECT EQUIPMENT_NAME, PLANT_NAME, FAILURE_PROB_48H FROM ${DB}.DT_EQUIPMENT_HEALTH QUALIFY ROW_NUMBER() OVER (PARTITION BY EQUIPMENT_ID ORDER BY READING_DATE DESC)=1 ORDER BY 3 DESC LIMIT 3`),
  }) },
  production: { title: "production orders, yield and scrap", facts: async () => ({
    by_material: await T(`SELECT MATERIAL_DESC, PLANT_NAME, SUM(PLANNED_QTY) planned, SUM(YIELD_QTY) yield, SUM(SCRAP_QTY) scrap, ROUND(AVG(CYCLE_TIME_DAYS),1) cycle_days FROM ${DB}.DT_PRODUCTION_ORDER_360 GROUP BY 1,2 ORDER BY scrap DESC`),
    oee_by_plant_month: await T(`SELECT PLANT_NAME, PERIOD_DATE, OEE_PCT, THROUGHPUT FROM ${DB}.DT_MANUFACTURING_KPI ORDER BY 1,2`),
  }) },
  bom: { title: "bill of materials cost structure", facts: async () => ({
    bom: await T(`SELECT PARENT_MATERIAL, COMPONENT_DESC, COMPONENT_QTY, COMPONENT_COST, COMPONENT_QTY*COMPONENT_COST ext_cost FROM ${DB}.DT_BOM_EXPLOSION WHERE BOM_LEVEL=0 ORDER BY 1, ext_cost DESC`),
    component_cover_critical: await T(`SELECT PLANT_NAME, COMPONENT_DESC, DAYS_OF_COVER, SUPPLIER_LEAD_TIME_DAYS FROM ${DB}.DT_COMPONENT_COVER WHERE STATUS='Critical'`),
  }) },
  inventory: { title: "inventory, days of inventory and obsolescence", facts: async () => ({
    by_plant: await T(`SELECT PLANT_NAME, COUNT(*) items, SUM(STOCK_VALUE) value, ROUND(AVG(DAYS_OF_INVENTORY),0) avg_doi, COUNT_IF(OBSOLETE_FLAG='Y') obsolete FROM ${DB}.DT_INVENTORY_OVERVIEW GROUP BY 1`),
    slowest: await T(`SELECT MATERIAL_DESC, PLANT_NAME, STOCK_VALUE, DAYS_OF_INVENTORY, OBSOLETE_FLAG FROM ${DB}.DT_INVENTORY_OVERVIEW ORDER BY DAYS_OF_INVENTORY DESC LIMIT 8`),
    component_cover: await T(`SELECT STATUS, COUNT(*) n FROM ${DB}.DT_COMPONENT_COVER GROUP BY 1`),
  }) },
  logistics: { title: "outbound delivery performance", facts: async () => ({
    by_shipping_point: await T(`SELECT SHIPPING_POINT_DESC, COUNT(*) deliveries, ROUND(100*COUNT_IF(ON_TIME_FLAG='Y')/COUNT(*),1) otd, ROUND(AVG(DELAY_DAYS),1) avg_delay FROM ${DB}.DT_DELIVERY_PERFORMANCE GROUP BY 1`),
    late_cause_cost: await T(`SELECT LATE_CAUSE_LABEL, COUNT(*) orders, SUM(LATE_COST_USD) cost FROM ${DB}.DT_ORDER_FULFILLMENT WHERE NOT ON_TIME GROUP BY 1 ORDER BY 3 DESC`),
  }) },
  workcenter: { title: "work center utilization and bottlenecks", facts: async () => ({
    utilization: await T(`SELECT * FROM ${DB}.DT_WORK_CENTER_UTILIZATION ORDER BY 1 LIMIT 90`),
    equipment_risk: await T(`SELECT WORK_CENTER_DESC, PLANT_NAME, EQUIPMENT_NAME, FAILURE_PROB_48H FROM ${DB}.DT_EQUIPMENT_HEALTH QUALIFY ROW_NUMBER() OVER (PARTITION BY EQUIPMENT_ID ORDER BY READING_DATE DESC)=1 ORDER BY 4 DESC LIMIT 6`),
  }) },
  projects: { title: "capital projects budget and schedule", facts: async () => ({
    projects: await T(`SELECT * FROM ${DB}.DT_PROJECT_STATUS LIMIT 40`),
  }) },
  supplychain: { title: "supply chain network flows", facts: async () => ({
    geo: await T(`SELECT * FROM ${DB}.DT_SUPPLY_CHAIN_GEO LIMIT 40`),
    supplier_quality: await T(`SELECT SUPPLIER_NAME, ROUND(AVG(QUALITY_SCORE),1) q, ROUND(AVG(DEFECT_RATE_PCT),2) defect, ROUND(AVG(ON_TIME_DELIVERY_PCT),1) otd FROM ${DB}.DT_SUPPLIER_QUALITY GROUP BY 1`),
  }) },
  forecasting: { title: "demand and KPI trends", facts: async () => ({
    kpi_trend: await T(`SELECT PERIOD_DATE, ROUND(AVG(OEE_PCT),1) oee, SUM(THROUGHPUT) throughput, ROUND(AVG(ON_TIME_DELIVERY_PCT),1) otd FROM ${DB}.DT_MANUFACTURING_KPI GROUP BY 1 ORDER BY 1`),
    order_trend: await T(`SELECT SHIP_MONTH, COUNT(*) orders, SUM(NET_VALUE_USD) value FROM ${DB}.DT_ORDER_FULFILLMENT GROUP BY 1 ORDER BY 1`),
  }) },
  fulfillment: { title: "order fulfillment, OTIF, late-order causes and late cost", facts: async () => ({
    kpi: (await T(`SELECT COUNT(*) orders, ROUND(100*COUNT_IF(OTIF)/COUNT(*),1) otif_pct, SUM(LATE_COST_USD) late_cost FROM ${DB}.DT_ORDER_FULFILLMENT`))[0],
    by_cause: await T(`SELECT LATE_CAUSE_LABEL, COUNT(*) orders, SUM(LATE_COST_USD) cost FROM ${DB}.DT_ORDER_FULFILLMENT WHERE NOT ON_TIME GROUP BY 1 ORDER BY 3 DESC`),
    by_plant: await T(`SELECT PLANT_NAME, ROUND(100*COUNT_IF(OTIF)/COUNT(*),1) otif, SUM(LATE_COST_USD) cost FROM ${DB}.DT_ORDER_FULFILLMENT GROUP BY 1 ORDER BY 3 DESC`),
    loss_tree: await T(`SELECT PLANT_NAME, SUM(NAMEPLATE_UNITS) nameplate, SUM(EQUIPMENT_LOSS_UNITS) equipment, SUM(MATERIAL_SHORTAGE_UNITS) material, SUM(PERFORMANCE_LOSS_UNITS) performance, SUM(PRODUCED_UNITS) produced FROM ${DB}.DT_OPERATING_RATE GROUP BY 1`),
  }) },
  constraint: { title: "binding constraint at a plant (equipment vs components)", facts: async (a) => ({
    loss_tree_by_month: await T(`SELECT PERIOD_DATE, NAMEPLATE_UNITS, EQUIPMENT_LOSS_UNITS, MATERIAL_SHORTAGE_UNITS, PERFORMANCE_LOSS_UNITS, PRODUCED_UNITS, OPERATING_RATE_PCT FROM ${DB}.DT_OPERATING_RATE WHERE PLANT_NAME=? ORDER BY 1`, [a.plant]),
    outages: await T(`SELECT EQUIPMENT_NAME, START_DATE, DOWNTIME_HRS, ROOT_CAUSE FROM ${DB}.DT_EQUIPMENT_OUTAGE WHERE PLANT_NAME=? ORDER BY START_DATE DESC`, [a.plant]),
    critical_components: await T(`SELECT COMPONENT_DESC, SUPPLIER_NAME, DAYS_OF_COVER, SUPPLIER_LEAD_TIME_DAYS FROM ${DB}.DT_COMPONENT_COVER WHERE PLANT_NAME=? AND STATUS<>'OK'`, [a.plant]),
    late_orders: await T(`SELECT LATE_CAUSE_LABEL, COUNT(*) n, SUM(LATE_COST_USD) cost FROM ${DB}.DT_ORDER_FULFILLMENT WHERE PLANT_NAME=? AND NOT ON_TIME GROUP BY 1`, [a.plant]),
  }) },
  order: { title: "why a specific customer order is late", facts: async (a) => {
    const o = (await T(`SELECT * FROM ${DB}.DT_ORDER_FULFILLMENT WHERE SALES_ORDER=?`, [a.order]))[0];
    if (!o) return { error: "order not found" };
    const day = new Date(o.requested_ship_date as string).toISOString().slice(0, 10);
    return {
      order: o,
      plant_month_loss_tree: await T(`SELECT * FROM ${DB}.DT_OPERATING_RATE WHERE PLANT=? AND PERIOD_DATE=DATE_TRUNC('month', ?::DATE)`, [String(o.plant), day]),
      plant_outages_near_date: await T(`SELECT EQUIPMENT_NAME, START_DATE, DOWNTIME_HRS, ROOT_CAUSE FROM ${DB}.DT_EQUIPMENT_OUTAGE WHERE PLANT=? AND START_DATE BETWEEN DATEADD('day',-30,?::DATE) AND ?::DATE`, [String(o.plant), day, day]),
      component_cover_for_system: await T(`SELECT c.COMPONENT_DESC, c.DAYS_OF_COVER, c.SUPPLIER_LEAD_TIME_DAYS, c.STATUS FROM ${DB}.DT_COMPONENT_COVER c JOIN ${DB}.DT_BOM_EXPLOSION b ON b.COMPONENT_MATERIAL=c.COMPONENT_MATERIAL WHERE b.PARENT_MATERIAL=? AND c.PLANT=?`, [String(o.material), String(o.plant)]),
    };
  } },
  equipment: { title: "equipment health, failure risk and downtime cost", facts: async () => ({
    latest_risk: await T(`SELECT EQUIPMENT_NAME, WORK_CENTER_DESC, PLANT_NAME, CRITICALITY, FAILURE_PROB_48H, ANOMALY_FLAG, VIBRATION_MM_S, TEMPERATURE_C FROM ${DB}.DT_EQUIPMENT_HEALTH QUALIFY ROW_NUMBER() OVER (PARTITION BY EQUIPMENT_ID ORDER BY READING_DATE DESC)=1 ORDER BY FAILURE_PROB_48H DESC LIMIT 10`),
    vibration_10d: await T(`SELECT EQUIPMENT_NAME, READING_DATE, VIBRATION_MM_S, FAILURE_PROB_48H FROM ${DB}.DT_EQUIPMENT_HEALTH WHERE EQUIPMENT_ID IN ('EQ-LIT2-1','EQ-ASM4-1') AND READING_DATE >= DATEADD('day',-10,(SELECT MAX(READING_DATE) FROM ${DB}.DT_EQUIPMENT_HEALTH)) ORDER BY 1,2`),
    outages: await T(`SELECT EQUIPMENT_NAME, PLANT_NAME, START_DATE, EVENT_TYPE, DOWNTIME_HRS, ROOT_CAUSE, REPAIR_COST_USD FROM ${DB}.DT_EQUIPMENT_OUTAGE ORDER BY START_DATE DESC LIMIT 15`),
  }) },
  components: { title: "component availability, supplier lots and quality", facts: async () => ({
    cover: await T(`SELECT PLANT_NAME, COMPONENT_DESC, SUPPLIER_NAME, DAYS_OF_COVER, SUPPLIER_LEAD_TIME_DAYS, OPEN_PO_QTY, STATUS FROM ${DB}.DT_COMPONENT_COVER WHERE STATUS<>'OK' ORDER BY DAYS_OF_COVER`),
    supplier_lot_quality: await T(`SELECT SUPPLIER_NAME, COUNT(DISTINCT LOT_ID) lots, COUNT(DISTINCT IFF(INSPECTION_RESULT<>'Accepted',LOT_ID,NULL)) deviating, COUNT(DISTINCT IFF(FINAL_TEST_RESULT<>'PASS',SERIAL_NO,NULL)) serials_reworked_or_failed, COUNT(DISTINCT SERIAL_NO) serials FROM ${DB}.DT_SERIAL_GENEALOGY GROUP BY 1`),
  }) },
  serial: { title: "digital thread for one system serial number", facts: async (a) => {
    const t = await threadData(a.serial);
    return t ?? { error: "serial not found" };
  } },
};

const SYSTEM = `You are Snowflake Cortex, an SAP supply chain analyst for a semiconductor inspection-equipment
manufacturer (KLA-style wafer inspection and metrology systems) with plants in San Jose, Austin, Dresden,
Singapore and Penang. Data comes from SAP Business Data Cloud data products plus demo enrichment for
orders, equipment health and component lots.

Rules:
- The JSON facts below are authoritative. Cite specific plants, tools, components, suppliers, orders,
  percentages, units and dollars from them. Never invent numbers.
- Lead with the direct answer in one or two sentences, then evidence (a small markdown table when comparing),
  then 2-4 concrete recommended actions.
- Trace causality where possible: equipment outage or component shortage -> units lost -> orders late -> cost.
- If the facts do not contain what is needed, say so plainly.
- Keep it under 300 words.`;

interface Job { status: "running" | "done" | "error"; answer?: string; error?: string; started: number }
const jobs = new Map<string, Job>();

async function runAsk(topic: string, args: Record<string, string>, question: string): Promise<string> {
  const t = TOPICS[topic];
  const facts = await t.facts(args);
  const q = question?.trim() || `Analyse this ${t.title}: what stands out, why, and what should we do?`;
  const prompt = `${SYSTEM}\n\nTopic: ${t.title}\nContext: ${JSON.stringify(args)}\n\nFACTS (JSON):\n${JSON.stringify(facts).slice(0, 60000)}\n\nQuestion: ${q}`;
  let lastErr: unknown;
  for (const model of MODELS) {
    try {
      const rows = await runQuery(`SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS answer`, [model, prompt]);
      return String(rows[0]?.answer ?? "No answer returned.");
    } catch (err) {
      lastErr = err;
      if (!MODEL_UNAVAILABLE.test(String(err))) throw err;
    }
  }
  throw new Error(`No Cortex model available (tried ${MODELS.join(", ")}): ${String(lastErr)}`);
}

router.get("/api/ask-cortex/topics", (_req, res) => {
  res.json(Object.fromEntries(Object.entries(TOPICS).map(([k, v]) => [k, v.title])));
});

router.post("/api/ask-cortex", (req: Request, res: Response) => {
  const { topic, args = {}, question = "" } = req.body ?? {};
  if (typeof topic !== "string" || !TOPICS[topic]) return res.status(400).json({ error: "unknown topic" });
  const clean: Record<string, string> = {};
  for (const [k, v] of Object.entries(args)) if (typeof v === "string" && v.length < 80) clean[k] = v;
  const id = crypto.randomUUID();
  jobs.set(id, { status: "running", started: Date.now() });
  runAsk(topic, clean, String(question).slice(0, 1000))
    .then((answer) => jobs.set(id, { status: "done", answer, started: Date.now() }))
    .catch((err) => jobs.set(id, { status: "error", error: String(err), started: Date.now() }));
  // Prune jobs older than an hour.
  for (const [k, j] of jobs) if (Date.now() - j.started > 3_600_000) jobs.delete(k);
  res.json({ id });
});

router.get("/api/ask-cortex/:id", (req: Request, res: Response) => {
  const j = jobs.get(String(req.params.id));
  if (!j) return res.status(404).json({ error: "job not found" });
  res.json(j);
});

export default router;
