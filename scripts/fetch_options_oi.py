#!/usr/bin/env python3
"""
fetch_options_oi.py — Daily Options Sentiment & Positioning Scraper

Scrapes Yahoo Finance options chains (via yfinance) to calculate total
Open Interest (OI) and Put/Call ratios for key narrative benchmark tickers.
Provides a free alternative to institutional options flow data.

Runs once per day (usually at end of day) to avoid Yahoo IP bans.

Usage:
  python3 scripts/fetch_options_oi.py
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
import yfinance as yf

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
OUTPUT_FILE = DATA_DIR / "options_sentiment.json"

# We select ONE highly liquid benchmark per narrative to avoid rate limits
BENCHMARKS = {
    "critical_resource_control": "XOM",
    "dollar_decline": "GLD",
    "deglobalization": "CAT",
    "china_ascent": "FXI",
    "space_economy": "LMT",
    "gene_editing": "XBI",
    "tech_convergence": "QQQ",
    "wealthy_sports": "DIS",
    "ai_chips": "NVDA",
    "crypto_reserve": "MSTR",
    "rate_cycle": "TLT",
    "commodity_supercycle": "DBC",
}

def fetch_options_sentiment(ticker_symbol):
    """Fetches near-term options chain and calculates aggregate OI & Put/Call ratio."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        expirations = ticker.options
        if not expirations:
            return None
        
        # Take the next 3 expirations for near-term tactical sentiment
        target_expirations = expirations[:3]
        
        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0
        
        for exp in target_expirations:
            chain = ticker.option_chain(exp)
            
            # Aggregate Calls
            calls = chain.calls
            if not calls.empty:
                total_call_oi += calls['openInterest'].sum()
                total_call_vol += calls['volume'].sum()
                
            # Aggregate Puts
            puts = chain.puts
            if not puts.empty:
                total_put_oi += puts['openInterest'].sum()
                total_put_vol += puts['volume'].sum()
                
        # Calculate Ratios
        put_call_oi_ratio = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else 0
        put_call_vol_ratio = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else 0
        
        return {
            "ticker": ticker_symbol,
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "total_call_vol": int(total_call_vol),
            "total_put_vol": int(total_put_vol),
            "put_call_oi_ratio": put_call_oi_ratio,
            "put_call_vol_ratio": put_call_vol_ratio,
            "expirations_analyzed": list(target_expirations),
            "status": "success"
        }
        
    except Exception as e:
        print(f"Error fetching options for {ticker_symbol}: {e}", file=sys.stderr)
        return {"ticker": ticker_symbol, "status": "error", "error": str(e)}

def main():
    ap = argparse.ArgumentParser(description="Fetch near-term options sentiment.")
    ap.add_argument("--dry-run", action="store_true", help="Print instead of saving")
    args = ap.parse_args()

    print(f"Fetching options sentiment for {len(BENCHMARKS)} benchmarks...")
    
    results = {}
    total_successful = 0
    
    for narrative, ticker in BENCHMARKS.items():
        print(f"  {narrative:25s} [{ticker:5s}] ... ", end="", flush=True)
        data = fetch_options_sentiment(ticker)
        
        if data and data["status"] == "success":
            results[narrative] = data
            total_successful += 1
            print(f"OK (P/C OI: {data['put_call_oi_ratio']})")
        else:
            print("FAILED")
            
        # VERY strict throttle to avoid Yahoo IP bans when scraping chains
        time.sleep(3.0)
        
    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_benchmarks": len(BENCHMARKS),
        "successful": total_successful,
        "data": results
    }
    
    if args.dry_run:
        print("\n[DRY RUN] Output payload:")
        print(json.dumps(output, indent=2))
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved {total_successful} options sentiments to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
