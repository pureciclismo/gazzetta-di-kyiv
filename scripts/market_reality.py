#!/usr/bin/env python3
"""
market_reality.py -- Financial price fetcher with yfinance -> AlphaVantage fallback.

Primary:   yfinance (free, fast, no key)
Fallback:  AlphaVantage REST API (requires ALPHAVANTAGE_API_KEY in env)

Ticker-to-narrative mapping for the Contradiction Gap calculation. When
yfinance times out or rate-limits, the call seamlessly cascades to
AlphaVantage so the pipeline never stalls on a single provider ban.

Usage:
  python3 market_reality.py --all
  python3 market_reality.py --ticker URA GLD ITA
  python3 market_reality.py --ticker URA --output /tmp/prices.json
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── external deps ───────────────────────────────────────────────────
import yfinance as yf
import requests

# ── config ──────────────────────────────────────────────────────────
PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
OUTPUT_FILE = DATA_DIR / "market_prices.json"

ALPHAVANTAGE_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")
AV_URL = "https://www.alphavantage.co/query"
FINNHUB_URL = "https://finnhub.io/api/v1/quote"

AV_DELAY = 13.0    # free tier: 5 calls/min
FINNHUB_DELAY = 1.1 # free tier: 60 calls/min
YF_TIMEOUT = 15
AV_TIMEOUT = 10
FINNHUB_TIMEOUT = 10

# Narrative -> ticker mapping (aligned with Strategic Architecture Report)
NARRATIVE_TICKERS = {
    "critical_resource_control": ["XOM", "CVX", "CCJ", "URNM"],
    "dollar_decline":     ["EURUSD=X", "GLD", "SLV", "UUP", "BTC-USD", "IAU"],
    "deglobalization":    ["CAT", "GE", "XLI", "RTX"],
    "china_ascent":       ["BABA", "FXI", "MCHI", "KWEB", "PDD"],
    "space_economy":      ["RKLB", "ARKX", "LMT", "UFO"],
    "gene_editing":       ["CRSP", "ARKG", "XBI"],
    "tech_convergence":   ["MSFT", "GOOGL", "NVDA", "ORCL"],
    "wealthy_sports":     ["BATRK", "MSGS", "MANU"],  # Real prestige assets
    "ai_chips":           ["NVDA", "AMD", "SMH"],
    "crypto_reserve":     ["BTC-USD", "MSTR", "COIN"],
    "rate_cycle":         ["TLT", "IEF", "SHY"],
    "commodity_supercycle": ["XOM", "CAT", "DBC", "COP"],
}

BENCHMARKS = ["SPY", "QQQ", "DX-Y.NYB", "TLT", "^VIX"]


# ── providers ───────────────────────────────────────────────────────
def _ts():
    return datetime.now(timezone.utc).isoformat()


def fetch_finnhub(ticker):
    """Finnhub real-time quote (60/min free tier). Returns dict or None."""
    if not FINNHUB_KEY:
        return None
    try:
        r = requests.get(FINNHUB_URL, params={
            "symbol": ticker,
            "token": FINNHUB_KEY,
        }, timeout=FINNHUB_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        
        # Finnhub returns 'c' for current price, 'pc' for previous close
        price = float(data.get("c", 0))
        prev = float(data.get("pc", 0))
        
        if price == 0:
            return None
            
        change = None
        if prev and prev > 0:
            change = round(((price - prev) / prev) * 100, 2)
            
        return {
            "ticker": ticker,
            "price": round(price, 2),
            "previous_close": round(prev, 2) if prev else None,
            "change_pct": change,
            "source": "finnhub",
            "fetched_at": _ts(),
        }
    except Exception as e:
        print(f"  finnhub err {ticker}: {type(e).__name__}", file=sys.stderr)
        return None


def fetch_yahoo(ticker):
    """yfinance fast_info + 2-day history fallback. Returns dict or None."""
    try:
        t = yf.Ticker(ticker)
        price = prev_close = None

        # fast path
        try:
            fi = t.fast_info
            price = fi.last_price if hasattr(fi, "last_price") else fi.regular_market_previous_close
            prev_close = getattr(fi, "regular_market_previous_close", None)
        except Exception:
            pass

        # history fallback
        if price is None:
            hist = t.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if len(hist) > 1:
                    prev_close = float(hist["Close"].iloc[-2])

        if price is None:
            return None

        change = None
        if prev_close and prev_close > 0:
            change = round(((price - prev_close) / prev_close) * 100, 2)

        # AUM / total assets (for capital_volume_usd)
        aum = None
        try:
            aum = getattr(fi, "total_assets", None)
        except Exception:
            pass

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "previous_close": round(prev_close, 2) if prev_close else None,
            "change_pct": change,
            "aum": aum,
            "source": "yfinance",
            "fetched_at": _ts(),
        }
    except Exception as e:
        print(f"  yfinance err {ticker}: {type(e).__name__}", file=sys.stderr)
        return None


def fetch_alphavantage(ticker):
    """AlphaVantage GLOBAL_QUOTE. Returns dict or None."""
    if not ALPHAVANTAGE_KEY:
        return None
    try:
        r = requests.get(AV_URL, params={
            "function": "GLOBAL_QUOTE",
            "symbol": ticker,
            "apikey": ALPHAVANTAGE_KEY,
        }, timeout=AV_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        q = data.get("Global Quote", {})
        if not q:
            note = data.get("Note", "")
            if note:
                print(f"  av note {ticker}: {note[:80]}", file=sys.stderr)
            return None
        price = float(q.get("05. price", 0))
        prev = float(q.get("08. previous close", 0))
        chg = q.get("10. change percent", "0%").replace("%", "")
        if price == 0:
            return None
        return {
            "ticker": ticker,
            "price": round(price, 2),
            "previous_close": round(prev, 2) if prev else None,
            "change_pct": float(chg) if chg else None,
            "source": "alphavantage",
            "fetched_at": _ts(),
        }
    except Exception as e:
        print(f"  av err {ticker}: {type(e).__name__}", file=sys.stderr)
        return None


def fetch_price(ticker, av_delay=False, finnhub_delay=False):
    """Finnhub primary, yfinance secondary, AlphaVantage fallback. Returns dict or None."""
    if finnhub_delay:
        time.sleep(FINNHUB_DELAY)
        
    result = fetch_finnhub(ticker)
    if result:
        return result
        
    result = fetch_yahoo(ticker)
    if result:
        return result
        
    if av_delay:
        time.sleep(AV_DELAY)
    return fetch_alphavantage(ticker)


# ── batch ───────────────────────────────────────────────────────────
def fetch_all():
    seen = set()
    tickers = []
    for narrative, tl in NARRATIVE_TICKERS.items():
        for t in tl:
            if t not in seen:
                tickers.append((t, narrative))
                seen.add(t)
    for t in BENCHMARKS:
        if t not in seen:
            tickers.append((t, "benchmark"))
            seen.add(t)

    results, failures, av_used = {}, [], False
    for i, (ticker, narrative) in enumerate(tickers):
        print(f"  {ticker:6s} ({narrative:22s})", end=" ", flush=True)

        # delay for finnhub on every call after the first, delay for av if the *previous* call used av
        finnhub_used = i > 0
        result = fetch_price(ticker, av_delay=av_used, finnhub_delay=finnhub_used)
        av_used = bool(result and result.get("source") == "alphavantage")

        if result:
            result["narrative"] = narrative
            results[ticker] = result
            chg = result.get("change_pct")
            chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
            print(f"${result['price']:>10.2f}  {chg_str:>8s}  [{result['source']}]")
        else:
            if narrative != "benchmark":
                failures.append(ticker)
            print("FAILED")

        if i < len(tickers) - 1:
            time.sleep(0.5)

    return results, failures


def save_output(results, failures, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _ts(),
        "total": len(results) + len(failures),
        "success": len(results),
        "failed": len(failures),
        "failed_tickers": failures,
        "prices": results,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nwrote {len(results)} prices to {path}")
    if failures:
        print(f"FAILURES ({len(failures)}): {', '.join(failures)}")


# ── main ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Market reality: fetch prices with yfinance -> AlphaVantage fallback"
    )
    ap.add_argument("--ticker", nargs="*", help="Specific tickers (e.g. URA GLD FXI)")
    ap.add_argument("--all", action="store_true", help="Fetch all narrative tickers + benchmarks")
    ap.add_argument("--output", help="Output JSON (default: data/market_prices.json)")
    args = ap.parse_args()

    out = Path(args.output) if args.output else OUTPUT_FILE

    if args.ticker:
        print(f"fetching {len(args.ticker)} ticker(s)...")
        results, failures = {}, []
        av_flag = False
        for i, raw in enumerate(args.ticker):
            t = raw.upper().strip()
            print(f"  {t:6s}", end=" ", flush=True)
            finnhub_flag = i > 0
            r = fetch_price(t, av_delay=av_flag, finnhub_delay=finnhub_flag)
            av_flag = bool(r and r.get("source") == "alphavantage")
            if r:
                results[t] = r
                chg = r.get("change_pct")
                s = f"{chg:+.2f}%" if chg is not None else "N/A"
                print(f"${r['price']:>10.2f}  {s:>8s}  [{r['source']}]")
            else:
                failures.append(t)
                print("FAILED")
            if i < len(args.ticker) - 1:
                time.sleep(0.5)
        save_output(results, failures, out)

    elif args.all:
        print(f"fetching all narrative tickers + benchmarks...")
        results, failures = fetch_all()
        save_output(results, failures, out)

    else:
        ap.print_help()
        sys.exit(0)

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
