#!/usr/bin/env python3
"""Build the SAP Supply Chain 360 presales deck.

Ten slides for an SE to drop into their own deck. Screenshots come from the
narrated walkthrough, cropped to remove the browser chrome — the raw frames show
a personal bookmarks bar and a localhost URL, neither of which belongs in front
of a customer.

    python3 tools/build_presales_deck.py
"""

import json
import pathlib
import subprocess

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

REPO = pathlib.Path(__file__).resolve().parent.parent
KIT = pathlib.Path.home() / "Documents" / "SAP" / "Supply_Chain_360_Presales_Kit"
VIDEO = pathlib.Path.home() / "Documents" / "SAP" / "SAP_Supply_Chain_360_Demo.mp4"
SHOTS = REPO / "tools" / ".presales_shots"

NAVY = RGBColor(0x1B, 0x3A, 0x57)
BLUE = RGBColor(0x29, 0xB5, 0xE8)
GREY = RGBColor(0x5A, 0x6A, 0x7A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC0, 0x28, 0x28)
GREEN = RGBColor(0x1B, 0x7F, 0x4B)
AMBER = RGBColor(0xB4, 0x6A, 0x00)
LIGHT = RGBColor(0xEE, 0xF4, 0xF8)

W, H = Inches(13.333), Inches(7.5)

# Screens come from the narrated walkthrough, which the shared video builder
# renders at a 1600x1000 app viewport with a 132px caption band below it — so
# a crop to APP_H drops the caption and there is no browser chrome to strip.
# Frames are taken partway into a named segment via the builder's timeline, so
# a re-recording with different pacing still lands on the right screen.
APP_H = 1000
TIMELINE = pathlib.Path("/tmp/sc_demo_video/timeline.json")
FRAMES = {                       # name -> (segment id, fraction into the segment)
    "ontology": ("09_sc_ontology", 0.6),
    "objects": ("06_lineage", 0.6),
}
# The video asks its Cortex Analyst question straight away, so the suggestion
# chip grid is never on screen for long. It is shot from the running app instead.
CHIPS_APP = "http://localhost:5174/"
CHIPS_BOX = (280, 120, 1576, 420)    # chip grid, in 1600x1000 viewport pixels

APP_PAGES = [
    "Executive Overview", "Production Planning", "Bill of Materials",
    "Inventory & Warehouse", "Logistics & Delivery", "Fulfillment & Constraints",
    "Equipment Health", "Components & Digital Thread", "Work Center & Capacity",
    "Project Management", "Supply Chain Map", "Supply Chain Ontology",
    "SC Optimization", "SC Forecasting", "BDC Sources & Lineage", "Cortex Analyst",
]

REGIONS = [
    ("North America", "PUBLIC.AWS_US_WEST_2"),
    ("EMEA", "AWS_EU_CENTRAL_1"),
    ("APAC", "PUBLIC.AWS_AP_SOUTHEAST_2"),
]


def frame_time(seg_id, frac):
    segs = {x["id"]: x for x in json.loads(TIMELINE.read_text())["segments"]}
    return round(segs[seg_id]["start"] + frac * segs[seg_id]["secs"], 2)


def shoot_chips(path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": APP_H})
        pg.goto(CHIPS_APP, wait_until="domcontentloaded")
        pg.get_by_role("button", name="Cortex Analyst", exact=True).click()
        pg.get_by_text("What is the monthly OEE trend by plant?").first.wait_for(timeout=30000)
        pg.mouse.move(5, APP_H - 5)    # keep the pointer out of the shot
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(path), clip=dict(x=CHIPS_BOX[0], y=CHIPS_BOX[1],
                      width=CHIPS_BOX[2] - CHIPS_BOX[0], height=CHIPS_BOX[3] - CHIPS_BOX[1]))
        b.close()


def grab_frames():
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = {}
    stale = VIDEO.stat().st_mtime
    for name, (seg, frac) in FRAMES.items():
        path = SHOTS / f"{name}.png"
        if not path.exists() or path.stat().st_mtime < stale:
            raw = SHOTS / f"{name}_raw.png"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", str(frame_time(seg, frac)), "-i", str(VIDEO),
                 "-frames:v", "1", str(raw), "-y"],
                check=True,
            )
            im = Image.open(raw)
            im.crop((0, 0, im.width, min(APP_H, im.height))).save(path)
            raw.unlink()
        out[name] = path
    chips = SHOTS / "chips.png"
    if not chips.exists() or chips.stat().st_mtime < stale:
        shoot_chips(chips)
    out["chips"] = chips
    return out


# ------------------------------------------------------------------ primitives


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, spacing=1.0):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, item in enumerate(runs):
        body_, size, bold, color = item[:4]
        after = item[4] if len(item) > 4 else 6
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(after)
        r = p.add_run()
        r.text = body_
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = "Arial"
    return tb


def header(slide, kicker, title):
    rect(slide, 0, 0, W, Inches(0.09), BLUE)
    text(slide, Inches(0.6), Inches(0.42), Inches(12.1), Inches(1.1),
         [(kicker.upper(), 10, True, BLUE, 3), (title, 27, True, NAVY, 0)])


def footer(slide, note):
    text(slide, Inches(0.6), Inches(7.03), Inches(12.1), Inches(0.3),
         [(note, 8, False, GREY, 0)])


def picture_fit(slide, path, x, y, w, h):
    im = Image.open(path)
    ar = im.width / im.height
    if ar > w / h:
        pw, ph = w, int(w / ar)
    else:
        ph, pw = h, int(h * ar)
    slide.shapes.add_picture(str(path), int(x + (w - pw) / 2), int(y + (h - ph) / 2), pw, ph)


def kpi_column(slide, items, x=Inches(8.55), y=Inches(1.8), w=Inches(4.18), h=Inches(1.15)):
    gap = Inches(0.17)
    for i, (label, value, color) in enumerate(items):
        cy = y + i * (h + gap)
        rect(slide, x, cy, w, h, LIGHT)
        rect(slide, x, cy, Inches(0.05), h, color)
        text(slide, x + Inches(0.24), cy + Inches(0.2), w - Inches(0.44), h - Inches(0.4),
             [(label.upper(), 8.5, True, GREY, 4), (value, 19, True, color, 0)])


def bullets(slide, x, y, w, items, size=13, gap=11):
    text(slide, x, y, w, Inches(4.0),
         [("—  " + b, size, False, NAVY, gap) for b in items], spacing=1.12)


# ---------------------------------------------------------------------- slides


def s01_title(prs):
    s = blank(prs)
    rect(s, 0, 0, W, H, NAVY)
    rect(s, Inches(0.6), Inches(2.5), Inches(0.06), Inches(1.9), BLUE)
    text(s, Inches(0.95), Inches(2.45), Inches(11.4), Inches(2.2), [
        ("SAP + SNOWFLAKE  ·  PRESALES KIT", 11, True, BLUE, 12),
        ("SAP Supply Chain 360", 44, True, WHITE, 8),
        ("SAP supply-chain analytics on Snowflake — zero ETL, zero copy", 17, False, LIGHT, 0),
    ])
    text(s, Inches(0.95), Inches(5.5), Inches(11.4), Inches(1.2), [
        ("21 SAP BDC objects · 15 gold tables · governed semantic view · Cortex Agent · 16-page app",
         12, True, BLUE, 6),
        ("Installs as a self-contained Native App in North America, EMEA and APAC", 11, False, LIGHT, 0),
    ])


def s02_problem(prs):
    s = blank(prs)
    header(s, "The problem", "The data exists. Getting to it is the project.")
    bullets(s, Inches(0.6), Inches(1.95), Inches(6.0), [
        "SAP customers already hold the supply-chain data they need — production "
        "orders, capacity, inventory, supplier quality. It sits inside S/4HANA.",
        "Getting it somewhere analytics and AI can reach usually means a pipeline "
        "project: extract, land, model, reconcile, then maintain it forever.",
        "Worse, the metrics get rebuilt on the way out. OEE recalculated in a "
        "warehouse is no longer SAP's OEE, and now two numbers disagree.",
        "So the question stops being 'what does the data say' and becomes 'whose "
        "number is right' — which is a meeting, not an answer.",
    ])
    rect(s, Inches(7.0), Inches(1.95), Inches(5.73), Inches(3.9), LIGHT)
    text(s, Inches(7.35), Inches(2.25), Inches(5.03), Inches(3.3), [
        ("WHAT CHANGES WITH BDC", 9, True, BLUE, 14),
        ("No pipeline.", 15, True, NAVY, 4),
        ("BDC shares governed data products into Snowflake with zero copy. There is "
         "nothing to build and nothing to break.", 12, False, NAVY, 12),
        ("No re-derived metrics.", 15, True, NAVY, 4),
        ("OEE, yield, on-time delivery and inventory turns arrive as SAP defines "
         "them. One definition, not two.", 12, False, NAVY, 12),
        ("No data movement.", 15, True, NAVY, 4),
        ("The analytics, the semantic layer, the AI and the app all run on the data "
         "where it lands.", 12, False, NAVY, 0),
    ])
    footer(s, "SAP BDC is included in a RISE with SAP subscription at no additional cost.")


def s03_architecture(prs):
    s = blank(prs)
    header(s, "How it works", "One medallion stack, entirely inside Snowflake")
    layers = [
        ("L0", "Bronze — SAP BDC Standard Data Products",
         "21 A_* objects across 16 domain schemas, shared zero-copy and treated as immutable"),
        ("L2", "Gold — SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS",
         "9 dynamic tables joining and aggregating L0 into analytics-ready shapes"),
        ("SRV", "Serving — APP_REF",
         "17 stable app-facing views, decoupling the app from the physical objects"),
        ("SEM", "Semantic — SAP_SUPPLY_CHAIN_360",
         "55 facts · 107 dimensions · 12 verified queries · 3 relationships"),
        ("AI", "Agent — SAP_SC360_ANALYST_AGENT",
         "Cortex Agent in Snowflake Intelligence, and Cortex Analyst inside the app"),
        ("APP", "Native App — 16 pages on SPCS",
         "React + Express, 18 tables bundled into SHARED_DATA, nothing to configure"),
    ]
    y = Inches(1.9)
    for tag, name, detail in layers:
        rect(s, Inches(0.6), y, Inches(0.85), Inches(0.74), BLUE)
        text(s, Inches(0.6), y + Inches(0.23), Inches(0.85), Inches(0.3),
             [(tag, 12, True, WHITE, 0)], align=PP_ALIGN.CENTER)
        rect(s, Inches(1.45), y, Inches(11.28), Inches(0.74), LIGHT)
        text(s, Inches(1.68), y + Inches(0.11), Inches(10.9), Inches(0.58), [
            (name, 12, True, NAVY, 2),
            (detail, 10, False, GREY, 0),
        ])
        y += Inches(0.86)
    footer(s, "Object counts verified against the account on 21 September 2026, not taken from design docs.")


def s04_objects(prs, shots):
    s = blank(prs)
    header(s, "It is real", "Nine gold tables you can point at in Snowsight")
    picture_fit(s, shots["objects"], Inches(0.6), Inches(1.72), Inches(7.6), Inches(5.2))
    kpi_column(s, [
        ("SAP BDC source objects", "21 across 16 schemas", NAVY),
        ("Gold dynamic tables", "9", NAVY),
        ("Serving views (APP_REF)", "11", NAVY),
        ("Semantic view", "55 facts · 107 dims", NAVY),
    ])
    footer(s, "The architect's slide: the objects exist, they are named, and the semantic view is governed.")


def s05_app(prs, shots):
    s = blank(prs)
    header(s, "The app", "Thirteen pages, and nothing to set up")
    picture_fit(s, shots["ontology"], Inches(0.6), Inches(1.72), Inches(7.6), Inches(5.2))
    col = APP_PAGES
    half = 7
    text(s, Inches(8.5), Inches(1.85), Inches(2.3), Inches(5.0),
         [(f"·  {p}", 10.5, False, NAVY, 7) for p in col[:half]], spacing=1.1)
    text(s, Inches(10.85), Inches(1.85), Inches(2.3), Inches(5.0),
         [(f"·  {p}", 10.5, False, NAVY, 7) for p in col[half:]], spacing=1.1)
    text(s, Inches(8.5), Inches(5.35), Inches(4.23), Inches(1.4), [
        ("Plant filters apply across every page. The data is bundled into the app, "
         "so there are no grants, no warehouse to size and no load step.",
         10.5, False, GREY, 0),
    ], spacing=1.12)
    footer(s, "Shown: the Supply Chain Ontology page. The Supply Chain Map renders supplier, plant and customer flows on a globe.")


def s06_agent(prs, shots):
    s = blank(prs)
    header(s, "The AI", "Plain-English questions, governed SQL underneath")
    text(s, Inches(0.6), Inches(1.8), Inches(12.13), Inches(0.5), [
        ("The eight questions the Cortex Analyst page ships with — each one backed by a "
         "verified query on the semantic view:", 13, False, NAVY, 0)])

    picture_fit(s, shots["chips"], Inches(0.9), Inches(2.45), Inches(11.5), Inches(2.5))

    rect(s, Inches(0.6), Inches(5.3), Inches(5.96), Inches(1.5), LIGHT)
    text(s, Inches(0.9), Inches(5.55), Inches(5.4), Inches(1.1), [
        ("WHY IT IS DEFENSIBLE", 9, True, BLUE, 8),
        ("The generated SQL expands on screen, and the agent is constrained to the "
         "semantic model — which is the entire reason for having one.",
         11.5, False, NAVY, 0)], spacing=1.12)

    rect(s, Inches(6.77), Inches(5.3), Inches(5.96), Inches(1.5), LIGHT)
    text(s, Inches(7.07), Inches(5.55), Inches(5.4), Inches(1.1), [
        ("ONE THING TO AVOID", 9, True, RED, 8),
        ("Do not ask time-relative questions. The data window ends September 2025, so "
         "\u201cthis quarter\u201d returns nothing and the tool looks broken when it is not.",
         11.5, False, NAVY, 0)], spacing=1.12)
    footer(s, "Ask one live rather than replaying a canned answer — the point is that it was not rehearsed.")


def s07_routes(prs):
    """Two-route comparison. Deliberately no screenshot: the only frame available
    of the Snowflake Intelligence chat is a mid-load state, and a half-rendered
    answer undersells the thing it is meant to prove."""
    s = blank(prs)
    header(s, "The other route", "Same agent, no app required")
    text(s, Inches(0.6), Inches(1.8), Inches(12.13), Inches(0.5), [
        ("The app is the fastest demo, but it is not the only one. Both routes run on "
         "the same semantic view and the same agent.", 13, False, NAVY, 0)])

    cards = [
        ("Native App", "The default",
         ["Install the listing, open it, present",
          "Data bundled in — no grants, no warehouse sizing",
          "16 pages plus Cortex Analyst and Ask Cortex",
          "Best for business, ops and exec audiences"],
         BLUE),
        ("Data share + Snowflake Intelligence", "For architects",
         ["Mount 9 dynamic tables, the semantic view and the agent",
          "Ask from Snowsight — no container, no app",
          "Show the objects, the grants and the generated SQL",
          "Best when the question is 'how does this actually work'"],
         NAVY),
    ]
    x = Inches(0.6)
    for title_, who, points, accent in cards:
        rect(s, x, Inches(2.5), Inches(5.96), Inches(3.5), LIGHT)
        rect(s, x, Inches(2.5), Inches(5.96), Inches(0.06), accent)
        text(s, x + Inches(0.3), Inches(2.75), Inches(5.36), Inches(0.7), [
            (title_, 16, True, NAVY, 2), (who.upper(), 9, True, accent, 0)])
        text(s, x + Inches(0.3), Inches(3.75), Inches(5.36), Inches(2.0),
             [(f"—  {pt}", 11.5, False, NAVY, 10) for pt in points], spacing=1.12)
        x += Inches(6.17)

    text(s, Inches(0.6), Inches(6.25), Inches(12.13), Inches(0.7), [
        ("Both are internal organization listings, visible to all internal accounts. "
         "Find them in Snowsight under Data Products, then Marketplace, filtered to your organization.",
         12, False, GREY, 0)], spacing=1.12)
    footer(s, "Agent: SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SC360_ANALYST_AGENT · Semantic view: SAP_SUPPLY_CHAIN_DF_V1.ANALYTICS.SAP_SUPPLY_CHAIN_360")


def s08_regions(prs):
    s = blank(prs)
    header(s, "Distribution", "One definition, three governed installs")
    text(s, Inches(0.6), Inches(1.8), Inches(12.1), Inches(0.5), [
        ("Published as a region-scoped organization listing. Each region is its own "
         "governed deployment — not one global instance.", 13, False, NAVY, 0)])
    y = Inches(2.5)
    for name, region in REGIONS:
        rect(s, Inches(0.6), y, Inches(12.13), Inches(1.0), LIGHT)
        rect(s, Inches(0.6), y, Inches(0.05), Inches(1.0), BLUE)
        text(s, Inches(1.0), y + Inches(0.16), Inches(4.0), Inches(0.7), [
            (name, 16, True, NAVY, 2), (region, 10.5, False, GREY, 0)])
        text(s, Inches(5.4), y + Inches(0.3), Inches(7.0), Inches(0.5), [
            ("Native App listing + data share listing, installable from the internal Marketplace",
             11.5, False, NAVY, 0)])
        y += Inches(1.12)
    text(s, Inches(0.6), Inches(6.1), Inches(12.13), Inches(0.9), [
        ("Data residency holds because each install is local to its region. There is no "
         "cross-region querying — do not imply otherwise, and note that consumers get "
         "their own URL when they install rather than sharing the reference deployment.",
         12, False, NAVY, 0)], spacing=1.12)
    footer(s, "Listings: ORGDATACLOUD$INTERNAL$SUPPLY_CHAIN_360_ORG (app) · ORGDATACLOUD$INTERNAL$SAP_BDC_SUPPLY_CHAIN_360 (share)")


def s09_real(prs):
    s = blank(prs)
    header(s, "Credibility", "What is real, and what is a demo dataset")
    text(s, Inches(0.6), Inches(1.75), Inches(12.13), Inches(0.4), [
        ("Say this before you are asked. The architecture is production-shaped; the rows are not.",
         13, True, GREY, 0)])
    rows = [
        ("Medallion architecture and SQL", "Real — this is the deliverable", GREEN),
        ("Semantic view (55 facts, 107 dimensions)", "Real — verified in the account", GREEN),
        ("Cortex Agent and its 12 verified queries", "Real — same objects a customer would run", GREEN),
        ("Native App, 16 pages, 3 regions", "Real — deployed and installable today", GREEN),
        ("SAP BDC structure (21 objects, 16 schemas)", "Real structure, modelled on actual BDC products", AMBER),
        ("The rows themselves", "Synthetic — Apex Manufacturing, 5 plants, 398 L0 rows", AMBER),
        ("OTIF, equipment and component cover (OPS_EXT)", "Generated enrichment keyed to SAP master data", AMBER),
        ("Data window", "Fixed: January to September 2025 — NOT current", RED),
        ("Live SAP connection", "None. This is a reference dataset, not a feed", RED),
    ]
    y = Inches(2.35)
    for i, (element, status, color) in enumerate(rows):
        rect(s, Inches(0.6), y, Inches(12.13), Inches(0.48), LIGHT if i % 2 == 0 else WHITE)
        rect(s, Inches(0.6), y, Inches(0.05), Inches(0.48), color)
        text(s, Inches(0.85), y + Inches(0.11), Inches(5.3), Inches(0.3), [(element, 12, True, NAVY, 0)])
        text(s, Inches(6.3), y + Inches(0.11), Inches(6.3), Inches(0.3), [(status, 12, False, color, 0)])
        y += Inches(0.5)
    footer(s, "Both marketplace listings state the data window and are set to refresh_rate STATIC rather than implying a live feed.")


def s10_ask(prs):
    s = blank(prs)
    rect(s, 0, 0, W, H, NAVY)
    rect(s, Inches(0.6), Inches(0.8), Inches(0.06), Inches(1.0), BLUE)
    text(s, Inches(0.95), Inches(0.75), Inches(11.5), Inches(1.2), [
        ("WHERE TO TAKE IT", 11, True, BLUE, 10),
        ("Four options, in order of effort", 32, True, WHITE, 0)])
    opts = [
        ("Demo it", "Install the Native App listing in your region and present. Nothing to build."),
        ("Show the architecture", "Run sql/02 to sql/05 in your own account and demo through Snowflake Intelligence — no app needed."),
        ("Point it at customer data", "Swap the L0 layer for the customer's own BDC data products. The gold tables, semantic view and agent above it still apply."),
        ("Pair it with the Ontology", "Supply Chain 360 reports on the supply chain; the Ontology kit models what happens when it breaks. Strong together."),
    ]
    y = Inches(2.3)
    for i, (head_, detail) in enumerate(opts):
        rect(s, Inches(0.95), y, Inches(11.4), Inches(0.92), RGBColor(0x24, 0x4A, 0x6B))
        text(s, Inches(1.25), y + Inches(0.14), Inches(10.8), Inches(0.7), [
            (f"{i + 1}.  {head_}", 14, True, BLUE, 3), (detail, 11.5, False, LIGHT, 0)])
        y += Inches(1.02)
    text(s, Inches(0.95), Inches(6.55), Inches(11.4), Inches(0.7), [
        ("Full kit on SAP Partnership Compass · start with 03_SE_Quick_Start.docx", 12, True, WHITE, 4),
        ("github.com/sfc-gh-dfreriks/sap-bdc-supply-chain-360 · contact Dave Freriks", 10.5, False, LIGHT, 0)])


def main():
    shots = grab_frames()
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    s01_title(prs)
    s02_problem(prs)
    s03_architecture(prs)
    s04_objects(prs, shots)
    s05_app(prs, shots)
    s06_agent(prs, shots)
    s07_routes(prs)
    s08_regions(prs)
    s09_real(prs)
    s10_ask(prs)

    out = KIT / "00_Presales_Overview.pptx"
    prs.save(out)
    print(f"wrote {out}  (10 slides)")


if __name__ == "__main__":
    main()
