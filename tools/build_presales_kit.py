#!/usr/bin/env python3
"""Build the SAP Supply Chain 360 presales kit documents.

Mirrors the Supply Chain Ontology kit so the two read as a set:

    00_START_HERE.docx              what is in the kit and which file to open
    03_SE_Quick_Start.docx          positioning, demo path, objections
    05_Architecture_and_Install.docx the medallion stack and how to stand it up
    06_Setup_and_Access.docx        the three region deployments and how to get in

Every figure below was verified against the account on 2026-10-08 rather than
copied from existing docs, because several of those disagreed with each other:

    16 domain schemas, 21 A_* L0 objects, 398 L0 rows   INFORMATION_SCHEMA
    15 L2 dynamic tables (9 BDC + 6 OPS_EXT), 17 APP_REF views  INFORMATION_SCHEMA
    14 tables, 55 facts, 107 dimensions, 12 verified queries  DESCRIBE SEMANTIC VIEW
    16 app pages                                        client/src/components/Sidebar.tsx
    data window Jan 2025 - Sep 2025                     MIN/MAX over the fact tables

    python3 tools/build_presales_kit.py
"""

import pathlib
import shutil
import subprocess
import sys

from docx import Document
from docx.shared import Pt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from docx_kit import (  # noqa: E402
    GREY,
    LIGHT_HEX,
    RED,
    SAP_NAVY,
    SNOW_BLUE,
    body,
    bullet,
    callout,
    h1,
    h2,
    setup_page,
    table,
)

KIT = pathlib.Path.home() / "Documents" / "SAP" / "Supply_Chain_360_Presales_Kit"
DATE = "8 October 2026"

REPO_URL = "https://github.com/sfc-gh-dfreriks/sap-bdc-supply-chain-360"
VIDEO_SRC = pathlib.Path.home() / "Documents" / "SAP" / "SAP_Supply_Chain_360_Demo.mp4"
APP_LISTING = "ORGDATACLOUD$INTERNAL$SUPPLY_CHAIN_360_ORG"
SHARE_LISTING = "ORGDATACLOUD$INTERNAL$SAP_BDC_SUPPLY_CHAIN_360"

REGIONS = [
    ("North America", "PUBLIC.AWS_US_WEST_2", "https://arzht4-sfsenorthamerica-dfreriks-aws1-w2.snowflakecomputing.app"),
    ("EMEA", "AWS_EU_CENTRAL_1", "https://ea3ite-sfseeurope-dfreriks-eu-demo.snowflakecomputing.app"),
    ("APAC", "PUBLIC.AWS_AP_SOUTHEAST_2", "https://eahbbd-sfseapac-sap-data-product-demo.snowflakecomputing.app"),
]

PAGES = [
    ("Executive Overview", "Plant KPIs, OEE, on-time delivery"),
    ("Production Planning", "Orders, planned vs confirmed, yield and scrap"),
    ("Bill of Materials", "Multi-level BOM with component costs"),
    ("Inventory & Warehouse", "Stock positions, days of inventory, obsolescence"),
    ("Logistics & Delivery", "Outbound deliveries, on-time %, delay analysis"),
    ("Fulfillment & Constraints", "OTIF, late cost by root cause, operating-rate loss tree (OPS_EXT)"),
    ("Equipment Health", "48-hour failure risk, vibration trends, outages and repair cost (OPS_EXT)"),
    ("Components & Digital Thread", "Days of cover vs lead time; serial-to-lot genealogy (OPS_EXT)"),
    ("Work Center & Capacity", "Capacity vs used hours — where the bottlenecks are"),
    ("Project Management", "Budget variance and completion %"),
    ("Supply Chain Map", "Supplier, plant and customer flows on a globe"),
    ("Supply Chain Ontology", "The class model behind the network"),
    ("SC Optimization", "Reroute and mitigation exploration"),
    ("SC Forecasting", "Forward-looking demand and supply signals"),
    ("BDC Sources & Lineage", "The SAP BDC products behind each page, with row counts"),
    ("Cortex Analyst", "Natural-language questions over the semantic view"),
]

# The eight suggestion chips on the app's Cortex Analyst page, read off the UI.
# Each corresponds to one of the twelve AI_VERIFIED_QUERY entries in the semantic view.
AGENT_QUESTIONS = [
    "What is the monthly OEE trend by plant?",
    "Which work centers have the highest utilization?",
    "What is the overall on-time delivery rate?",
    "How do suppliers rank by quality score?",
    "What is the production yield rate by product?",
    "Which projects are over budget?",
    "What percentage of inventory is obsolete?",
    "What are the most expensive BOM components?",
]

DATA_WINDOW = "January 2025 to September 2025"


def kit_video(src):
    """Copy the walkthrough into the kit under a name carrying its real length,
    replacing any older cut, and return that name for the file table."""
    secs = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
        check=True, capture_output=True, text=True).stdout)
    name = f"04_Walkthrough_Narrated_{int(secs // 60)}min{int(secs % 60):02d}.mp4"
    KIT.mkdir(parents=True, exist_ok=True)
    for old in KIT.glob("04_Walkthrough_Narrated_*.mp4"):
        if old.name != name:
            old.unlink()
    if not (KIT / name).exists() or (KIT / name).stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, KIT / name)
    return name


def title_block(doc, title, subtitle, strap):
    for text_, size, bold, color, after in (
        (title, 20, True, SAP_NAVY, 2),
        (subtitle, 11.5, False, SNOW_BLUE, 2),
        (strap, 9, False, GREY, 14),
    ):
        p = doc.add_paragraph()
        r = p.add_run(text_)
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        p.paragraph_format.space_after = Pt(after)


def stale_data_callout(doc):
    callout(
        doc,
        "Read this before you demo",
        f"The bundled data covers {DATA_WINDOW}. Shown today, the newest point on "
        "every trend is about a year old. Nobody usually notices unless you draw "
        "attention to a date axis — but if asked, say it plainly: this is a fixed "
        "reference snapshot built to show the BDC pattern, not a live SAP feed. "
        "Do not claim the data is current.",
    )


# ---------------------------------------------------------------- START HERE


def build_start_here():
    doc = Document()
    setup_page(doc)
    title_block(
        doc,
        "SAP Supply Chain 360",
        "Presales kit — start here",
        f"SAP Partnership Compass  ·  {DATE}  ·  Owner: Dave Freriks",
    )

    body(
        doc,
        "Supply Chain 360 is the production-analytics half of the SAP supply-chain "
        "story: what SAP S/4HANA data looks like once it reaches Snowflake through "
        "SAP Business Data Cloud, with a governed semantic layer and a Cortex Agent "
        "on top. It installs as a self-contained Native App — nothing to configure, "
        "no data to load.",
    )

    callout(
        doc,
        "Fastest path to a demo",
        f"Install the Native App listing {APP_LISTING} from the internal Marketplace "
        "in your nearest region, open it, and you have a 16-page dashboard with its "
        "own data already inside. See 06_Setup_and_Access.",
    )

    stale_data_callout(doc)

    h1(doc, "What this demonstrates")
    body(
        doc,
        "Zero ETL and zero copy, with SAP business context preserved. SAP BDC shares "
        "governed supply-chain data products into Snowflake; the medallion layers, "
        "the semantic view, the agent and the app are all built on top without "
        "extracting anything. One definition ships to three regions, each as its own "
        "governed install.",
    )

    table(
        doc,
        ["The demo in eight numbers", "Value"],
        [
            ["SAP BDC source objects", "21 A_* objects across 16 domain schemas"],
            ["Analytics layer", "9 dynamic tables in ANALYTICS"],
            ["Serving layer", "11 APP_REF views (the 9 plus A_PLANT and A_SUPPLY_CHAIN_NODES)"],
            ["Semantic view", "14 tables, 55 facts, 107 dimensions, 12 verified queries"],
            ["Agent", "SAP_SC360_ANALYST_AGENT, in Snowflake Intelligence"],
            ["App", "16 pages, React + Express on Snowpark Container Services"],
            ["Regions live", "North America, EMEA, APAC"],
            ["Data window", f"{DATA_WINDOW} — a fixed snapshot, 398 L0 rows"],
        ],
        widths=[2.3, 4.4],
    )

    h1(doc, "Which file to open")
    table(
        doc,
        ["File", "Use it when", "Read time"],
        [
            [
                "03_SE_Quick_Start.docx",
                "You are demoing this week. Positioning, a ten-minute path, the "
                "agent questions that work, discovery questions, objections. Start here.",
                "10 min",
            ],
            [
                "01_Demo_Guide_Deck.pptx",
                "You want the existing customer-facing deck with presenter notes.",
                "15 slides",
            ],
            [
                "00_Presales_Overview.pptx",
                "You need slides of your own. Ten slides: problem, architecture, the "
                "app, the agent, regions, and the ask. Drop into your deck.",
                "10 slides",
            ],
            [
                VIDEO_NAME,
                "You want to see it run before running it, or need an async asset.",
                "9m40s",
            ],
            [
                "05_Architecture_and_Install.docx",
                "An architect is in the room, or you are standing it up yourself. "
                "The medallion stack, every object, and the build order.",
                "reference",
            ],
            [
                "06_Setup_and_Access.docx",
                "You need access: the three region URLs, the two listings, and what "
                "to install for which kind of demo.",
                "5 min",
            ],
            [
                "07_Background/",
                "The longer June deck, the project guide, and a 14-minute combined "
                "video covering Supply Chain 360 and the Ontology as one narrative.",
                "optional",
            ],
        ],
        widths=[2.0, 3.9, 0.8],
    )

    h1(doc, "Two ways to demo, and when to pick each")
    table(
        doc,
        ["Route", "What you get", "Pick it when"],
        [
            [
                "Native App listing",
                "The 16-page dashboard with data bundled in. No setup, no grants, "
                "no warehouse to size.",
                "Default. Any business audience.",
            ],
            [
                "Data share + Snowflake Intelligence",
                "The 9 dynamic tables, the semantic view and the agent in your own "
                "account, queried from Snowsight.",
                "An architect wants to see the objects, the SQL and the governance.",
            ],
        ],
        widths=[1.7, 3.1, 1.9],
    )

    h1(doc, "The companion kit")
    body(
        doc,
        "Supply Chain Ontology is the other half and a separate kit. It models "
        "disruption — if a plant goes offline, what fails downstream and how much can "
        "be protected. Supply Chain 360 reports on the supply chain; the Ontology "
        "reasons about it. Lead with 360 for an analytics conversation and with the "
        "Ontology for a resilience one. The combined video in 07_Background presents "
        "both as one narrative.",
    )

    h1(doc, "Support")
    body(doc, f"Source and documentation: {REPO_URL}. Questions: Dave Freriks.")

    out = KIT / "00_START_HERE.docx"
    doc.save(out)
    return out


# --------------------------------------------------------------- QUICK START


def build_quick_start():
    doc = Document()
    setup_page(doc)
    title_block(
        doc,
        "SAP Supply Chain 360",
        "SE quick start",
        f"Ten-minute demo path, agent questions and objection handling  ·  {DATE}",
    )

    body(
        doc,
        "Written to be read once, the day before you demo. It assumes you have not "
        "opened the app before.",
    )

    h1(doc, "Positioning, in three sentences")
    bullet(
        doc,
        "SAP customers have the supply-chain data they need, and it is locked inside "
        "S/4HANA where analytics and AI cannot reach it without a pipeline project.",
    )
    bullet(
        doc,
        "SAP Business Data Cloud shares that data into Snowflake with zero copy and "
        "full business context intact — OEE, yield, on-time delivery, inventory turns "
        "arrive as SAP defines them, not as someone re-derived them in a warehouse.",
    )
    bullet(
        doc,
        "Snowflake then adds the semantic layer, the AI and the app, and distributes "
        "the whole thing as a governed install in any region. No ETL, and nothing "
        "leaves SAP's definition of the truth.",
    )

    h1(doc, "Before you start")
    bullet(
        doc,
        f"Install the Native App ({APP_LISTING}) in your nearest region, or use the "
        "reference deployment URL from 06_Setup_and_Access. Open it once to warm it.",
    )
    bullet(
        doc,
        "Decide which route you are on — bundled Native App or the data share plus "
        "Snowflake Intelligence. The agent questions differ slightly; see below.",
    )
    bullet(
        doc,
        "Check the plant filter. It applies across every page, and a stray "
        "single-plant selection makes the map look empty.",
    )
    bullet(
        doc,
        f"Know the data window: {DATA_WINDOW}. Do not say 'this quarter' or 'today' "
        "about anything on screen.",
    )

    h1(doc, "The ten-minute path")
    table(
        doc,
        ["#", "Page", "Do and say", "Time"],
        [
            [
                "1",
                "—",
                "Open the app cold. Say: nothing was installed, configured or loaded "
                "to get here — the data is already inside. That is the whole point.",
                "1 min",
            ],
            [
                "2",
                "Executive Overview",
                "Plant KPIs, OEE, on-time delivery. Say: these are SAP's own "
                "definitions, not metrics we re-invented in a warehouse.",
                "1 min",
            ],
            [
                "3",
                "Production Planning",
                "Planned vs confirmed vs scrap and yield. Drill one plant.",
                "1 min",
            ],
            [
                "4",
                "Inventory & Warehouse",
                "Days of inventory and obsolescence. Pair it with Logistics if the "
                "room is operations-led.",
                "1 min",
            ],
            [
                "5",
                "Work Center & Capacity",
                "Capacity against used hours — the bottleneck view. This is the page "
                "plant people lean forward for.",
                "1 min",
            ],
            [
                "5b",
                "Fulfillment & Constraints",
                "OTIF 71.7%, $4.4M late cost, component shortage the top cause. Click "
                "Ask Cortex: it names San Jose (59.7% OTIF, $3.2M) from the numbers on "
                "screen. Say these three operations pages run on representative OPS_EXT "
                "data keyed to the SAP master data. Swap in for Work Center if short.",
                "1 min",
            ],
            [
                "6",
                "Supply Chain Map",
                "Supplier to plant to customer flows on the globe. Strongest visual "
                "in the app; do not rush it.",
                "2 min",
            ],
            [
                "7",
                "Cortex Analyst",
                "Ask a real question live (see the list below). Then expand the "
                "generated SQL — governed and explainable, not a black box.",
                "2 min",
            ],
            [
                "8",
                "—",
                "Recap: zero ETL, SAP context preserved, AI-ready, and one definition "
                "installed in three regions as three governed deployments.",
                "1 min",
            ],
        ],
        widths=[0.3, 1.5, 4.2, 0.7],
    )

    h2(doc, "Questions that work on the agent")
    body(
        doc,
        "These are the eight suggestion chips the Cortex Analyst page ships with, and "
        "they line up with eight of the twelve verified queries in the semantic view — so they "
        "are the safe set. Read them off the screen or type your own variation.",
    )
    for q in AGENT_QUESTIONS:
        bullet(doc, q)
    body(
        doc,
        "Ask one live rather than reading a canned answer — the point is that it was "
        "not rehearsed. Avoid anything time-relative ('this quarter', 'last month'): "
        "the data window ends September 2025, so a relative-date question returns "
        "nothing and makes the tool look broken when it is the data that is fixed.",
        italic=True,
    )

    h2(doc, "The closing line")
    callout(
        doc,
        "Say this",
        "Everything you just saw reads SAP data in place — no pipeline, no copy, no "
        "re-derived metrics — and the same definition installs in North America, "
        "EMEA or APAC as its own governed deployment.",
    )

    h1(doc, "What is on each page")
    table(
        doc,
        ["Page", "What it shows"],
        [[name, what] for name, what in PAGES],
        widths=[2.0, 4.7],
    )

    h1(doc, "Discovery questions")
    bullet(doc, "How much of your SAP supply-chain reporting runs on extracts today, and who maintains them?")
    bullet(doc, "When a metric like OEE is questioned, how long does it take to agree whose number is right?")
    bullet(doc, "Are you on RISE with SAP, and is BDC part of that subscription already?")
    bullet(doc, "Who would use natural-language querying — analysts, or the plant and ops teams directly?")
    bullet(doc, "Do you need the same analytics in more than one region, under local governance?")

    h1(doc, "Objections, and what to say")
    table(
        doc,
        ["They say", "You say"],
        [
            [
                "Where does the OTIF and equipment data come from?",
                "Fulfillment, Equipment Health and Components run on OPS_EXT, a "
                "generated enrichment keyed to the SAP plants, work centers, BOM and "
                "suppliers. In a customer build those feeds come from sales orders, "
                "plant maintenance and MES or IoT; the joins to SAP stay the same.",
            ],
            [
                "Is this our data or a demo dataset?",
                f"A demo dataset — a fixed snapshot covering {DATA_WINDOW}, modelled "
                "on real SAP BDC data products and their real structure. The "
                "architecture, semantic layer and agent are exactly what you would "
                "run; only the rows are synthetic.",
            ],
            [
                "How is this different from extracting to a warehouse?",
                "Nothing is extracted. BDC shares the data products into Snowflake "
                "with zero copy, so there is no pipeline to build or break, and SAP's "
                "definitions come with the data rather than being rebuilt downstream.",
            ],
            [
                "What does it cost to run?",
                "The app runs on Snowpark Container Services and the data is already "
                "in Snowflake, so there is no separate ETL tool or duplicate storage. "
                "BDC is included in a RISE subscription at no extra cost.",
            ],
            [
                "Can the agent be wrong?",
                "It generates SQL against a governed semantic view with verified "
                "queries, and you can expand the SQL on screen. It is constrained to "
                "the model, which is exactly why the semantic layer exists.",
            ],
            [
                "Does it work in our region?",
                "It is deployed in North America, EMEA and APAC today. Each is its "
                "own governed install — not one global instance — so data residency "
                "holds. Do not promise cross-region querying; that is not what this is.",
            ],
            [
                "Can we point it at our own SAP data?",
                "Yes, and that is the follow-on. The medallion SQL and the semantic "
                "view are the deliverable; swap the L0 layer for the customer's own "
                "BDC data products and the layers above it still apply.",
            ],
            [
                "Why are the dates a year old?",
                "It is a fixed reference snapshot, not a live feed — say so directly "
                "rather than explaining it away. If currency matters for the "
                "conversation, flag it and we can refresh the window.",
            ],
        ],
        widths=[1.9, 4.8],
    )

    h1(doc, "If it goes wrong")
    bullet(doc, "A page is empty — check the plant filter; it persists across pages.")
    bullet(doc, "The agent returns nothing — you probably asked a time-relative question. Re-ask without the date.")
    bullet(doc, "The app is slow on first open — the container is cold. Open it before the call.")
    bullet(doc, "The map renders blank — it needs WebGL; a remote-desktop session may not have it. Fall back to the video.")

    out = KIT / "03_SE_Quick_Start.docx"
    doc.save(out)
    return out


# ------------------------------------------------- ARCHITECTURE AND INSTALL


def build_architecture():
    doc = Document()
    setup_page(doc)
    title_block(
        doc,
        "SAP Supply Chain 360",
        "Architecture and install",
        f"The medallion stack, every object, and the build order  ·  {DATE}",
    )

    body(
        doc,
        "Everything sits inside Snowflake and reads SAP data through SAP Business "
        "Data Cloud zero-copy shares. No ETL, no extraction, SAP business context "
        "preserved. Object counts below were taken from the account, not from the "
        "design docs.",
    )

    h1(doc, "The stack")
    table(
        doc,
        ["Layer", "Objects", "What it does"],
        [
            [
                "L0 Bronze",
                "21 A_* objects across 16 domain schemas",
                "SAP BDC Standard Data Products, shared zero-copy and treated as "
                "immutable. PLANT, WORK_CENTER, PROJECT, BILL_OF_MATERIAL, "
                "MANUFACTURING_CODES, DELIVERY_MGMT_CONFIG and others.",
            ],
            [
                "L2 Gold",
                "9 dynamic tables in ANALYTICS",
                "Join and aggregate L0 into the shapes the dashboard and semantic "
                "model need.",
            ],
            [
                "Serving",
                "11 views in APP_REF",
                "Stable app-facing views over the 9 dynamic tables plus A_PLANT and "
                "A_SUPPLY_CHAIN_NODES, decoupling the app from physical objects.",
            ],
            [
                "Semantic",
                "SAP_SUPPLY_CHAIN_360",
                "14 tables, 55 facts, 107 dimensions, 12 verified queries and 3 relationships "
                "over the gold layer.",
            ],
            [
                "Agent",
                "SAP_SC360_ANALYST_AGENT",
                "Account-level Cortex Agent in Snowflake Intelligence, and the same "
                "model behind the app's Cortex Analyst page.",
            ],
            [
                "App",
                "16 pages on SPCS",
                "React client and Express server, packaged as a self-contained "
                "Native App with 11 tables bundled into SHARED_DATA.",
            ],
        ],
        widths=[0.9, 1.9, 3.9],
    )

    body(
        doc,
        "Unlike Finance 360, which has an explicit SAP_BDC_L1 silver layer, Supply "
        "Chain 360 collapses L1 into the raw L0 objects — the dynamic tables read "
        "the A_* products directly and APP_REF is the serving layer. Worth knowing "
        "if someone asks why the two projects differ.",
        italic=True,
    )

    h1(doc, "The gold tables")
    table(
        doc,
        ["Dynamic table", "Business content"],
        [
            ["DT_MANUFACTURING_KPI", "Monthly plant KPIs — OEE, scrap rate, throughput, on-time delivery, turns"],
            ["DT_PRODUCTION_ORDER_360", "Production orders — planned, confirmed, scrap, yield, cycle time"],
            ["DT_BOM_EXPLOSION", "Multi-level bill of materials with component costs"],
            ["DT_INVENTORY_OVERVIEW", "Stock positions, days of inventory, turnover, obsolescence"],
            ["DT_DELIVERY_PERFORMANCE", "Outbound deliveries, on-time %, delay analysis"],
            ["DT_WORK_CENTER_UTILIZATION", "Work-center capacity against used hours — bottlenecks"],
            ["DT_PROJECT_STATUS", "Project budget variance and completion %"],
            ["DT_SUPPLY_CHAIN_GEO", "Geographic flows, supplier to plant to customer"],
            ["DT_SUPPLIER_QUALITY", "Supplier defect rates and composite quality scores"],
            ["DT_ORDER_FULFILLMENT *", "Order-level OTIF, root cause of lateness, penalty + expedite cost"],
            ["DT_OPERATING_RATE *", "Monthly loss tree: nameplate to planned, equipment, component, rate loss, produced"],
            ["DT_EQUIPMENT_HEALTH *", "Daily tool vibration, temperature and 48-hour failure probability"],
            ["DT_EQUIPMENT_OUTAGE *", "Outage events, downtime hours, root cause, repair cost"],
            ["DT_COMPONENT_COVER *", "Component days of cover against supplier lead time"],
            ["DT_SERIAL_GENEALOGY *", "Serial to component lot, supplier inspection and final test"],
        ],
        widths=[2.2, 4.5],
    )
    body(
        doc,
        "* OPS_EXT demo enrichment: synthetic rows generated by tools/gen_ops_ext.py "
        "and keyed to the SAP plants, work centers, BOM and suppliers, so they join "
        "to the BDC data. Representative, not customer data — say so when you demo "
        "the three operations pages.",
        italic=True,
    )

    h1(doc, "Build order")
    table(
        doc,
        ["Step", "What to run", "Result"],
        [
            ["1", "sql/02_appref_serving_views.sql", "APP_REF serving views"],
            ["2", "sql/03_l2_analytics_dynamic_tables.sql", "The 9 BDC-sourced ANALYTICS dynamic tables"],
            ["2b", "tools/gen_ops_ext.py, then sql/06_ops_ext_dynamic_tables.sql", "OPS_EXT seed data and its 6 dynamic tables"],
            ["3", "sql/04_semantic_view.sql", "SAP_SUPPLY_CHAIN_360 semantic view"],
            ["4", "sql/05_cortex_agent.sql", "SAP_SC360_ANALYST_AGENT"],
            ["5", "scripts/build_and_push.sh", "Container image for SPCS"],
            ["6", "scripts/migrate_data.py", "Bundle the 18 tables into SHARED_DATA"],
            ["7", "scripts/deploy_native_app.py", "Application package and version"],
            ["8", "scripts/create_org_listing.py", "Region-scoped organization listing"],
        ],
        widths=[0.5, 2.9, 3.3],
    )
    body(
        doc,
        "Run steps 1 to 4 as ACCOUNTADMIN. After step 4 you can already demo through "
        "Snowflake Intelligence without the app at all — useful if you want the "
        "architecture conversation rather than the dashboard.",
    )

    h1(doc, "Refresh behaviour, and a caveat")
    body(
        doc,
        "The fifteen dynamic tables are defined with TARGET_LAG = DOWNSTREAM, which "
        "means they refresh only when something downstream with its own lag demands "
        "it. Nothing downstream currently declares a lag, so in practice they do not "
        "refresh on a schedule.",
    )
    body(
        doc,
        f"That is academic for the demo, because the L0 data is a fixed snapshot "
        f"ending September 2025 — refreshing the dynamic tables would not move any "
        f"date forward. If you point this stack at live BDC data products, set an "
        f"explicit TARGET_LAG on the gold tables rather than relying on DOWNSTREAM.",
    )

    h1(doc, "Security notes")
    bullet(doc, "No credentials are committed. Scripts read key-pair connections from ~/.snowflake/connections.toml by connection name.")
    bullet(doc, ".gitignore excludes *.p8, .env and connections.toml.")
    bullet(doc, "L0 BDC products are read-only zero-copy shares; the medallion only reads from them.")

    out = KIT / "05_Architecture_and_Install.docx"
    doc.save(out)
    return out


# ------------------------------------------------------------- SETUP, ACCESS


def build_setup():
    doc = Document()
    setup_page(doc)
    title_block(
        doc,
        "SAP Supply Chain 360",
        "Setup and access",
        f"Three region deployments, two listings, and what to install  ·  {DATE}",
    )

    h1(doc, "Pick your route")
    table(
        doc,
        ["Route", "Listing", "What you get"],
        [
            [
                "Native App (default)",
                APP_LISTING,
                "The 16-page dashboard with data bundled in. No grants, no warehouse "
                "sizing, no data setup. Region-scoped: install the one for your region.",
            ],
            [
                "Data share",
                SHARE_LISTING,
                "The 9 dynamic tables, the SAP_SUPPLY_CHAIN_360 semantic view and "
                "SAP_SC360_ANALYST_AGENT mounted in your own account, for Snowsight "
                "and Snowflake Intelligence. Available in all regions.",
            ],
        ],
        widths=[1.3, 2.1, 3.3],
    )
    body(
        doc,
        "Both are internal organization listings, visible to all internal accounts. "
        "Find them in Snowsight under Data Products, then Marketplace, filtered to "
        "your organization.",
    )

    h1(doc, "The reference deployment")
    body(
        doc,
        "Already running in three regions. These URLs are the internal reference "
        "install — consumers get their own URL when they install the app themselves.",
    )
    table(
        doc,
        ["Region", "Snowflake region", "App URL"],
        [[name, region, url] for name, region, url in REGIONS],
        widths=[1.1, 1.7, 3.9],
    )
    body(
        doc,
        "Each region is an independent governed install of the same definition. "
        "There is no cross-region querying, and you should not imply there is — "
        "data residency is part of the value here.",
        italic=True,
    )

    h1(doc, "Standing it up yourself")
    table(
        doc,
        ["Step", "Command"],
        [
            ["Clone", f"git clone {REPO_URL}"],
            ["Data platform", "Run sql/02 through sql/05 as ACCOUNTADMIN"],
            ["Then demo via", "Snowsight → AI/ML → Snowflake Intelligence → SAP_SC360_ANALYST_AGENT"],
            ["App (optional)", "scripts/build_and_push.sh → migrate_data.py → deploy_native_app.py"],
        ],
        widths=[1.2, 5.5],
    )
    body(
        doc,
        "Full runbook in docs/INSTALL.md, architecture in "
        "05_Architecture_and_Install.docx.",
    )

    h1(doc, "Snowflake objects")
    table(
        doc,
        ["Object", "Detail"],
        [
            ["Database", "SAP_SUPPLY_CHAIN_DF_V1"],
            ["L0 source", "21 A_* objects across 16 domain schemas, 398 rows total"],
            ["ANALYTICS", "9 dynamic tables, DT_* prefix"],
            ["APP_REF", "11 serving views"],
            ["Semantic view", "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SUPPLY_CHAIN_360"],
            ["Agent", "SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SC360_ANALYST_AGENT"],
            ["Share", "9 dynamic tables + semantic view + agent"],
        ],
        widths=[1.7, 5.0],
    )
    callout(
        doc,
        "Naming",
        "There is exactly one SC360 agent and it lives in ANALYTICS: "
        "SAP_SC360_ANALYST_AGENT. Older deployment notes referenced "
        "SEMANTIC_ENHANCED.SAP_BDC_SUPPLY_360, which does not exist — if you see "
        "that name in a script, it is stale and the grant will fail.",
    )

    h1(doc, "Data currency")
    body(
        doc,
        f"The dataset covers {DATA_WINDOW} and is a fixed synthetic snapshot. Both "
        "marketplace listings state this, and their refresh rate is set to STATIC "
        "rather than implying a live feed. Plan your talk track accordingly and avoid "
        "time-relative claims or agent questions.",
    )

    h1(doc, "Related assets")
    table(
        doc,
        ["Asset", "Where"],
        [
            ["Supply Chain Ontology kit", "The disruption-modelling companion — separate kit on Compass"],
            ["SAP BDC Ontology Explorer", "https://sfc-gh-dfreriks.github.io/sap-bdc-data-products/"],
            ["This kit", "SAP Partnership Compass, Seismic"],
        ],
        widths=[1.9, 4.8],
    )

    h1(doc, "Contact")
    body(doc, "Dave Freriks — for access help, or to scope pointing this at a customer's own BDC data products.")

    out = KIT / "06_Setup_and_Access.docx"
    doc.save(out)
    return out


def main():
    global VIDEO_NAME
    VIDEO_NAME = kit_video(VIDEO_SRC)
    KIT.mkdir(parents=True, exist_ok=True)
    for fn in (build_start_here, build_quick_start, build_architecture, build_setup):
        print(f"wrote {fn()}")


if __name__ == "__main__":
    main()
