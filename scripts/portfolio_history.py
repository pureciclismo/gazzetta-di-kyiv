import json
import os
import yfinance as yf
import pandas as pd
import datetime

DATA_DIR = os.environ.get("GAZZETTA_DATA_DIR", "data")
DEBASEMENT_HURDLE = 0.08
ASSUMED_CPI = 0.03 # Placeholder for CPI (3%)

def load_portfolios():
    filepath = os.path.join(DATA_DIR, "portfolios.json")
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return []
    with open(filepath, "r") as f:
        return json.load(f)

def get_market_caps_and_prices(tickers):
    data = {}
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            # info can be slow or missing, fallback to recent history if market cap not available
            info = ticker_obj.info
            mc = info.get("marketCap", 0)
            
            # Get last 35 days to ensure we have 30 trading days ago
            hist = ticker_obj.history(period="2mo")
            if hist.empty:
                continue
                
            current_price = float(hist["Close"].iloc[-1])
            price_30d_ago = float(hist["Close"].iloc[-30]) if len(hist) >= 30 else current_price
            
            # If market cap is 0 (e.g., for some ETFs or futures), approximate or set to 1 for relative sizing
            if mc == 0:
                mc = info.get("totalAssets", 1e9) # Default to 1B if unknown
            
            data[t] = {
                "market_cap": mc,
                "current_price": current_price,
                "price_30d_ago": price_30d_ago
            }
        except Exception as e:
            print(f"Error fetching data for {t}: {e}")
    return data

def compute_history():
    portfolios = load_portfolios()
    if not portfolios:
        return

    all_tickers = set()
    for p in portfolios:
        for c in p.get("constituents", []):
            all_tickers.add(c["ticker"])
            
    market_data = get_market_caps_and_prices(list(all_tickers))
    
    today_str = datetime.date.today().isoformat()
    history_entries = []

    for p in portfolios:
        narrative_id = p.get("narrative_id")
        current_nmc = 0.0
        nmc_30d_ago = 0.0
        
        for c in p.get("constituents", []):
            t = c["ticker"]
            purity = c.get("purity_weight", 1.0)
            if t in market_data:
                md = market_data[t]
                # NMC = sum(Market Cap * Purity Weight)
                current_nmc += md["market_cap"] * purity
                
                # To calculate past NMC, adjust current market cap by the price ratio
                price_ratio = md["price_30d_ago"] / md["current_price"] if md["current_price"] > 0 else 1.0
                nmc_30d_ago += (md["market_cap"] * price_ratio) * purity

        if nmc_30d_ago > 0:
            momentum_30d = current_nmc / nmc_30d_ago
            return_30d = momentum_30d - 1.0
        else:
            momentum_30d = 1.0
            return_30d = 0.0
            
        # Debasement adjusted return: return - hurdle - CPI (annualized adjustment for 30d = roughly 1/12th)
        # Using monthly approximations for 8% and 3%
        monthly_hurdle = DEBASEMENT_HURDLE / 12
        monthly_cpi = ASSUMED_CPI / 12
        debasement_adj_return = return_30d - monthly_hurdle - monthly_cpi

        entry = {
            "date": today_str,
            "narrative_id": narrative_id,
            "nmc": current_nmc,
            "momentum_30d": momentum_30d,
            "return_30d": return_30d,
            "debasement_adjusted_return_30d": debasement_adj_return
        }
        history_entries.append(entry)
        
    os.makedirs(DATA_DIR, exist_ok=True)
    history_path = os.path.join(DATA_DIR, "nmc_history.jsonl")
    
    with open(history_path, "a") as f:
        for entry in history_entries:
            f.write(json.dumps(entry) + "\n")
            
    print(f"Appended {len(history_entries)} records to {history_path}")

if __name__ == "__main__":
    compute_history()
