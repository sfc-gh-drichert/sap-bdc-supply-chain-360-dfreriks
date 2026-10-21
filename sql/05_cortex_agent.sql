-- =====================================================================
-- Cortex Agent — SAP_SC360_ANALYST_AGENT
-- Account-level agent for Snowflake Intelligence. Uses the
-- cortex_analyst_text_to_sql tool over the SAP_SUPPLY_CHAIN_360 semantic view.
-- Prereqs: 04_semantic_view.sql + SNOWFLAKE.CORTEX_USER on the executing role.
-- =====================================================================

CREATE OR REPLACE AGENT SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SC360_ANALYST_AGENT
WITH PROFILE='{"display_name":"SAP Supply Chain 360 Analyst","color":"blue"}'
COMMENT='Cortex Agent for SAP Supply Chain 360 natural language analytics. Answers questions about manufacturing KPIs, production orders, inventory, delivery performance, supplier quality, BOM costs, and project status using the SAP_SUPPLY_CHAIN_360 semantic view.'
FROM SPECIFICATION $$
{
  "models": {
    "orchestration": "auto"
  },
  "orchestration": {
    "budget": {
      "seconds": 60,
      "tokens": 32000
    }
  },
  "instructions": {
    "response": "You are an SAP Supply Chain analytics expert. Answer questions about  manufacturing KPIs, production yield, inventory levels, delivery performance,  supplier quality, bill of materials costs, and project budget status. Provide  clear, concise answers with the key metric values highlighted. When trends are  relevant, describe direction (improving/declining). Always include the time  period when answering trend questions.\n",
    "orchestration": "For any question about OEE, cycle time, throughput, scrap rate,  or plant-level manufacturing KPIs, use the Analyst tool. For production order  yield, scrap, or cycle time by material, use the Analyst tool. For inventory  stock levels, values, or days-of-inventory, use the Analyst tool. For on-time  delivery rates or delay analysis, use the Analyst tool. For supplier quality  scores or defect rates, use the Analyst tool. For bill of materials component  costs, use the Analyst tool. For project budget variance or completion status,  use the Analyst tool. For customer order OTIF, late orders, late cause or late cost, use the Analyst tool (ORDER_FULFILLMENT). For operating rate, capacity loss tree or whether equipment or components is the binding constraint, use the Analyst tool (OPERATING_RATE). For tool failure risk, anomalies, outages or repair cost, use the Analyst tool (EQUIPMENT_HEALTH, EQUIPMENT_OUTAGE). For component shortages, days of cover or supplier lead time, use the Analyst tool (COMPONENT_COVER). When explaining a late order, trace cause -> units lost -> ship slip -> cost.\n",
    "sample_questions": [
      {
        "question": "What is the monthly OEE trend by plant?"
      },
      {
        "question": "What is the production yield rate by product?"
      },
      {
        "question": "Which work centers have the highest utilization and may be bottlenecks?"
      },
      {
        "question": "What is the overall on-time delivery rate?"
      },
      {
        "question": "What is the breakdown of inventory items and value by obsolete status?"
      },
      {
        "question": "What are the most expensive components across all BOMs?"
      },
      {
        "question": "How do suppliers rank by quality score?"
      },
      {
        "question": "Which projects are over budget?"
      },
      {
        "question": "What is driving late customer orders and what does it cost?"
      },
      {
        "question": "Which tools have the highest failure risk right now?"
      },
      {
        "question": "Which components are below supplier lead time on cover?"
      }
    ]
  },
  "tools": [
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "SAP_SC360_Analyst",
        "description": "Converts natural language questions into SQL queries against the  SAP Supply Chain 360 semantic view. Covers manufacturing KPIs (OEE, cycle  time, throughput, scrap), production orders, bill of materials, work center  utilization, inventory management, delivery performance, supplier quality,  project status, geographic supply chain flows, customer order fulfillment (OTIF, late cause and cost), operating-rate loss tree, equipment health and outages, and component days of cover.\n"
      }
    }
  ],
  "skills": [],
  "tool_resources": {
    "SAP_SC360_Analyst": {
      "semantic_view": "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SUPPLY_CHAIN_360"
    }
  }
}
$$;
