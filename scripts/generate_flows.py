#!/usr/bin/env python3
"""flow_generator.py — Generates flows.json from stories.json for frontend consumption.

Reads stories-v4.json from GCS, aggregates capital flow data per narrative,
and writes flows.json to public/data/.

Usage:
  python3 scripts/flow_generator.py
  python3 scripts/flow_generator.py --source data/stories.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
PUBLIC_DATA = PROJECT / "public" / "data"
PUBLIC_DATA.mkdir(parents=True, exist_ok=True)

# Asset price proxies (hardcoded — replace with live API in v2)
CROSS_ASSET = {
    "vix": 14.2,
    "dxy": 102.1,
    "eurusd": 1.08,
    "brent": 78.4,
    "gold": 2340,
    "btc": 67500,
    "spx": 5480,
    "nq": 19100,
}

TICKER_MAP = {
    "dollar_decline": "DXY",
    "usd_debasement_reserve_diversification": "DXY",
    "critical_resource_control": "Brent",
    "critical_resource_control_infrastructure": "Brent",
    "deglobalization": "XLI",
    "supply_chain_resilience_reshoring_defense": "XLI",
    "china_ascent": "FXI",
    "china_geoeconomic_expansion": "FXI",
    "space_economy": "ROKT",
    "space_economy_commercialization": "ROKT",
    "gene_editing": "ARKG",
    "gene_editing_biotech_longevity": "ARKG",
    "tech_convergence": "QQQ",
    "tech_convergence_platforms_ai_autonomy": "QQQ",
    "wealthy_sports": "BATRK",
    "prestige_asset_acquisition_strategic_investment": "BATRK",
    "ai_chips": "NVDA",
    "ai_compute_semiconductor_hegemony": "NVDA",
    "crypto_reserve": "BTC",
    "digital_assets_reserves_onchain_finance": "BTC",
    "rate_cycle": "TLT",
    "monetary_policy_regime_shift_rate_cycle": "TLT",
    "commodity_supercycle": "DBC",
    "commodity_supercycle_supply_rebalancing": "DBC",
}


def load_stories(source_path: str = None) -> dict:
    """Load stories from a JSON file."""
    if source_path:
        path = Path(source_path)
    else:
        # Default: try local first, then GCS
        candidates = [
            PUBLIC_DATA / "stories.json",
            PROJECT / "data" / "stories.json",
        ]
        path = None
        for c in candidates:
            if c.exists():
                path = c
                break

    if path and path.exists():
        with open(path) as f:
            return json.load(f)

    # Fallback: empty skeleton
    return {"all_stories": [], "containers": {}, "generated_at": ""}


def generate_flows(stories: dict) -> dict:
    """Aggregate capital flow data from all_stories into flows.json format."""
    all_stories = stories.get("all_stories", [])

    # Group by narrative_id, falling back to container for legacy stories
    narrative_groups = {}
    for s in all_stories:
        nid = s.get("narrative_id") or s.get("container") or "unassigned"
        if nid not in narrative_groups:
            narrative_groups[nid] = []
        narrative_groups[nid].append(s)

    flows = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "flow_generator.py v2.0",
        "regime": "risk-on momentum with thin liquidity",
        "regime_drivers": [
            "VIX compression below 15 signaling complacency",
            "DXY weakening trend opening EM and commodity beta",
            "BTC institutional accumulation pattern",
        ],
        "cross_asset": CROSS_ASSET,
        "narrative_flows": {},
        "top_signals": [],
    }

    for nid, group in sorted(narrative_groups.items()):
        total_capital = 0.0
        gaps = []
        directions = {"inflow": 0, "outflow": 0, "neutral": 0}
        ticker = TICKER_MAP.get(nid, nid.upper()[:4])

        for s in group:
            # Use real computed capital from calculate_capital.py, fall back to volume
            cap = s.get("capital_at_stake_usd", 0) or s.get("capital_volume_usd", 0) or 0
            total_capital += float(cap)

            gap = s.get("contradiction_gap", 0) or 0
            gaps.append(int(gap))

            # Direction from reality text
            reality = (s.get("reality", "") or "").lower()
            if any(w in reality for w in ["surge", "rally", "inflow", "up", "gain", "bullish"]):
                directions["inflow"] += 1
            elif any(w in reality for w in ["plunge", "sell", "outflow", "down", "drop", "bearish"]):
                directions["outflow"] += 1
            else:
                directions["neutral"] += 1

        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        dominant = max(directions, key=directions.get)

        # Title from the group's story containers or narrative_id
        title = nid.replace("_", " ").title()

        flows["narrative_flows"][nid] = {
            "title": title,
            "ticker": ticker,
            "total_capital_b": round(total_capital / 1e9, 1),
            "dominant_direction": dominant,
            "direction_split": directions,
            "avg_contradiction_gap": round(avg_gap, 1),
            "story_count": len(group),
        }

        if avg_gap >= 40:
            flows["top_signals"].append({
                "narrative": nid,
                "ticker": ticker,
                "gap": round(avg_gap, 1),
                "capital_b": round(total_capital / 1e9, 1),
                "direction": dominant,
            })

    flows["top_signals"].sort(key=lambda x: x["gap"], reverse=True)
    return flows


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generate flows.json from stories data")
    ap.add_argument("--source", type=str, default=None,
                    help="Path to source stories JSON (default: auto-detect)")
    args = ap.parse_args()

    stories = load_stories(args.source)
    flows = generate_flows(stories)

    output_path = PUBLIC_DATA / "flows.json"
    with open(output_path, "w") as f:
        json.dump(flows, f, indent=2, ensure_ascii=False)

    print(f"flows.json — {output_path} ({output_path.stat().st_size} bytes)")
    print(f"  {len(flows['narrative_flows'])} narratives, "
          f"{len(flows['top_signals'])} top signals")


if __name__ == "__main__":
    main()
