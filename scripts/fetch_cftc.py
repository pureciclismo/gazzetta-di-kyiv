#!/usr/bin/env python3
"""
fetch_cftc.py -- CFTC Commitments of Traders Report via Public SODA API
========================================================================
Weekly fetch of institutional futures positioning. Maps 18 physical commodity
contracts to Gazzetta's narratives and outputs cftc_positions.json.

API:      https://publicreporting.cftc.gov/resource/kh3c-gbw2.json
Dataset:  Disaggregated Futures+Options Combined
Docs:     https://publicreporting.cftc.gov/stories/s/r4w3-av2u
Key:      NONE REQUIRED -- completely public SODA endpoint

Schedule: Weekly (Wednesday after 15:30 ET -- COT release day).
          Governor runs this daily after market_data, before synthesis.
          Non-critical: data is weekly, so 6/7 days return cached latest.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

# -- config ----------------------------------------------------------
PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = DATA_DIR / "cftc_positions.json"

BASE_URL = "https://publicreporting.cftc.gov/resource/kh3c-gbw2.json"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# -- Commodity to Narrative mapping ----------------------------------
# Exact commodity_name values as returned by the SODA API.
# Each entry: the CFTC commodity_name, ticker symbol, Gazzetta narrative,
# and human-readable contract name.
COMMODITY_MAP = [
    # --- usd_debasement_reserve_diversification: gold, silver ---
    {"cftc_name": "GOLD",         "ticker": "GC",  "narrative": "usd_debasement_reserve_diversification",  "label": "Gold"},
    {"cftc_name": "SILVER",       "ticker": "SI",  "narrative": "usd_debasement_reserve_diversification",  "label": "Silver"},
    {"cftc_name": "PALLADIUM",    "ticker": "PA",  "narrative": "usd_debasement_reserve_diversification",  "label": "Palladium"},
    {"cftc_name": "PLATINUM",     "ticker": "PL",  "narrative": "usd_debasement_reserve_diversification",  "label": "Platinum"},

    # --- critical_resource_control_infrastructure: oil, gas ---
    {"cftc_name": "CRUDE OIL",            "ticker": "CL",  "narrative": "critical_resource_control_infrastructure",  "label": "WTI Crude Oil"},
    {"cftc_name": "NATURAL GAS",          "ticker": "NG",  "narrative": "critical_resource_control_infrastructure",  "label": "Henry Hub Natural Gas"},
    {"cftc_name": "GASOLINE",             "ticker": "RB",  "narrative": "critical_resource_control_infrastructure",  "label": "RBOB Gasoline"},
    {"cftc_name": "DIESEL/HEATING OIL",   "ticker": "HO",  "narrative": "critical_resource_control_infrastructure",  "label": "Heating Oil / Diesel"},
    {"cftc_name": "JET FUEL",             "ticker": "JF",  "narrative": "critical_resource_control_infrastructure",  "label": "Jet Fuel"},
    {"cftc_name": "JET FUEL/HEATING OIL", "ticker": "JH",  "narrative": "critical_resource_control_infrastructure",  "label": "Jet/Heating Oil Spread"},

    # --- commodity_supercycle_supply_rebalancing: grains, metals, softs ---
    {"cftc_name": "COPPER",       "ticker": "HG",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Copper"},
    {"cftc_name": "ALUMINUM",     "ticker": "AL",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Aluminum"},
    {"cftc_name": "STEEL",        "ticker": "ST",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Steel"},
    {"cftc_name": "CORN",         "ticker": "ZC",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Corn"},
    {"cftc_name": "WHEAT",        "ticker": "ZW",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Wheat"},
    {"cftc_name": "SOYBEANS",     "ticker": "ZS",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Soybeans"},
    {"cftc_name": "SOYBEAN MEAL", "ticker": "ZM",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Soybean Meal"},
    {"cftc_name": "SUGAR",        "ticker": "SB",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Sugar"},
    {"cftc_name": "COFFEE",       "ticker": "KC",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Coffee"},
    {"cftc_name": "COCOA",        "ticker": "CC",  "narrative": "commodity_supercycle_supply_rebalancing",  "label": "Cocoa"},
]

# All narratives we populate
NARRATIVES = [
    "usd_debasement_reserve_diversification", "critical_resource_control_infrastructure", "commodity_supercycle_supply_rebalancing",
    "supply_chain_resilience_reshoring_defense", "china_geoeconomic_expansion", "space_economy_commercialization",
    "gene_editing_biotech_longevity", "tech_convergence_platforms_ai_autonomy", "prestige_asset_acquisition_strategic_investment",
    "ai_compute_semiconductor_hegemony", "digital_assets_reserves_onchain_finance", "monetary_policy_regime_shift_rate_cycle",
]

# -- Fetch helpers ---------------------------------------------------
def fetch_commodity(cftc_name, retries=MAX_RETRIES):
    """Fetch the most recent COT row for a single commodity."""
    for attempt in range(retries):
        try:
            url = (
                f"{BASE_URL}"
                f"?commodity_name={quote(cftc_name)}"
                f"&$order=report_date_as_yyyy_mm_dd+DESC"
                f"&$limit=1"
            )
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0]
                print(
                    f"  [cftc] No data for '{cftc_name}'",
                    file=sys.stderr,
                )
                return None
            elif resp.status_code == 429:
                wait = min(2 ** attempt, 16)
                print(
                    f"  [cftc] Rate limited on '{cftc_name}', "
                    f"waiting {wait}s...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            else:
                print(
                    f"  [cftc] HTTP {resp.status_code} for '{cftc_name}' "
                    f"(attempt {attempt+1})",
                    file=sys.stderr,
                )
                if attempt < retries - 1:
                    time.sleep(2)
        except requests.exceptions.Timeout:
            print(
                f"  [cftc] Timeout on '{cftc_name}' (attempt {attempt+1})",
                file=sys.stderr,
            )
            if attempt < retries - 1:
                time.sleep(5)
        except Exception as e:
            print(
                f"  [cftc] Error on '{cftc_name}': {e}",
                file=sys.stderr,
            )
            if attempt < retries - 1:
                time.sleep(3)
    return None


def safe_int(val):
    """Parse CFTC position values which come as strings from SODA."""
    if val is None:
        return 0
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return 0


def compute_summary(row):
    """Extract the key positioning fields from a COT row."""
    mm_long = safe_int(row.get("m_money_positions_long_all"))
    mm_short = safe_int(row.get("m_money_positions_short_all"))
    prod_long = safe_int(row.get("prod_merc_positions_long"))
    prod_short = safe_int(row.get("prod_merc_positions_short"))
    swap_long = safe_int(row.get("swap_positions_long_all"))
    swap_short = safe_int(row.get("swap__positions_short_all"))
    oi = safe_int(row.get("open_interest_all"))

    return {
        "managed_money_long": mm_long,
        "managed_money_short": mm_short,
        "managed_money_net": mm_long - mm_short,
        "producer_long": prod_long,
        "producer_short": prod_short,
        "producer_net": prod_long - prod_short,
        "swap_long": swap_long,
        "swap_short": swap_short,
        "total_open_interest": oi,
        "spec_pct_of_oi": round((mm_long / oi * 100), 1) if oi > 0 else 0,
        "report_date": row.get("report_date_as_yyyy_mm_dd", ""),
        "contract_market": row.get("contract_market_name", ""),
    }


# -- Main ------------------------------------------------------------
def main():
    print(f"[cftc] Fetching COT data from public SODA API ({len(COMMODITY_MAP)} commodities)")

    positions_by_contract = {}
    positions_by_narrative = {}
    fetched = 0
    failed = 0

    for cfg in COMMODITY_MAP:
        row = fetch_commodity(cfg["cftc_name"])
        if row is None:
            failed += 1
            # Write a degraded entry so consumers know this commodity failed
            positions_by_contract[cfg["ticker"]] = {
                "ticker": cfg["ticker"],
                "label": cfg["label"],
                "narrative": cfg["narrative"],
                "cftc_name": cfg["cftc_name"],
                "managed_money_net": None,
                "report_date": None,
                "status": "error",
                "error": f"No data returned for '{cfg['cftc_name']}'",
            }
            continue

        summary = compute_summary(row)
        summary["ticker"] = cfg["ticker"]
        summary["label"] = cfg["label"]
        summary["narrative"] = cfg["narrative"]
        summary["cftc_name"] = cfg["cftc_name"]
        summary["status"] = "ok"

        positions_by_contract[cfg["ticker"]] = summary
        fetched += 1

        # Aggregate into narrative bucket
        nid = cfg["narrative"]
        if nid not in positions_by_narrative:
            positions_by_narrative[nid] = {
                "contracts": [],
                "total_mm_net": 0,
                "total_producer_net": 0,
                "sentiment": "neutral",
            }
        bucket = positions_by_narrative[nid]
        bucket["contracts"].append(cfg["ticker"])
        bucket["total_mm_net"] += summary.get("managed_money_net", 0) or 0
        bucket["total_producer_net"] += summary.get("producer_net", 0) or 0

        # Courteous pause between calls
        time.sleep(0.3)

    # Derive narrative sentiment
    for nid, bucket in positions_by_narrative.items():
        mm = bucket["total_mm_net"]
        prod = bucket["total_producer_net"]
        if mm > 0 and prod < 0:
            bucket["sentiment"] = "bullish"       # specs long, hedgers short
        elif mm < 0 and prod > 0:
            bucket["sentiment"] = "bearish"       # specs short, hedgers long
        elif abs(mm) < 1000 and abs(prod) < 1000:
            bucket["sentiment"] = "neutral"
        else:
            bucket["sentiment"] = "divergent"     # both same direction = unusual

    # Determine latest report date across all commodities
    report_dates = set()
    for c in positions_by_contract.values():
        rd = c.get("report_date")
        if rd:
            report_dates.add(rd)
    latest_date = max(report_dates) if report_dates else None

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "CFTC Disaggregated COT (public SODA API)",
        "source_url": "https://publicreporting.cftc.gov/resource/kh3c-gbw2.json",
        "latest_report_date": latest_date,
        "commodities_fetched": fetched,
        "commodities_failed": failed,
        "total_commodities_defined": len(COMMODITY_MAP),
        "narratives_populated": len(positions_by_narrative),
        "positions_by_contract": positions_by_contract,
        "positions_by_narrative": positions_by_narrative,
        "status": "ok" if fetched > 0 else "error",
    }

    # Atomic write
    tmp = str(OUTPUT_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    os.replace(tmp, OUTPUT_FILE)

    print(
        f"[cftc] {fetched}/{len(COMMODITY_MAP)} commodities "
        f"({len(positions_by_narrative)} narratives) "
        f"written to {OUTPUT_FILE} "
        f"(report date: {latest_date or 'N/A'})"
    )
    return 0 if fetched > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
