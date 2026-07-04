#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_to_json.py v2.0 — Compile gazzetta.db into 6-container JSON.

Output: data/stories.json with container-grouped stories + tags index.
No flows.json — flow data embedded in story full_json when available.
No RU sync — EN-only (Russian scorched-earth June 2026).

Usage: python3 scripts/db_to_json.py [--data-only]
"""

import json, os, sys, fcntl, sqlite3, shutil, html, re
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("GAZZETTA_DB_PATH", str(PROJECT / "data" / "gazzetta.db")))
DATA = PROJECT / "data"
SITE_DATA = PROJECT / "public" / "data"

CONTAINER_META = {
    "usd_debasement_reserve_diversification": {
        "title": "USD Debasement & Reserve Diversification",
        "subtitle": "USD reserve status erosion, BRICS payment rails, gold repatriation",
        "sort_order": 0,
    },
    "critical_resource_control_infrastructure": {
        "title": "Critical Resource Control & Energy Infrastructure",
        "subtitle": "Crude, natural gas, nuclear, rare earths, grid control, critical minerals",
        "sort_order": 1,
    },
    "supply_chain_resilience_reshoring_defense": {
        "title": "Reshoring, Defense Logistics & Supply-Chain Resilience",
        "subtitle": "Supply chain fragmentation, trade bloc realignment, sanctions rewiring",
        "sort_order": 2,
    },
    "china_geoeconomic_expansion": {
        "title": "China Geoeconomic Expansion & Market Integration",
        "subtitle": "Parallel tech stack, yuan internationalization, BRI, semiconductor independence",
        "sort_order": 3,
    },
    "space_economy_commercialization": {
        "title": "Space Economy & Aerospace",
        "subtitle": "Orbital infrastructure, space mining, satellite internet, GPS alternatives",
        "sort_order": 4,
    },
    "gene_editing_biotech_longevity": {
        "title": "Biotech & Longevity Science",
        "subtitle": "CRISPR therapies, biotech industrialization, healthspan extension",
        "sort_order": 5,
    },
    "tech_convergence_platforms_ai_autonomy": {
        "title": "Enterprise Tech & Artificial Intelligence",
        "subtitle": "AI + quantum + biotech + materials intersections",
        "sort_order": 6,
    },
    "prestige_asset_acquisition_strategic_investment": {
        "title": "Trophy Assets & Sovereign Investment",
        "subtitle": "Sovereign wealth in teams, sports as soft power, capital concentration",
        "sort_order": 7,
    },
    "ai_compute_semiconductor_hegemony": {
        "title": "Semiconductors & Compute Hegemony",
        "subtitle": "Advanced chip manufacturing, foundry limits, export control regimes",
        "sort_order": 8,
    },
    "digital_assets_reserves_onchain_finance": {
        "title": "Digital Assets & Decentralized Capital",
        "subtitle": "Stablecoin settlement, tokenized reserves, sovereign crypto allocations",
        "sort_order": 9,
    },
    "monetary_policy_regime_shift_rate_cycle": {
        "title": "Monetary Policy & Rates",
        "subtitle": "Central bank pivots, yield curve spreads, rate cycle dynamics",
        "sort_order": 10,
    },
    "commodity_supercycle_supply_rebalancing": {
        "title": "Commodities & Physical Supply",
        "subtitle": "Transition metals, underinvestment, physical supply squeezes",
        "sort_order": 11,
    },
}


def compile_containers(conn):
    """Query stories grouped by container, build 6-array output."""
    
    # ── Fetch all stories with tags ──
    rows = conn.execute("""
        SELECT s.id, s.full_json, s.container, s.thesis,
               GROUP_CONCAT(st.tag) as tags_str
        FROM stories s
        LEFT JOIN story_tags st ON s.id = st.story_id
        WHERE s.full_json IS NOT NULL
          AND s.container IS NOT NULL
        GROUP BY s.id
        ORDER BY s.generated_at DESC, s.contradiction_score DESC
    """).fetchall()
    
    # ── Fetch all tags for tags_index ──
    tag_rows = conn.execute("""
        SELECT tag, GROUP_CONCAT(story_id) as story_ids
        FROM story_tags
        GROUP BY tag
        ORDER BY tag
    """).fetchall()
    
    # ── Build container output ──
    containers = {}
    all_stories = []
    
    for cname in CONTAINER_META:
        containers[cname] = {
            "title": CONTAINER_META[cname]["title"],
            "subtitle": CONTAINER_META[cname]["subtitle"],
            "count": 0,
            "stories": [],
        }
    
    for sid, fj_str, container, thesis, tags_str in rows:
        if not fj_str:
            continue
        try:
            story = json.loads(fj_str)
        except json.JSONDecodeError:
            continue
        
        # Ensure story_id is set
        if "story_id" not in story:
            story["story_id"] = sid
        
        # Add container + thesis + source metadata
        story["container"] = container
        story["thesis"] = thesis or ""
        story["tags"] = [t.strip() for t in (tags_str or "").split(",") if t.strip()]
        
        # Unescape HTML entities in headline (&#039; → ')
        if story.get("headline"):
            story["headline"] = html.unescape(story["headline"])
        
        # Extract source name from raw source field, or from headline suffix
        raw_source = story.get("source", "")
        if raw_source and raw_source != "osint":
            # "osint_reuters_business" -> "Reuters Business"
            cleaned = raw_source.replace("osint_", "").replace("_", " ").title()
            story["source_name"] = cleaned
        else:
            # Fallback: extract " - SourceName" from headline suffix
            story["source_name"] = ""
            headline = story.get("headline", "")
            if headline:
                m = re.search(r'\s+[-–—]\s+([A-Z][A-Za-z0-9\s.]+)$', headline)
                if m:
                    story["source_name"] = m.group(1).strip()
        
        # Source URL from story if available (rare)
        story["source_url"] = story.get("source_url", "") or ""
        
        all_stories.append(story)
        
        if container in containers:
            containers[container]["stories"].append(story)
            containers[container]["count"] += 1
    
    # ── Build tags index ──
    tags_index = {}
    for tag, story_ids_str in tag_rows:
        tags_index[tag] = [s.strip() for s in story_ids_str.split(",") if s.strip()]
    
    # ── Atomic write output ──
    generated_at = datetime.now(timezone.utc).isoformat()
    doc = {
        "generated_at": generated_at,
        "generated_by": "db_to_json.py v2.0",
        "containers": dict(sorted(containers.items(), 
                                  key=lambda x: CONTAINER_META[x[0]]["sort_order"])),
        "all_stories": all_stories,
        "tags_index": tags_index,
        "total_stories": len(all_stories),
    }
    
    out_path = DATA / "stories.json"
    tmp_path = DATA / "stories.tmp.json"
    
    # Write to temp file
    with open(tmp_path, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    
    # Validate: re-read and verify structure
    with open(tmp_path, "r") as f:
        validated = json.load(f)
    
    required_keys = ["generated_at", "containers", "all_stories", "total_stories"]
    for key in required_keys:
        if key not in validated:
            raise ValueError(f"VALIDATION FAILED: missing key '{key}' in stories.tmp.json")
    
    if not isinstance(validated.get("all_stories"), list):
        raise ValueError("VALIDATION FAILED: all_stories is not a list")
    
    # Atomic rename (same filesystem = instant, no partial read possible)
    os.replace(tmp_path, out_path)
    
    for cname, cdata in containers.items():
        print(f"  {cname:30s} {cdata['count']:4d} stories")
    print(f"  ✓ stories.json — {len(all_stories)} total, {len(tags_index)} tags")
    
    return len(all_stories)


def main():
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.")
        sys.exit(1)
    
    data_only = "--data-only" in sys.argv
    
    # ── File locking (prevent concurrent runs) ──
    lock_path = DB_PATH.with_suffix(".lock")
    lock_fd = open(str(lock_path), "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("WARNING: Another pipeline instance is running. Exiting.")
        sys.exit(0)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    
    try:
        print("Compiling gazzetta.db → JSON (v2.0 — 6 containers)...")
        story_count = compile_containers(conn)
        
        # ── Sync to public/data/ for deployment ──
        if not data_only:
            os.makedirs(str(SITE_DATA), exist_ok=True)
            src = DATA / "stories.json"
            dst = SITE_DATA / "stories.json"
            if src.exists():
                dst.write_text(src.read_text())
                print(f"  ✓ public/data/stories.json synced")
        
        print(f"\n  DB → JSON compiled: {story_count} stories")
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
