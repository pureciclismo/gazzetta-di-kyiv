#!/usr/bin/env python3
"""
fetch_cftc_financial.py — CFTC Traders in Financial Futures (TIFF) via Bulk ZIP
==============================================================================
Downloads the weekly TIFF report ZIP, extracts the XLS, filters for our 8 target
financial contracts, and outputs cftc_financial_positions.json in the same schema
as the physical COT data.

Data source: https://www.cftc.gov/files/dea/history/fut_fin_xls_2026.zip
Report:      Traders in Financial Futures (TIFF) — separate from Disaggregated COT
Schedule:    Weekly (released Tuesday/Wednesday after 15:30 ET).
Cache:       48 hours — data is weekly, don't re-download 4.5MB every cycle.
             Protects VM bandwidth and prevents CFTC IP throttling.

Targets:     Currencies (dollar_decline), Treasuries (rate_cycle), Equities (tech_convergence)
"""

import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlretrieve
import ssl

# -- config ----------------------------------------------------------
PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TIFF_URL = "https://www.cftc.gov/files/dea/history/fut_fin_xls_2026.zip"
ZIP_PATH = DATA_DIR / "cftc_financial_tiff.zip"
XLS_PATH = DATA_DIR / "cftc_financial_tiff.xls"
OUTPUT_FILE = DATA_DIR / "cftc_financial_positions.json"
CACHE_HOURS = 48  # Only re-download every 48 hours (data is weekly)
REQUEST_TIMEOUT = 60

# Proxy config
SCRAPE_DO_TOKEN = os.environ.get("SCRAPE_DO_TOKEN", "0225f0e590eb4864bc7ef73765e97a980e02888fae1")

# -- Target financial contracts ---------------------------------------
# Verified against live FinFutYY.xls (June 27, 2026).
# TIFF uses Lev_Money (hedge funds/CTAs) as the speculative positioning signal.
# Map each contract to a Gazzetta narrative, ticker, and human-readable label.
FINANCIAL_CONTRACTS = [
    # --- dollar_decline: currency futures = anti-dollar positioning ---
    {"cftc_code": "099741", "ticker": "6E",  "narrative": "dollar_decline", "label": "Euro FX (6E)"},
    {"cftc_code": "097741", "ticker": "6J",  "narrative": "dollar_decline", "label": "Japanese Yen (6J)"},
    {"cftc_code": "096742", "ticker": "6B",  "narrative": "dollar_decline", "label": "British Pound (6B)"},

    # --- rate_cycle: Treasury futures = duration/rate positioning ---
    {"cftc_code": "042601", "ticker": "ZT",  "narrative": "rate_cycle",     "label": "2-Year UST Note (ZT)"},
    {"cftc_code": "043602", "ticker": "ZN",  "narrative": "rate_cycle",     "label": "10-Year UST Note (ZN)"},
    {"cftc_code": "020601", "ticker": "ZB",  "narrative": "rate_cycle",     "label": "30-Year UST Bond (ZB)"},

    # --- tech_convergence: equity index futures = tech/systemic positioning ---
    {"cftc_code": "13874A", "ticker": "ES",  "narrative": "tech_convergence", "label": "E-Mini S&P 500 (ES)"},
    {"cftc_code": "209742", "ticker": "NQ",  "narrative": "tech_convergence", "label": "Nasdaq Mini (NQ)"},
]

# All narratives we populate via financial futures
FINANCIAL_NARRATIVES = ["dollar_decline", "rate_cycle", "tech_convergence"]


def safe_int(val):
    """Parse CFTC position values (floats/strings from XLS)."""
    if val is None or (isinstance(val, float) and pd.isna(val) if 'pd' in dir() else False):
        return 0
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return 0


def is_cache_valid():
    """Check if cached ZIP is recent enough to skip re-download."""
    if not ZIP_PATH.exists() or not XLS_PATH.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(ZIP_PATH.stat().st_mtime)
    return age < timedelta(hours=CACHE_HOURS)


def download_tiff():
    """Download the TIFF ZIP with browser-grade headers + exponential backoff.
    Returns True on success. Uses standard SSL (no cert bypass) to avoid WAF triggers."""
    import urllib.request
    import urllib.parse

    # Minimal headers for proxy routing
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    max_retries = 3
    base_delay = 5  # seconds

    # Attempt 1: scrape.do with retries
    for attempt in range(1, max_retries + 1):
        try:
            ctx = ssl.create_default_context()  # Proper TLS — no cert bypass
            proxy_url = f"https://api.scrape.do/?token={SCRAPE_DO_TOKEN}&url={urllib.parse.quote(TIFF_URL)}"
            print(f"[cftc_fin] Downloading TIFF ZIP via scrape.do (attempt {attempt}/{max_retries}, {CACHE_HOURS}h cache)...")

            req = urllib.request.Request(proxy_url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx)

            # urlopen raises HTTPError on 4xx/5xx — if we get here, status is 2xx
            with open(ZIP_PATH, "wb") as f:
                f.write(resp.read())

            # Extract XLS
            with zipfile.ZipFile(ZIP_PATH, "r") as zf:
                xls_names = [n for n in zf.namelist() if n.endswith(".xls")]
                if not xls_names:
                    raise ValueError("No .xls file found in ZIP")
                xls_name = xls_names[0]
                with zf.open(xls_name) as src, open(XLS_PATH, "wb") as dst:
                    dst.write(src.read())

            print(f"[cftc_fin] Downloaded + extracted via scrape.do: {xls_name}")
            return True

        except urllib.error.HTTPError as e:
            print(f"[cftc_fin] HTTP {e.code} on attempt {attempt}: {e.reason}", file=sys.stderr)
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                time.sleep(delay)
        except Exception as e:
            print(f"[cftc_fin] Download failed (attempt {attempt}): {e}", file=sys.stderr)
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                time.sleep(delay)

    # Attempt 2: Webshare proxy fallback
    print("[cftc_fin] scrape.do failed. Trying Webshare proxy fallback...")
    webshare_token = os.environ.get("WEBSHARE_API_KEY", "m63tjlsqiv03vwst6n1fzzcftz6cifeolhanx8x6")
    if webshare_token:
        try:
            req_ws = urllib.request.Request("https://proxy.webshare.io/api/v2/proxy/list/?mode=direct", 
                                            headers={"Authorization": f"Token {webshare_token}"})
            with urllib.request.urlopen(req_ws, timeout=15) as resp_ws:
                data = json.loads(resp_ws.read().decode())
                results = data.get("results", [])
                proxy_str = None
                for p in results:
                    if p.get("valid"):
                        user = p.get("username")
                        pwd = p.get("password")
                        ip = p.get("proxy_address")
                        port = p.get("port")
                        proxy_str = f"http://{user}:{pwd}@{ip}:{port}"
                        break
                
                if proxy_str:
                    print(f"[cftc_fin] Using Webshare proxy: {ip}:{port}")
                    ctx = ssl.create_default_context()
                    proxy_support = urllib.request.ProxyHandler({'http': proxy_str, 'https': proxy_str})
                    opener = urllib.request.build_opener(proxy_support)
                    urllib.request.install_opener(opener)
                    
                    req_direct = urllib.request.Request(TIFF_URL, headers=HEADERS)
                    with urllib.request.urlopen(req_direct, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
                        with open(ZIP_PATH, "wb") as f:
                            f.write(resp.read())
                    
                    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
                        xls_names = [n for n in zf.namelist() if n.endswith(".xls")]
                        if not xls_names:
                            raise ValueError("No .xls file found in ZIP")
                        xls_name = xls_names[0]
                        with zf.open(xls_name) as src, open(XLS_PATH, "wb") as dst:
                            dst.write(src.read())
                    print(f"[cftc_fin] Downloaded + extracted via Webshare proxy: {xls_name}")
                    return True
        except Exception as e:
            print(f"[cftc_fin] Webshare proxy fallback failed: {e}", file=sys.stderr)

    return False


def compute_summary(row):
    """Extract positioning fields from TIFF row into standard schema."""
    mm_long = safe_int(row.get("Lev_Money_Positions_Long_All"))
    mm_short = safe_int(row.get("Lev_Money_Positions_Short_All"))
    am_long = safe_int(row.get("Asset_Mgr_Positions_Long_All"))
    am_short = safe_int(row.get("Asset_Mgr_Positions_Short_All"))
    dlr_long = safe_int(row.get("Dealer_Positions_Long_All"))
    dlr_short = safe_int(row.get("Dealer_Positions_Short_All"))
    oi = safe_int(row.get("Open_Interest_All"))

    return {
        "managed_money_long": mm_long,     # Leveraged money = specs (hedge funds, CTAs)
        "managed_money_short": mm_short,
        "managed_money_net": mm_long - mm_short,
        "asset_mgr_long": am_long,         # Asset managers = institutional
        "asset_mgr_short": am_short,
        "asset_mgr_net": am_long - am_short,
        "dealer_long": dlr_long,           # Dealers = market makers / banks
        "dealer_short": dlr_short,
        "dealer_net": dlr_long - dlr_short,
        "total_open_interest": oi,
        "spec_pct_of_oi": round((mm_long / oi * 100), 1) if oi > 0 else 0,
        "report_date": str(row.get("Report_Date_as_MM_DD_YYYY", "")),
        "contract_market": str(row.get("Market_and_Exchange_Names", "")),
    }


def main():
    print("[cftc_fin] CFTC Financial Futures (TIFF) Ingest")

    # -- Cache check --------------------------------------------------
    if is_cache_valid():
        print(f"[cftc_fin] Cache valid (< {CACHE_HOURS}h old) — skipping download")
    else:
        if not download_tiff():
            # Non-blocking: use cached data if download fails
            if XLS_PATH.exists():
                print("[cftc_fin] Download failed but cached XLS exists — using cached data")
            else:
                print("[cftc_fin] No cached data available — cannot fetch financial futures")
                return 1

    # -- Parse XLS ----------------------------------------------------
    try:
        import pandas as pd
        df = pd.read_excel(XLS_PATH, dtype={"CFTC_Contract_Market_Code": str})
    except ImportError:
        print("[cftc_fin] pandas not available — install pandas and xlrd", file=sys.stderr)
        return 1

    print(f"[cftc_fin] Parsed TIFF: {len(df)} rows, {len(df['CFTC_Contract_Market_Code'].dropna().unique())} unique contracts")

    # -- Filter for our 8 target contracts ----------------------------
    target_codes = {c["cftc_code"] for c in FINANCIAL_CONTRACTS}
    code_map = {c["cftc_code"]: c for c in FINANCIAL_CONTRACTS}

    df["code_str"] = df["CFTC_Contract_Market_Code"].astype(str).str.strip()
    df_target = df[df["code_str"].isin(target_codes)]

    if df_target.empty:
        print("[cftc_fin] WARNING: No target contracts found in TIFF data!", file=sys.stderr)
        # Could be code format mismatch — try again more carefully
        all_codes = set(df["code_str"].dropna().unique())
        missing = target_codes - all_codes
        print(f"[cftc_fin] Missing codes: {missing}", file=sys.stderr)
        print(f"[cftc_fin] Sample available codes: {sorted(all_codes)[:20]}", file=sys.stderr)
        return 1

    # -- Build output (same schema as physical cftc_positions.json) ---
    positions_by_contract = {}
    positions_by_narrative = {}
    fetched = 0
    failed = 0

    for code in target_codes:
        cfg = code_map[code]
        contract_rows = df_target[df_target["code_str"] == code]

        if contract_rows.empty:
            failed += 1
            positions_by_contract[cfg["ticker"]] = {
                "ticker": cfg["ticker"],
                "label": cfg["label"],
                "narrative": cfg["narrative"],
                "cftc_code": code,
                "managed_money_net": None,
                "report_date": None,
                "status": "error",
                "error": f"No data for CFTC code '{code}'",
            }
            continue

        # Get the most recent report date
        row = contract_rows.sort_values("Report_Date_as_MM_DD_YYYY", ascending=False).iloc[0]
        summary = compute_summary(row)
        summary["ticker"] = cfg["ticker"]
        summary["label"] = cfg["label"]
        summary["narrative"] = cfg["narrative"]
        summary["cftc_code"] = code
        summary["status"] = "ok"

        positions_by_contract[cfg["ticker"]] = summary
        fetched += 1

        # Aggregate into narrative bucket
        nid = cfg["narrative"]
        if nid not in positions_by_narrative:
            positions_by_narrative[nid] = {
                "contracts": [],
                "total_mm_net": 0,
                "total_am_net": 0,
                "total_dealer_net": 0,
                "sentiment": "neutral",
            }
        bucket = positions_by_narrative[nid]
        bucket["contracts"].append(cfg["ticker"])
        bucket["total_mm_net"] += summary.get("managed_money_net", 0) or 0
        bucket["total_am_net"] += summary.get("asset_mgr_net", 0) or 0
        bucket["total_dealer_net"] += summary.get("dealer_net", 0) or 0

    # Derive narrative sentiment
    for nid, bucket in positions_by_narrative.items():
        mm = bucket["total_mm_net"]
        am = bucket["total_am_net"]
        if mm > 0 and am > 0:
            bucket["sentiment"] = "bullish"      # specs + institutions aligned long
        elif mm < 0 and am < 0:
            bucket["sentiment"] = "bearish"      # specs + institutions aligned short
        elif mm < 0 and am > 0:
            bucket["sentiment"] = "divergent"    # specs short, institutions long
        elif mm > 0 and am < 0:
            bucket["sentiment"] = "divergent"    # specs long, institutions short
        else:
            bucket["sentiment"] = "neutral"

    # Determine latest report date
    report_dates = set()
    for c in positions_by_contract.values():
        rd = c.get("report_date")
        if rd and rd != "NaT" and rd != "None":
            report_dates.add(rd)
    latest_date = max(report_dates) if report_dates else None

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "CFTC Traders in Financial Futures (TIFF) — bulk ZIP",
        "source_url": TIFF_URL,
        "cache_hours": CACHE_HOURS,
        "latest_report_date": latest_date,
        "contracts_fetched": fetched,
        "contracts_failed": failed,
        "total_contracts_defined": len(FINANCIAL_CONTRACTS),
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

    # -- Summary ------------------------------------------------------
    print(f"[cftc_fin] {fetched}/{len(FINANCIAL_CONTRACTS)} contracts fetched "
          f"({len(positions_by_narrative)} narratives)")
    for nid, bucket in positions_by_narrative.items():
        mm_b = bucket["total_mm_net"] / 1_000_000_000
        am_b = bucket["total_am_net"] / 1_000_000_000
        print(f"  {nid}: MM net={mm_b:+.2f}B, AM net={am_b:+.2f}B, sentiment={bucket['sentiment']}")
    print(f"[cftc_fin] Written: {OUTPUT_FILE} (report date: {latest_date or 'N/A'})")

    return 0 if fetched > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
