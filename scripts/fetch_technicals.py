#!/usr/bin/env python3
"""
fetch_technicals.py — Tactical Horizon Indicators Fetcher

Scrapes Twelve Data for RSI, MACD, and ATR for the 12 core narrative benchmarks.
Strictly throttles to 8 requests per minute to comply with the free tier limits.

Usage:
  python3 scripts/fetch_technicals.py
"""

import json
import os
import sys
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
OUTPUT_FILE = DATA_DIR / "technicals.json"
API_KEYS_ENV = os.environ.get("TWELVEDATA_API_KEY", "")
API_KEYS = [k.strip() for k in API_KEYS_ENV.split(",") if k.strip()]

# Single highly liquid benchmark per narrative
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

def fetch_indicator(symbol: str, indicator: str, params: dict, api_key: str):
    """Fetch a single technical indicator from Twelve Data, handling limits."""
    if not api_key:
        return {"error": "TWELVEDATA_API_KEY not set"}
        
    base_url = f"https://api.twelvedata.com/{indicator}"
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{base_url}?symbol={symbol}&interval=1day&apikey={api_key}&{qs}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GazzettaVault/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if "status" in data and data["status"] == "error":
                return {"error": data.get("message", "Twelve Data API error")}
            return data
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def extract_latest(data_response: dict, keys: list):
    """Extract the most recent indicator values from the time series."""
    if "values" not in data_response or not data_response["values"]:
        return {k: None for k in keys}
    
    latest = data_response["values"][0]
    return {k: float(latest.get(k, 0)) for k in keys}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print instead of saving")
    args = ap.parse_args()

    if not API_KEYS and not args.dry_run:
        print("❌ TWELVEDATA_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(0)

    # 12 tickers * 3 indicators = 36 calls
    DELAY = 8.0 / len(API_KEYS) if API_KEYS else 8.0
    key_idx = 0
    
    def next_key():
        nonlocal key_idx
        if not API_KEYS: return ""
        k = API_KEYS[key_idx % len(API_KEYS)]
        key_idx += 1
        return k

    print(f"Fetching Twelve Data Technicals for {len(BENCHMARKS)} benchmarks...")
    print(f"Using {len(API_KEYS)} API key(s). Throttling to 1 request per {DELAY:.1f} seconds...")
    
    results = {}
    total_successful = 0
    
    for narrative, ticker in BENCHMARKS.items():
        print(f"\n[ {ticker:5s} ] {narrative}")
        ticker_data = {"ticker": ticker, "status": "success"}
        
        # 1. RSI (Momentum)
        rsi_resp = fetch_indicator(ticker, "rsi", {"time_period": 14}, next_key())
        if "error" in rsi_resp:
            print(f"  ⚠ RSI failed: {rsi_resp['error']}")
            ticker_data["status"] = "partial_error"
        else:
            rsi_val = extract_latest(rsi_resp, ["rsi"])
            ticker_data["rsi_14d"] = rsi_val.get("rsi")
            print(f"  RSI:  {ticker_data['rsi_14d']}")
        
        time.sleep(DELAY)
        
        # 2. MACD (Trend)
        macd_resp = fetch_indicator(ticker, "macd", {"fast_period": 12, "slow_period": 26, "signal_period": 9}, next_key())
        if "error" in macd_resp:
            print(f"  ⚠ MACD failed: {macd_resp['error']}")
            ticker_data["status"] = "partial_error"
        else:
            macd_val = extract_latest(macd_resp, ["macd", "macd_signal", "macd_hist"])
            ticker_data["macd"] = macd_val.get("macd")
            ticker_data["macd_signal"] = macd_val.get("macd_signal")
            ticker_data["macd_hist"] = macd_val.get("macd_hist")
            print(f"  MACD: {ticker_data['macd']} (Hist: {ticker_data['macd_hist']})")
            
        time.sleep(DELAY)
        
        # 3. ATR (Volatility)
        atr_resp = fetch_indicator(ticker, "atr", {"time_period": 14}, next_key())
        if "error" in atr_resp:
            print(f"  ⚠ ATR failed: {atr_resp['error']}")
            ticker_data["status"] = "partial_error"
        else:
            atr_val = extract_latest(atr_resp, ["atr"])
            ticker_data["atr_14d"] = atr_val.get("atr")
            print(f"  ATR:  {ticker_data['atr_14d']}")
            
        time.sleep(DELAY)
        
        results[narrative] = ticker_data
        if ticker_data["status"] == "success":
            total_successful += 1

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
        print(f"\nSaved {total_successful} full technical profiles to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
