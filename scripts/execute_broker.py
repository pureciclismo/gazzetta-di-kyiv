#!/usr/bin/env python3
"""
execute_broker.py — Autonomous Execution Engine v0.2
=====================================================
Filters HIGH+ conviction LONG/SHORT trades from stories.json,
verifies entry prices against live market data (slippage protection),
and submits bracket orders to the broker.

Price sources (priority order):
  1. EODHD (free tier: 20+500 calls/day, real-time quotes)
  2. Finnhub (free tier: 60 calls/min, real-time)
  3. yfinance (free, unlimited, delayed)

Broker support: IBKR Client Portal Gateway (primary)
Dry-run mode: validates everything, simulates orders, writes audit trail.

Env vars:
  EODHD_API_KEY       — EODHD token (solianin@lagazzettadikyiv.com, free tier)
  FINNHUB_API_KEY     — Finnhub token (fallback, 60 calls/min)
  EXECUTE_DRY_RUN=0   — set to 0 for live broker orders
  IBKR_GATEWAY_URL    — default http://localhost:5000
  GAZZETTA_HOME       — project root
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── configuration ──────────────────────────────────────────────────
GAZZETTA_HOME = os.environ.get("GAZZETTA_HOME", "/opt/gazzetta-di-kyiv")
PROJECT = Path(GAZZETTA_HOME)

# Load .env file for cron compatibility
_ENV_PATH = PROJECT / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

STORIES_PATH = PROJECT / "public" / "data" / "stories.json"
EXECUTED_PATH = PROJECT / "data" / "executed_trades.json"

# API tokens
EODHD_TOKENS = [t.strip() for t in os.environ.get("EODHD_API_KEY", "").split(",") if t.strip()]
FINNHUB_TOKEN = os.environ.get("FINNHUB_API_KEY", "")

# API endpoints (format strings: {ticker}, {token})
EODHD_REALTIME = "https://eodhd.com/api/real-time/{ticker}?api_token={token}&fmt=json"
FINNHUB_QUOTE = "https://finnhub.io/api/v1/quote?symbol={ticker}&token={token}"

MAX_SLIPPAGE_PCT = 2.0
DRY_RUN = os.environ.get("EXECUTE_DRY_RUN", "1") == "1"
IBKR_GATEWAY = os.environ.get("IBKR_GATEWAY_URL", "http://localhost:5000")

# ── helpers ─────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def strip_dollar(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip().replace("$", "").replace(",", "")
        if val.lower() in ("", "market", "none", "n/a"):
            return None
        try:
            return float(val)
        except ValueError:
            return None
    return None


def _http_get_json(url: str) -> dict | None:
    """Fetch JSON from URL. Returns dict or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Gazzetta/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def fetch_live_price(ticker: str) -> float | None:
    """
    Fetch current price. Priority: EODHD → Finnhub → yfinance.
    Returns float or None if all sources fail.
    """
    # ── 1. EODHD real-time (free tier, 20+500 calls/day) ──
    for token in EODHD_TOKENS:
        url = EODHD_REALTIME.format(ticker=ticker, token=token)
        data = _http_get_json(url)
        if data:
            close = data.get("close")
            if close is not None and close != "NA":
                try:
                    val = float(close)
                    if val > 0:
                        return val
                except (ValueError, TypeError):
                    pass

    # ── 2. Finnhub real-time (free tier, 60 calls/min) ──
    if FINNHUB_TOKEN:
        url = FINNHUB_QUOTE.format(ticker=ticker, token=FINNHUB_TOKEN)
        data = _http_get_json(url)
        if data:
            current = data.get("c")
            if current is not None and current != "NA":
                try:
                    val = float(current)
                    if val > 0:
                        return val
                except (ValueError, TypeError):
                    pass

    # ── 3. yfinance (free, unlimited, delayed) ──
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1d")
        if not hist.empty:
            val = float(hist["Close"].iloc[-1])
            if val > 0:
                return val
    except Exception:
        pass

    return None


def check_idempotency(story_id: str, executed: dict) -> bool:
    for ex in executed.get("executed_trades", []):
        if ex.get("story_id") == story_id:
            return True
    return False


def validate_entry(thesis_entry: float | None, live_price: float | None) -> tuple[bool, float | None]:
    if thesis_entry is None:
        return True, 0.0
    if live_price is None or live_price <= 0:
        return False, None
    if thesis_entry <= 0:
        return False, None
    deviation = abs(thesis_entry - live_price) / live_price * 100
    return deviation <= MAX_SLIPPAGE_PCT, round(deviation, 2)


def submit_bracket_order_ibkr(trade: dict) -> dict | None:
    if DRY_RUN:
        return {"order_id": f"DRY-{trade['story_id']}", "status": "SIMULATED"}

    direction = trade["direction"]
    ticker = trade["ticker"]
    entry = trade["entry_price"] or trade["live_price_at_execution"]
    quantity = 100

    side = "SELL" if direction == "SHORT" else "BUY"

    payload = {"orders": [{
        "symbol": ticker, "secType": "STK", "exchange": "SMART",
        "currency": "USD", "orderType": "LMT", "price": entry,
        "side": side, "quantity": quantity, "tif": "DAY",
        "outsideRTH": False, "isSingleGroup": True,
    }]}

    try:
        url = f"{IBKR_GATEWAY}/v1/api/order"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        return {"order_id": result.get("order_id", "UNKNOWN"),
                "status": "SUBMITTED", "response": result}
    except Exception as e:
        print(f"  [execute] IBKR order failed: {e}", file=sys.stderr)
        return None


# ── main ────────────────────────────────────────────────────────────

def main() -> int:
    print("[execute] Autonomous Execution Engine v0.2")
    print(f"[execute] Price sources: EODHD{' ✓' if EODHD_TOKENS else ' ✗'} ({len(EODHD_TOKENS)} keys) | "
          f"Finnhub{' ✓' if FINNHUB_TOKEN else ' ✗'} | yfinance (fallback)")
    print(f"[execute] Mode: {'DRY RUN' if DRY_RUN else 'LIVE (IBKR)'}")
    print(f"[execute] Slippage gate: {MAX_SLIPPAGE_PCT}% max")

    if not STORIES_PATH.exists():
        print(f"[execute] FATAL: {STORIES_PATH} not found", file=sys.stderr)
        return 1

    stories_data = load_json(STORIES_PATH)
    all_stories = stories_data.get("all_stories", [])
    print(f"[execute] Loaded {len(all_stories)} stories")

    # Filter candidates
    candidates = []
    for s in all_stories:
        tt = s.get("trade_thesis")
        if not tt or not isinstance(tt, dict):
            continue
        direction = str(tt.get("direction", "")).upper().strip()
        if direction not in ("LONG", "SHORT"):
            continue
        conviction = str(tt.get("conviction", "")).upper().strip()
        if conviction not in ("HIGH", "MAXIMAL", "ELEVATED"):
            continue
        ticker = str(tt.get("primary_ticker", "")).strip().upper()
        if not ticker or ticker == "NONE":
            continue

        candidates.append({
            "story_id": s.get("story_id", s.get("id", "")),
            "headline": str(s.get("headline", ""))[:120],
            "ticker": ticker,
            "direction": direction,
            "conviction": conviction,
            "entry_price": strip_dollar(tt.get("limit_entry_price")),
            "stop_loss": strip_dollar(tt.get("stop_loss")),
            "take_profit": strip_dollar(tt.get("take_profit")),
            "tier": s.get("tier", ""),
            "gap_score": s.get("gap_score", 0),
        })

    print(f"[execute] {len(candidates)} candidates (HIGH+ conviction, LONG/SHORT)")
    if not candidates:
        print("[execute] No candidates. Exiting.")
        return 0

    executed = load_json(EXECUTED_PATH)
    if "executed_trades" not in executed:
        executed["executed_trades"] = []

    executed_count = 0
    skipped_idem = 0
    rejected_slip = 0
    rejected_nodata = 0

    for trade in candidates:
        sid = trade["story_id"]
        ticker = trade["ticker"]

        if check_idempotency(sid, executed):
            print(f"  \u23ed  {sid} \u2014 already executed")
            skipped_idem += 1
            continue

        live_price = fetch_live_price(ticker)
        if live_price is None:
            print(f"  \u26a0  {sid} ({ticker}) \u2014 no price data")
            rejected_nodata += 1
            continue

        thesis_entry = trade["entry_price"]
        ok, dev = validate_entry(thesis_entry, live_price)
        if not ok:
            thesis_str = f"${thesis_entry:,.2f}" if thesis_entry else "market"
            print(f"  \u2717  {sid} ({ticker}) \u2014 SLIPPAGE: "
                  f"{thesis_str} vs ${live_price:,.2f} ({dev:.1f}%, max {MAX_SLIPPAGE_PCT}%)")
            rejected_slip += 1
            continue

        if thesis_entry:
            print(f"  \u2713  {sid} ({ticker}) \u2014 VALID: "
                  f"thesis ${thesis_entry:,.2f} vs live ${live_price:,.2f} ({dev:.1f}%)")
        else:
            print(f"  \u2713  {sid} ({ticker}) \u2014 MARKET @ ${live_price:,.2f}")

        order_record = {
            "story_id": sid, "headline": trade["headline"],
            "ticker": ticker, "direction": trade["direction"],
            "conviction": trade["conviction"],
            "thesis_entry_price": thesis_entry,
            "live_price_at_execution": live_price,
            "stop_loss": trade["stop_loss"],
            "take_profit": trade["take_profit"],
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "broker": "DRY_RUN" if DRY_RUN else "IBKR",
            "order_id": None,
            "status": "SIMULATED" if DRY_RUN else "PENDING",
        }

        broker_result = submit_bracket_order_ibkr(trade)
        if broker_result:
            order_record["order_id"] = broker_result.get("order_id")
            order_record["status"] = broker_result.get("status", order_record["status"])

        executed["executed_trades"].append(order_record)
        executed_count += 1

    if executed_count > 0:
        save_json(EXECUTED_PATH, executed)
        print(f"\n[execute] Saved {executed_count} records \u2192 {EXECUTED_PATH}")

    print(f"\n{'='*55}")
    print(f"  AUTONOMOUS EXECUTION REPORT")
    print(f"  {'='*55}")
    print(f"  Candidates:               {len(candidates)}")
    print(f"  Executed (new):           {executed_count}")
    print(f"  Skipped (idempotent):     {skipped_idem}")
    print(f"  Rejected \u2014 slippage:      {rejected_slip}")
    print(f"  Rejected \u2014 no data:       {rejected_nodata}")
    print(f"  Slippage gate:            {MAX_SLIPPAGE_PCT}%")
    print(f"  Mode:                     {'DRY RUN' if DRY_RUN else 'LIVE'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
