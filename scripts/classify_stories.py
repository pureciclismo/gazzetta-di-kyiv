#!/usr/bin/env python3
"""
La Gazzetta di Kyiv — Phase 3
Module: classify_stories.py
Purpose: Re-assign narrative_id to all stories after synthesis merges.
         Uses keyword matching from narratives.json descriptions + tickers.
Runs: between synthesis and calc_capital in governor loop.
"""

import os, sys, json, re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
STORIES_FILE = DATA_DIR / "stories.json"
NARRATIVES_FILE = DATA_DIR / "narratives.json"
SITE_STORIES_FILE = PROJECT / "public" / "data" / "stories.json"

# Keyword boosters from the proven backfill — catches stories missed by ticker matching
SEED_KEYWORDS = {
    "ai_compute_semiconductor_hegemony": ["nvidia", "tsmc", "semiconductor", "chip", "gpu", "h100", "b200", "amd", "intel", "taiwan semiconductor", "advanced gpu accelerators", "foundry capacity concentration", "export control regimes", "hbm advanced packaging"],
    "digital_assets_reserves_onchain_finance": ["bitcoin", "ethereum", "btc", "eth", "stablecoin", "defi", "crypto", "coinbase", "digital asset", "stablecoin settlement", "tokenized reserves", "on-chain settlement", "institutional crypto adoption"],
    "monetary_policy_regime_shift_rate_cycle": ["fed", "fomc", "rate cut", "rate hike", "powell", "treasury yield", "bond yield", "interest rate", "central bank", "inflation", "world bank", "global growth", "ppi", "wholesale price", "policy pivot", "tightening cycle", "real rate regime", "monetary regime shift"],
    "commodity_supercycle_supply_rebalancing": ["crude oil", "copper", "corn futures", "soybean", "wheat futures", "gold price", "silver price", "oil price", "oil market", "commodity price", "brent", "wti crude", "natural gas", "transition metals boom", "supply squeeze", "physical supply rebalancing"],
    "space_economy_commercialization": ["spacex", "nasa", "blue origin", "rocket", "satellite", "orbital", "lunar", "mars mission", "starship", "space commercialization", "LEO infrastructure", "satcom constellations", "space logistics"],
    "gene_editing_biotech_longevity": ["biopharma", "biotech", "crispr", "fda approval", "gene therapy", "clinical trial", "pharma", "drug", "in vivo editing", "cell therapy commercialization", "longevity therapeutics"],
    "china_geoeconomic_expansion": ["china etf", "chinese market", "hong kong", "shanghai", "beijing", "xi jinping", "chinese economy", "china stock", "Belt and Road expansion", "RMB internationalization", "China-led trade corridors", "economic coercion", "dual circulation export leverage"],
    "usd_debasement_reserve_diversification": ["dollar index", "usd weakness", "fed reserve", "currency war", "dedollarization", "brics currency", "gold sinks", "gold rally", "gold hits", "USD debasement", "reserve diversification", "de-dollarization", "currency substitution"],
    "critical_resource_control_infrastructure": ["nuclear", "uranium", "energy independence", "power grid", "renewable energy", "iran", "opec", "hormuz", "persian gulf", "gulf shock", "oil export", "gas price", "solar", "coal", "russia ukraine", "samara refinery", "eia", "oil tanker", "crude export", "energy security", "critical minerals control", "strategic stockpiles", "grid resilience"],
    "supply_chain_resilience_reshoring_defense": ["supply chain", "tariff", "trade war", "protectionist", "reshoring", "nearshoring", "merger", "acquisition", "defense logistics modernization", "supply-chain resilience"],
    "tech_convergence_platforms_ai_autonomy": ["artificial intelligence", "cloud computing", "enterprise software", "ai model", "machine learning", "openai", "anthropic", "data center", "aws", "google", "rivian", "amazon", "AI-native platforms", "autonomous workflows", "enterprise AI adoption", "platform consolidation"],
    "prestige_asset_acquisition_strategic_investment": ["sports franchise", "premier league", "nba team", "sovereign fund", "private equity sports", "frasers", "soccer club", "prestige asset acquisition", "state-affiliated investment", "trophy asset purchases", "strategic capital deployment"],
}

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
        "title": "AI Compute & Semiconductor Hegemony",
        "subtitle": "GPU supply chains, foundry bottlenecks, lithography wars, domestic compute hubs",
        "sort_order": 8,
    },
    "digital_assets_reserves_onchain_finance": {
        "title": "Digital Assets & On-Chain Settlement",
        "subtitle": "Bitcoin reserve assets, tokenized treasuries, stablecoin liquidity networks",
        "sort_order": 9,
    },
    "monetary_policy_regime_shift_rate_cycle": {
        "title": "Monetary Regime Pivots",
        "subtitle": "Real interest rate shifts, central bank liquidity cycles, fiscal dominance",
        "sort_order": 10,
    },
    "commodity_supercycle_supply_rebalancing": {
        "title": "Commodity Supercycle & Physical Markets",
        "subtitle": "Metals deficits, agriculture hedging, supply chain physical bottlenecks",
        "sort_order": 11,
    },
}


def fix_ownership(path_str: str):
    if sys.platform != "linux":
        return
    try:
        import pwd, grp
        uid = pwd.getpwnam("gazzetta").pw_uid
        gid = grp.getgrnam("gazzetta").gr_gid
        os.chown(path_str, uid, gid)
    except (KeyError, OSError):
        pass


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_classifier(narratives: dict) -> dict:
    """Build per-narrative regex patterns from display_name + tickers."""
    matchers = {}
    for nid, meta in narratives.items():
        terms = [meta["display_name"].lower()]
        for t in meta.get("tickers", []):
            terms.append(t.lower().replace("=f", "").replace("-usd", "").replace("^", ""))
        pattern = r'\b(' + '|'.join(map(re.escape, terms)) + r')\b'
        matchers[nid] = re.compile(pattern, re.IGNORECASE)
    return matchers


def classify_story(story: dict, matchers: dict, keywords: dict) -> str:
    """Assign narrative_id using ticker/name matching + seed keywords."""
    headline = story.get("headline", "").lower()
    they_say = story.get("they_say", "").lower()
    content = headline + " " + they_say

    # 1. Try ticker/display_name regex matching
    best_nid = None
    best_len = 0
    for nid, regex in matchers.items():
        matches = regex.findall(content)
        if matches and len(matches) > best_len:
            best_nid = nid
            best_len = len(matches)

    if best_nid:
        return best_nid

    # 2. Try seed keyword matching for emergent narratives
    for nid, kws in keywords.items():
        if any(kw in content for kw in kws):
            return nid

    # 3. Fallback: use container/pillar only if it's a canonical narrative_id
    legacy = story.get("pillar") or story.get("container")
    CANONICAL = {
        "usd_debasement_reserve_diversification", "critical_resource_control_infrastructure",
        "supply_chain_resilience_reshoring_defense", "china_geoeconomic_expansion",
        "space_economy_commercialization", "gene_editing_biotech_longevity",
        "tech_convergence_platforms_ai_autonomy", "prestige_asset_acquisition_strategic_investment",
        "ai_compute_semiconductor_hegemony", "digital_assets_reserves_onchain_finance",
        "monetary_policy_regime_shift_rate_cycle", "commodity_supercycle_supply_rebalancing",
    }
    if legacy and legacy in CANONICAL:
        return legacy

    return "unassigned"


def main():
    print("[classify] Re-assigning narrative_ids...")
    stories_data = load_json(STORIES_FILE)
    narratives_data = load_json(NARRATIVES_FILE)

    narratives = narratives_data.get("narratives", {})
    matchers = build_classifier(narratives)

    all_stories = stories_data.get("all_stories", [])
    classified = 0
    changed = 0

    migration_map = {
        "dollar_decline": "usd_debasement_reserve_diversification",
        "critical_resource_control": "critical_resource_control_infrastructure",
        "energy_sovereignty": "critical_resource_control_infrastructure",
        "deglobalization": "supply_chain_resilience_reshoring_defense",
        "china_ascent": "china_geoeconomic_expansion",
        "space_economy": "space_economy_commercialization",
        "gene_editing": "gene_editing_biotech_longevity",
        "tech_convergence": "tech_convergence_platforms_ai_autonomy",
        "wealthy_sports": "prestige_asset_acquisition_strategic_investment",
        "ai_chips": "ai_compute_semiconductor_hegemony",
        "crypto_reserve": "digital_assets_reserves_onchain_finance",
        "rate_cycle": "monetary_policy_regime_shift_rate_cycle",
        "commodity_supercycle": "commodity_supercycle_supply_rebalancing",
    }

    for story in all_stories:
        # Migrate old IDs to new IDs in all fields
        old_nid = story.get("narrative_id", "")
        if old_nid in migration_map:
            story["narrative_id"] = migration_map[old_nid]
            changed += 1
        
        c = story.get("container", "")
        if c in migration_map:
            story["container"] = migration_map[c]
            
        p = story.get("pillar", "")
        if p in migration_map:
            story["pillar"] = migration_map[p]
            
        if story.get("containers"):
            story["containers"] = [migration_map.get(x, x) for x in story["containers"]]
            
        if story.get("narrative_weights"):
            new_weights = {}
            for k, v in story["narrative_weights"].items():
                new_key = migration_map.get(k, k)
                new_weights[new_key] = v
            story["narrative_weights"] = new_weights

        # DeepSeek multi-vector bypass: preserve LLM-assigned routing
        if story.get("narrative_weights"):
            # Ensure containers list exists (rebuild from weights at 0.40 threshold)
            if "containers" not in story:
                story["containers"] = [
                    nid for nid, score in story["narrative_weights"].items()
                    if score >= 0.40
                ]
            classified += 1
            continue

        old_nid = story.get("narrative_id", "")
        new_nid = classify_story(story, matchers, SEED_KEYWORDS)

        # Reclassify if: no narrative_id, unassigned, or not in current taxonomy
        if not old_nid or old_nid == "unassigned" or old_nid not in narratives:
            story["narrative_id"] = new_nid
            story["narrative_confidence"] = 0.7 if new_nid != "unassigned" else 0.0
            changed += 1
        # Also reclassify legacy tags that aren't in the 12-narrative taxonomy
        elif old_nid in ("china_ascendancy", "multi_pillar", "eu_fragmentation",
                         "abundance_tech", "neutral", "blockchain_agentic"):
            story["narrative_id"] = new_nid
            story["narrative_confidence"] = 0.5
            changed += 1
        classified += 1

    stories_data["all_stories"] = all_stories

    # Rebuild tags_index from current all_stories (eliminates orphans)
    tags_index = {}
    for s in all_stories:
        sid = str(s.get("story_id", ""))
        # Index by containers list (multi-vector) or narrative_id (legacy)
        index_ids = s.get("containers") or [s.get("narrative_id", "")]
        for nid in index_ids:
            if nid and nid != "unassigned":
                tags_index.setdefault(nid, [])
                if sid and sid not in tags_index[nid]:
                    tags_index[nid].append(sid)
        for tag in (s.get("entity_tags") or []):
            tags_index.setdefault(tag, [])
            if sid and sid not in tags_index[tag]:
                tags_index[tag].append(sid)
    stories_data["tags_index"] = tags_index

    # Rebuild containers dictionary
    new_containers = {}
    for cid, meta in CONTAINER_META.items():
        new_containers[cid] = {
            "title": meta["title"],
            "subtitle": meta["subtitle"],
            "count": 0,
            "stories": [],
        }

    for story in all_stories:
        cid = story.get("narrative_id", "")
        if cid in new_containers:
            new_containers[cid]["stories"].append(story)
            new_containers[cid]["count"] += 1

    sorted_containers = dict(sorted(new_containers.items(), key=lambda x: CONTAINER_META[x[0]]["sort_order"]))
    stories_data["containers"] = sorted_containers
    stories_data["total_stories"] = len(all_stories)

    tmp_path = STORIES_FILE.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
      json.dump(stories_data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, STORIES_FILE)

    # Sync to public/data/stories.json for deployment
    try:
      SITE_STORIES_FILE.parent.mkdir(parents=True, exist_ok=True)
      with open(SITE_STORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(stories_data, f, indent=2, ensure_ascii=False)
      fix_ownership(str(SITE_STORIES_FILE))
    except Exception as e:
      print(f"[classify] Warning: failed to sync to site stories: {e}")

    fix_ownership(str(STORIES_FILE))

    print(f"[classify] {classified} stories checked, {changed} re-classified.")


if __name__ == "__main__":
    main()
