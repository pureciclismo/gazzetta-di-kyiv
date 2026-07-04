#!/usr/bin/env python3
"""
build_frontend.py -- Gazzetta di Kyiv Multi-View Dashboard Compiler
Supports two modes:
  1. Next.js Build Mode (Local): Runs npm install && npm run build, copies web/out to public/
  2. Data Compile Mode (VM / Local): Normalizes data, generates stories.json, narratives.json,
     and compiles dossier HTML pages. Does not overwrite the Next.js public/index.html.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Paths ──────────────────────────────────────────────────────────
PROJECT = Path(os.environ.get("GAZZETTA_HOME", "/opt/gazzetta-di-kyiv"))
if not PROJECT.exists():
    # Local fallback
    PROJECT = Path(__file__).resolve().parent.parent

DATA = PROJECT / "data"
PUBLIC = PROJECT / "public"
PUBLIC_DATA = PUBLIC / "data"
TEMPLATES = PROJECT / "templates"
WEB_DIR = PROJECT / "web"

ICON_FALLBACK_MAP = {
    "dollar_decline": "trending_down", "critical_resource_control": "bolt",
    "deglobalization": "public", "china_ascent": "language",
    "space_economy": "rocket_launch", "gene_editing": "biotech",
    "tech_convergence": "memory", "wealthy_sports": "sports_soccer",
    "ai_chips": "memory", "crypto_reserve": "account_balance",
    "rate_cycle": "percent", "commodity_supercycle": "inventory_2",
}

LEGACY_ORDER = [
    "usd_debasement_reserve_diversification",
    "critical_resource_control_infrastructure",
    "supply_chain_resilience_reshoring_defense",
    "china_geoeconomic_expansion",
    "space_economy_commercialization",
    "gene_editing_biotech_longevity",
    "tech_convergence_platforms_ai_autonomy",
    "prestige_asset_acquisition_strategic_investment",
    "ai_compute_semiconductor_hegemony",
    "digital_assets_reserves_onchain_finance",
    "monetary_policy_regime_shift_rate_cycle",
    "commodity_supercycle_supply_rebalancing"
]

def load_json(path):
    with open(path) as f:
        return json.load(f)

def load_narratives_config():
    path = DATA / "narratives.json"
    if not path.exists():
        return {}, list(LEGACY_ORDER)
    try:
        data = load_json(path)
        narratives = data.get("narratives", {})
        ordered = sorted(narratives.keys(),
                        key=lambda nid: (narratives[nid].get("capital_total_usd", 0),
                                        narratives[nid].get("story_count", 0)),
                        reverse=True)
        return narratives, ordered
    except Exception:
        return {}, list(LEGACY_ORDER)

def narrative_phase(gap, count):
    if count < 3: return "EMERGENT", "New signal — limited data"
    if gap >= 80: return "CRITICAL SHIFT", "Extreme divergence — media narrative disconnected from capital reality"
    if gap >= 70: return "ACTIVE DIVERGENCE", "Significant gap — institutional capital actively contradicting consensus"
    if gap >= 50: return "BUILDING TENSION", "Growing friction between media framing and capital positioning"
    return "MATURE/STABLE", "Narrative and capital flows broadly aligned"

def calculate_narrative_status(top_gap, story_count):
    if top_gap >= 70 and story_count > 3:
        return "BREAKING ACCELERATION"
    elif top_gap >= 50:
        return "ACTIVE CONTRADICTION"
    return "SETTLING REGIME"

def build_cft_block(narrative_id, stories, narrative_config):
    mine = [
        s for s in stories
        if narrative_id in (s.get("containers") or [s.get("narrative_id")])
    ]
    if not mine:
        return None

    catalyst = max(mine, key=lambda s: s.get("contradiction_gap", 0) or 0)
    gap = catalyst.get("contradiction_gap", 0) or 0
    if gap < 25:
        return None

    capital = catalyst.get("capital_volume_usd", 0) or 0
    assets = catalyst.get("affected_asset_classes") or []

    llm_tickers = catalyst.get("affected_tickers") or []
    # Canonical ticker safe-list per narrative
    CANONICAL_TICKERS = {
        "usd_debasement_reserve_diversification":        ["GLD", "UUP", "SLV", "IAU", "DXY", "EURUSD=X", "DX=F", "GC=F"],
        "critical_resource_control_infrastructure": ["CL=F", "NG=F", "XOM", "CVX", "CCJ", "URNM", "URA", "NLR", "REMX", "XLE"],
        "supply_chain_resilience_reshoring_defense":       ["XLI", "ITA", "PPA", "XME", "FDX", "CAT"],
        "china_geoeconomic_expansion":          ["FXI", "KWEB", "MCHI", "ASHR", "BABA", "OBOR", "AAXJ", "CNYB", "EMLC", "CNY=X"],
        "space_economy_commercialization":         ["ROKT", "UFO", "ARKX", "RKLB", "LMT", "MARS", "SPCE", "ASTR", "MOON", "NOC"],
        "gene_editing_biotech_longevity":          ["ARKG", "XBI", "IBB", "CRSP", "NTLA"],
        "tech_convergence_platforms_ai_autonomy":      ["CLOU", "WCLD", "ARTY", "BOTZ", "FCLD", "MSFT", "GOOGL", "NVDA", "ORCL", "CRM", "AMZN", "QQQ"],
        "prestige_asset_acquisition_strategic_investment":        ["DKNG", "PENN", "MGM", "DIS", "CMCSA", "WBD", "FOXA", "MSG", "FUBO", "STAD", "BATRK", "MANU", "MSGS"],
        "ai_compute_semiconductor_hegemony":              ["NVDA", "AMD", "TSM", "SMH", "ASML"],
        "digital_assets_reserves_onchain_finance":        ["BTC-USD", "ETH-USD", "COIN", "MSTR"],
        "monetary_policy_regime_shift_rate_cycle":            ["TLT", "SHY", "IEF", "^TNX", "^IRX", "ZN=F", "ZB=F"],
        "commodity_supercycle_supply_rebalancing":  ["DBC", "GLD", "GDX", "HG=F", "COPX", "XME", "WEAT", "CORN"],
    }

    if narrative_id in CANONICAL_TICKERS:
        narrative_safe_list = CANONICAL_TICKERS[narrative_id]
        filtered_tickers = [t for t in llm_tickers if t in narrative_safe_list]
        final_tickers = filtered_tickers if filtered_tickers else narrative_safe_list[:4]
    else:
        final_tickers = llm_tickers[:4]

    card_catalyst = (catalyst.get("they_say") or "").strip() or "Awaiting narrative acceleration event."
    card_flow = (catalyst.get("reality") or "").strip() or "Capital baseline established. Monitoring movements."

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_count = sum(
        1 for s in mine
        if s.get("generated_at") and datetime.fromisoformat(s["generated_at"]) > cutoff
    )
    status_label = calculate_narrative_status(gap, recent_count)

    weights = catalyst.get("narrative_weights", {})
    domino = []
    for nid, score in sorted(weights.items(), key=lambda x: -x[1]):
        if nid == narrative_id:
            continue
        if score >= 0.25:
            cfg = narrative_config.get(nid, {})
            domino.append({
                "narrative_id": nid,
                "title": cfg.get("display_name", nid.replace("_", " ").title()),
                "score": round(score, 2),
            })

    if capital >= 1_000_000_000:
        capital_fmt = f"${capital / 1e9:.1f}B"
    elif capital >= 1_000_000:
        capital_fmt = f"${capital / 1e6:.1f}M"
    else:
        capital_fmt = f"${capital:,}"

    return {
        "catalyst_text": card_catalyst,
        "catalyst_gap": gap,
        "flow_text": card_flow,
        "capital_usd": capital,
        "capital_fmt": capital_fmt,
        "affected_tickers": final_tickers,
        "affected_asset_classes": assets,
        "domino": domino,
        "status": status_label,
    }

def run_nextjs_build():
    """Runs npm run build inside web_dir and copies the output to public_dir."""
    print("[build_frontend] Starting Next.js build locally...")
    
    # Check if npm is available
    if not shutil.which("npm"):
        print("[build_frontend] npm command not found. Skipping Next.js build.")
        return False

    posted_stories = PUBLIC_DATA / "posted_stories.jsonl"
    posted_stories_backup = None
    if posted_stories.exists():
        try:
            posted_stories_backup = posted_stories.read_text()
        except Exception:
            pass

    flows_json = PUBLIC_DATA / "flows.json"
    flows_backup = None
    if flows_json.exists():
        try:
            flows_backup = flows_json.read_text()
        except Exception:
            pass
        
    try:
        subprocess.run(["npm", "install"], cwd=WEB_DIR, check=True)
        subprocess.run(["npm", "run", "build"], cwd=WEB_DIR, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[build_frontend] Next.js build failed: {e}")
        return False
        
    # Recreate public directory (preserving public/data/posted_stories.jsonl and flows.json)
    if PUBLIC.exists():
        # Only wipe everything EXCEPT public/data/ if we want, or wipe everything and restore backup
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    
    # Copy web/out to public/
    out_dir = WEB_DIR / "out"
    if out_dir.exists():
        for item in out_dir.iterdir():
            dest = PUBLIC / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
                
    if posted_stories_backup:
        PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
        posted_stories.write_text(posted_stories_backup)

    if flows_backup:
        PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
        flows_json.write_text(flows_backup)
        
    print("[build_frontend] Next.js build completed successfully.")
    return True

def compile_data_json():
    """Loads stories, normalizes them, writes stories.json & narratives.json, and runs build_dossiers."""
    print("[build_frontend] Compiling data JSONs...")
    
    stories_src = DATA / "stories.json"
    if not stories_src.exists():
        print(f"[build_frontend] ERROR: {stories_src} not found. Cannot compile data.")
        return False
        
    # Recreate public/data/ & public/data/locales/
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DATA / "locales").mkdir(parents=True, exist_ok=True)
    
    # Copy all raw data JSONs to public/data first (flows.json, derivatives.json, etc.)
    for f in DATA.glob("*.json"):
        if f.name == "flows.json":
            continue
        shutil.copy2(f, PUBLIC_DATA / f.name)
        
    # Copy locales
    locales_src = TEMPLATES / "locales"
    if locales_src.exists():
        for f in locales_src.glob("*.json"):
            shutil.copy2(f, PUBLIC_DATA / "locales" / f.name)

    stories_raw = load_json(stories_src)
    all_stories = stories_raw.get("all_stories", [])
    if not all_stories:
        # Fallback to containers if all_stories is missing
        containers = stories_raw.get("containers", {})
        for cid, cdata in containers.items():
            for s in cdata.get("stories", []):
                s["_container_id"] = cid
                all_stories.append(s)

    narrative_config, narrative_ids = load_narratives_config()
    
    # Normalize stories
    for s in all_stories:
        nid = s.get("narrative_id", "")
        if nid and nid in narrative_config:
            s["_container_id"] = nid
            s["_container_title"] = narrative_config[nid].get("display_name", nid)
            
    # Filter T source anomalies
    all_stories = [s for s in all_stories if (s.get("source_name") or "").strip().upper() != "T"]

    # Normalize capital values
    for s in all_stories:
        computed = s.get("capital_at_stake_usd", 0) or 0
        existing = s.get("capital_volume_usd", 0) or 0
        if computed > 0:
            s["capital_volume_usd"] = computed
        elif existing == 0:
            s["capital_volume_usd"] = 0
            
    all_stories.sort(key=lambda s: s.get("generated_at", ""), reverse=True)

    # Load Narrative Market Cap data
    NMC_PATH = DATA / "narrative_cap.json"
    NMC_DATA = load_json(NMC_PATH) if NMC_PATH.exists() else {}

    # Compile narratives.json
    narratives = []
    for cid in narrative_ids:
        cstories = [s for s in all_stories if s.get("narrative_id") == cid]
        caps = [s.get("capital_volume_usd", 0) or 0 for s in cstories]
        gaps = [s.get("contradiction_gap", 0) or 0 for s in cstories]
        total_cap = sum(caps) / 1e9
        
        nmc_entry = NMC_DATA.get(cid, {})
        nmc_usd = nmc_entry.get("narrative_cap_usd", 0)
        if nmc_usd and nmc_usd > 0:
            total_cap = nmc_usd / 1e9
            
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        top_gap = max(gaps) if gaps else 0
        directions = {"inflow": 0, "outflow": 0, "neutral": 0}
        for s in cstories:
            cf = s.get("capital_flow") or {}
            d = (cf.get("direction") or "neutral").lower()
            directions[d] = directions.get(d, 0) + 1
            
        phase, phase_desc = narrative_phase(top_gap, len(cstories))
        cfg = narrative_config.get(cid, {})
        ticker = (cfg.get("tickers", [""]) or [""])[0]
        threshold_val = cfg.get("invalidation_threshold", "N/A")
        threshold_desc = cfg.get("status", "")
        
        narratives.append({
            "id": cid,
            "title": cfg.get("display_name", cid.replace("_", " ").title()),
            "ticker": ticker or "N/A",
            "capital_b": total_cap,
            "count": len(cstories),
            "gap": avg_gap,
            "directions": directions,
            "phase": phase,
            "phase_desc": phase_desc,
            "threshold_val": threshold_val,
            "threshold_desc": threshold_desc,
            "icon": ICON_FALLBACK_MAP.get(cid, "public"),
            "cft": build_cft_block(cid, all_stories, narrative_config),
        })

    # Compile discrepancies & capital flows
    discrepancies = [s for s in all_stories if (s.get("contradiction_gap") or 0) >= 40]
    capital_flows = {}
    for n in narratives:
        nid = n["id"]
        cap_stories = [s for s in all_stories if s.get("narrative_id") == nid]
        inflow_total = sum((s.get("capital_volume_usd") or 0) / 1e9 for s in cap_stories
                          if (s.get("capital_flow") or {}).get("direction") == "inflow")
        outflow_total = sum((s.get("capital_volume_usd") or 0) / 1e9 for s in cap_stories
                           if (s.get("capital_flow") or {}).get("direction") == "outflow")
        disc_count = sum(1 for s in cap_stories if (s.get("contradiction_gap") or 0) >= 40)
        capital_flows[nid] = {
            "title": n["title"],
            "ticker": n["ticker"],
            "inflow_b": round(inflow_total, 2),
            "outflow_b": round(outflow_total, 2),
            "net_b": round(inflow_total - outflow_total, 2),
            "total_capital_b": round(n["capital_b"], 1),
            "dominant_direction": "inflow" if inflow_total > outflow_total else ("outflow" if outflow_total > inflow_total else "neutral"),
            "story_count": n["count"],
            "discrepancies": disc_count,
            "avg_contradiction_gap": round(n["gap"], 1),
        }

    # Slim down stories for stories.json
    dead_fields = {"thesis", "multi_persona", "confidence_pct", "contradiction_score", "sector", "source_name", "tags"}
    stories_slim = []
    for s in all_stories[:200]:
        stories_slim.append({k: v for k, v in s.items() if k not in dead_fields})

    # Save compiled JSON files
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "build_frontend.py unified",
        "containers": stories_raw.get("containers", {}),
        "all_stories": stories_slim,
        "total_stories": len(all_stories)
    }
    
    with open(PUBLIC_DATA / "stories.json", "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        
    with open(PUBLIC_DATA / "narratives.json", "w") as f:
        json.dump({"generated_at": doc["generated_at"], "narratives": narrative_config, "narratives_list": narratives}, f, indent=2, ensure_ascii=False)

    # Save capital flows
    existing_flows = {}
    if (PUBLIC_DATA / "flows.json").exists():
        try:
            existing_flows = load_json(PUBLIC_DATA / "flows.json")
        except Exception:
            pass

    with open(PUBLIC_DATA / "flows.json", "w") as f:
        existing_flows["narrative_flows"] = capital_flows
        existing_flows["generated_at"] = doc["generated_at"]
        json.dump(existing_flows, f, indent=2, ensure_ascii=False)

    print(f"[build_frontend] Successfully compiled JSON feeds: {len(stories_slim)} stories, {len(narratives)} narratives.")

    # Compile Dossiers
    try:
        sys.path.append(str(PROJECT / "scripts"))
        from build_dossiers import build_dossiers
        # Read raw flows data
        flows_raw = load_json(DATA / "flows.json") if (DATA / "flows.json").exists() else {}
        build_dossiers(all_stories, flows_raw, narrative_config)
    except Exception as e:
        print(f"[build_frontend] WARNING: build_dossiers failed: {e}")

    return True

def main():
    # If we are local and npm is installed, run Next.js compilation
    is_local_next = WEB_DIR.exists() and (WEB_DIR / "package.json").exists()
    
    if is_local_next:
        run_nextjs_build()
    else:
        print("[build_frontend] VM environment detected. Skipping Next.js static asset build.")

    # Compile JSON feeds & dossier pages in both environments
    compile_data_json()

if __name__ == "__main__":
    main()
