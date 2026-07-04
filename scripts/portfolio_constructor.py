import json
import os
import yfinance as yf
import pandas as pd
import numpy as np

DATA_DIR = os.environ.get("GAZZETTA_DATA_DIR", "data")

def load_narrative_graph():
    filepath = os.path.join(DATA_DIR, "narrative_graph.json")
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found. Returning empty graph.")
        return []
    with open(filepath, "r") as f:
        return json.load(f)

def get_historical_returns(tickers, period="1y"):
    if not tickers:
        return pd.DataFrame()
    data = yf.download(tickers, period=period, interval="1d", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        # yfinance behavior for multiple tickers
        close = data["Close"]
    else:
        close = pd.DataFrame({tickers[0]: data["Close"]})
    returns = close.pct_change().dropna()
    return returns

def calculate_erc_weights(returns):
    """
    Approximates Equal Risk Contribution using Inverse Volatility.
    In a true ERC, risk contribution w_i * (Cov * w)_i is equalized.
    Inverse vol is a common proxy when correlations are assumed uniform.
    """
    vols = returns.std()
    inv_vols = 1.0 / vols
    return inv_vols / inv_vols.sum()

def construct_portfolios():
    narratives = load_narrative_graph()
    portfolios = []

    for narrative_id, narrative in narratives.items():
        assets = narrative.get("assets", [])
        if not assets:
            continue
        
        tickers = [a["ticker"] for a in assets if "ticker" in a]
        returns = get_historical_returns(tickers)
        
        if returns.empty:
            continue
            
        target_vol = 0.15 # 15% Volatility Target
        
        # 1. Bucket by instrument_type (asset class)
        buckets = {}
        for a in assets:
            b_type = a.get("instrument_type", "Equity")
            if b_type not in buckets:
                buckets[b_type] = []
            buckets[b_type].append(a)
            
        # 2. ERC within buckets and 3. Narrative Purity Weighting across buckets
        # For simplicity, we calculate inverse vol weights for all, then multiply by purity.
        asset_weights = {}
        if not returns.empty:
            vols = returns.std() * np.sqrt(252) # Annualized vol
            inv_vols = 1.0 / vols
            erc_weights_raw = inv_vols / inv_vols.sum()
            
            # Combine ERC with Purity
            unnormalized_weights = {}
            for a in assets:
                ticker = a["ticker"]
                if ticker in erc_weights_raw:
                    purity = a.get("purity_weight", 1.0)
                    unnormalized_weights[ticker] = erc_weights_raw[ticker] * purity
            
            total_weight = sum(unnormalized_weights.values())
            for ticker, w in unnormalized_weights.items():
                asset_weights[ticker] = w / total_weight

        # 4. Volatility Targeting (to 15%)
        # Calculate portfolio variance
        cov_matrix = returns.cov() * 252
        weights_array = np.array([asset_weights.get(t, 0) for t in returns.columns])
        if sum(weights_array) > 0:
            port_var = weights_array.T @ cov_matrix @ weights_array
            port_vol = np.sqrt(port_var)
            
            # Leverage factor to hit 15% vol
            if port_vol > 0:
                lev_factor = target_vol / port_vol
            else:
                lev_factor = 1.0
            
            # Final weights
            final_weights = {t: w * lev_factor for t, w in asset_weights.items()}
        else:
            final_weights = {}
            port_vol = 0
            
        portfolio = {
            "narrative_id": narrative_id,
            "target_volatility": target_vol,
            "historical_volatility": float(port_vol),
            "constituents": []
        }
        
        for a in assets:
            t = a["ticker"]
            if t in final_weights:
                portfolio["constituents"].append({
                    "ticker": t,
                    "target_weight": float(final_weights[t]),
                    "instrument_type": a.get("instrument_type", "Unknown"),
                    "purity_weight": a.get("purity_weight", 1.0),
                    "role": a.get("role", "Core")
                })
        
        portfolios.append(portfolio)

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, "portfolios.json")
    with open(out_path, "w") as f:
        json.dump(portfolios, f, indent=2)
    print(f"Generated {len(portfolios)} portfolios in {out_path}")

if __name__ == "__main__":
    construct_portfolios()
