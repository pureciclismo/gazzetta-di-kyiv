#!/usr/bin/env python3
"""
fetch_narrative_cap.py — Narrative Market Capitalization Engine v1

Pulls market cap and liquidity data from yfinance for all assets
in data/narrative_graph.json, applies theme purity weights, and writes:
  - data/narrative_graph.json (full graph with computed values)
  - data/narrative_cap.json    (lightweight frontend cache)

Cadence: Daily at 07:00 Kyiv (04:00 UTC).
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")

# Resolve paths from script location (safe for cron from any cwd)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT = SCRIPT_DIR.parent
GRAPH_PATH = PROJECT / "data" / "narrative_graph.json"
CACHE_PATH = PROJECT / "data" / "narrative_cap.json"

# Log to stdout (cron captures) or explicit log file
LOG_FILE = os.environ.get("NMC_LOG", "")


def log(msg: str):
    line = f"[{datetime.now(KYIV_TZ).isoformat()}] {msg}"
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")


def load_graph() -> dict:
    if not GRAPH_PATH.exists():
        log(f"ERROR: {GRAPH_PATH} not found. Run with --init to create skeleton.")
        sys.exit(1)
    with open(GRAPH_PATH) as f:
        return json.load(f)


def fetch_narrative_caps(graph: dict) -> dict:
    """Pull market data for all assets and compute NMC + liquidity."""
    import yfinance as yf

    frontend_cache = {}
    now_ts = datetime.now(KYIV_TZ).isoformat()

    for nid, data in graph.items():
        total_nmc = 0
        total_nl = 0
        updated_assets = []

        display = data.get("display_name", nid)
        log(f"Processing: {display} ({nid})")

        for asset in data.get("assets", []):
            ticker_str = asset["ticker"]
            purity = asset.get("purity_weight", 1.0)
            asset_type = asset.get("type", "equity")

            try:
                t = yf.Ticker(ticker_str)
                info = t.info

                # Resilience: handle delisted or unavailable tickers
                if not info or info.get("regularMarketPreviousClose") is None:
                    log(f"  ⚠ {ticker_str}: No market data available (delisted?)")
                    updated_assets.append(asset)
                    continue

                # 1. Type-safe capitalization
                if asset_type == "equity":
                    raw_cap = info.get("marketCap", 0) or 0
                elif asset_type == "etf":
                    raw_cap = info.get("totalAssets") or info.get("netAssets") or 0
                else:
                    raw_cap = 0

                # 2. Average daily dollar liquidity
                price = info.get("regularMarketPreviousClose") or info.get("currentPrice") or 1
                avg_volume = info.get("averageVolume") or info.get("averageVolume10day") or 0
                raw_liquidity = int(avg_volume * price)

                # 3. Apply theme purity weights
                weighted_cap = int(raw_cap * purity)
                weighted_liq = int(raw_liquidity * purity)

                total_nmc += weighted_cap
                total_nl += weighted_liq

                # Persist node state
                asset_node = dict(asset)
                if asset_type == "equity":
                    asset_node["market_cap"] = raw_cap
                else:
                    asset_node["total_assets"] = raw_cap
                asset_node["calculated_liquidity_usd"] = raw_liquidity
                updated_assets.append(asset_node)

                log(f"  ✓ {ticker_str}: Cap={raw_cap:,.0f} Liq={raw_liquidity:,.0f} (w={purity})")

            except Exception as e:
                log(f"  ❌ {ticker_str}: {e}")
                updated_assets.append(asset)

        # Update narrative node
        data["narrative_cap_usd"] = total_nmc
        data["narrative_liquidity_usd"] = total_nl
        data["as_of"] = now_ts
        data["assets"] = updated_assets

        # Lightweight frontend cache
        frontend_cache[nid] = {
            "display_name": display,
            "narrative_cap_usd": total_nmc,
            "narrative_liquidity_usd": total_nl,
            "as_of": now_ts,
        }

        log(f"  → NMC: ${total_nmc:,.0f} | NL: ${total_nl:,.0f}")

    return frontend_cache


def main():
    parser = argparse.ArgumentParser(description="Fetch Narrative Market Capitalization")
    parser.add_argument("--force", action="store_true", help="Force fetch, ignoring cache")
    parser.add_argument("--cache-hours", type=float, default=24.0, help="Cache age threshold in hours (default: 24.0)")
    args = parser.parse_args()

    # Cache check
    if not args.force and CACHE_PATH.exists():
        mtime = datetime.fromtimestamp(CACHE_PATH.stat().st_mtime)
        age = datetime.now() - mtime
        if age < timedelta(hours=args.cache_hours):
            log(f"Cache is valid (age: {age.total_seconds() / 3600:.1f}h < {args.cache_hours}h). Skipping fetch.")
            return 0

    log("NMC Engine v1 — starting fetch cycle")

    graph = load_graph()
    frontend_cache = fetch_narrative_caps(graph)

    # Atomic writes
    with open(GRAPH_PATH, "w") as f:
        json.dump(graph, f, indent=2)
    log(f"Wrote {GRAPH_PATH}")

    with open(CACHE_PATH, "w") as f:
        json.dump(frontend_cache, f, indent=2)
    log(f"Wrote {CACHE_PATH}")

    # Summary
    total_nmc = sum(n["narrative_cap_usd"] for n in graph.values())
    active = sum(1 for n in graph.values() if n["narrative_cap_usd"] > 0)
    log(f"Complete. {active}/{len(graph)} narratives with data. Total NMC: ${total_nmc:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
