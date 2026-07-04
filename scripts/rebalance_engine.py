import json
import os
import yfinance as yf
import datetime

DATA_DIR = os.environ.get("GAZZETTA_DATA_DIR", "data")
DRIFT_THRESHOLD = 0.05  # 5% drift threshold

def load_portfolios():
    filepath = os.path.join(DATA_DIR, "portfolios.json")
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return []
    with open(filepath, "r") as f:
        return json.load(f)

def get_returns_30d(tickers):
    data = {}
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            hist = ticker_obj.history(period="2mo")
            if len(hist) < 30:
                data[t] = 1.0
                continue
            current_price = float(hist["Close"].iloc[-1])
            price_30d_ago = float(hist["Close"].iloc[-30])
            if price_30d_ago > 0:
                data[t] = current_price / price_30d_ago
            else:
                data[t] = 1.0
        except Exception:
            data[t] = 1.0
    return data

def run_rebalance_engine():
    portfolios = load_portfolios()
    if not portfolios:
        return

    all_tickers = set()
    for p in portfolios:
        for c in p.get("constituents", []):
            all_tickers.add(c["ticker"])
            
    returns_data = get_returns_30d(list(all_tickers))
    
    logs = []
    log_path = os.path.join(DATA_DIR, "rebalance_log.json")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    today_str = datetime.date.today().isoformat()

    for p in portfolios:
        narrative_id = p.get("narrative_id")
        constituents = p.get("constituents", [])
        
        # Simulate current weight assuming it was perfectly balanced 30 days ago
        simulated_value = 0.0
        for c in constituents:
            t = c["ticker"]
            tw = c.get("target_weight", 0)
            ret = returns_data.get(t, 1.0)
            c["current_value"] = tw * ret
            simulated_value += c["current_value"]
            
        max_drift = 0.0
        drifted_asset = None
        
        for c in constituents:
            cw = c["current_value"] / simulated_value if simulated_value > 0 else 0
            tw = c.get("target_weight", 0)
            drift = abs(cw - tw)
            if drift > max_drift:
                max_drift = drift
                drifted_asset = c["ticker"]
                
        # Evaluate triggers
        if max_drift > DRIFT_THRESHOLD:
            log_entry = {
                "date": today_str,
                "narrative_id": narrative_id,
                "trigger_type": "DRIFT",
                "max_drift": max_drift,
                "drifted_asset": drifted_asset,
                "action": "REBALANCE_REQUIRED",
                "details": f"Max drift of {max_drift:.2%} exceeded {DRIFT_THRESHOLD:.2%} threshold on {drifted_asset}"
            }
            logs.append(log_entry)
            print(f"[{narrative_id}] REBALANCE TRIGGERED: Drift {max_drift:.2%} on {drifted_asset}")
        else:
            print(f"[{narrative_id}] No rebalance needed. Max drift: {max_drift:.2%}")

    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)
        
    print(f"Rebalance evaluation complete. Logged to {log_path}")

if __name__ == "__main__":
    run_rebalance_engine()
