#!/usr/bin/env python3
"""
calculate_capital.py -- Multi-source capital volume computation
================================================================
Phase 3: Bridges CFTC institutional positioning + FRED macro regime
into real dollar-value capital-at-stake per narrative.

Reads:  cftc_positions.json, fred_series.json, market_prices.json, stories.json
Writes: stories.json (atomic swap) — adds capital_at_stake_usd, data_fidelity,
        materiality_pass, tier, rci, narrative_alpha

Governor step 6 — runs after classify, before gen_flows.
"""

import json
import os
import statistics
import sys
from pathlib import Path

# -- config ----------------------------------------------------------
PROJECT = Path(__file__).resolve().parent.parent
PUBLIC_DATA = PROJECT / "public" / "data"
DATA_DIR = PROJECT / "data"
STORIES_FILE = DATA_DIR / "stories.json"
CFTC_FILE = DATA_DIR / "cftc_positions.json"
CFTC_FINANCIAL_FILE = DATA_DIR / "cftc_financial_positions.json"
FRED_FILE = DATA_DIR / "fred_series.json"
PRICES_FILE = DATA_DIR / "market_prices.json"

MATERIALITY_THRESHOLD_USD = 0   # Disable gate (all stories are material)
GAP_MATERIALITY_FLOOR = 0       # Disable floor
FIDELITY_MULTIPLIERS = {"TIER_1": 1.0, "TIER_2": 0.8, "TIER_3": 0.5}
MAX_CAPITAL_PER_STORY = 10_000_000_000   # $10B hard cap — single story can't exceed this
MAX_NARRATIVE_CAPITAL = 10_000_000_000_000  # $10T circuit breaker — narrative aggregate cap

# FRED series normalization ranges: (min_plausible, max_plausible)
# Maps raw FRED values into [0,1] before averaging so exchange rates (7),
# trade balances (100K), and indices (103) aren't naively averaged.
FRED_NORM_RANGES = {
    "DGS10":       (0, 10),       # 10Y yield: 0-10%
    "T10Y2Y":      (-3, 3),       # 10Y-2Y spread: -3 to +3%
    "DFEDTARU":    (0, 10),       # Fed Funds upper limit: 0-10%
    "UNRATE":      (2, 15),       # Unemployment: 2-15%
    "DEXCHUS":     (5, 9),        # CNY/USD: 5-9
    "BOPGSTB":     (-150000, 50000),  # Trade balance ($M): -150B to +50B
    "INDPRO":      (80, 120),     # Industrial production index: 80-120
    "DTWEXBGS":    (80, 160),     # Trade-weighted USD: 80-160
    "DEXUSEU":     (0.8, 1.4),    # EUR/USD: 0.80-1.40
    "DEXJPUS":     (0.004, 0.010),# JPY/USD: 0.004-0.010 (100-250 JPY per USD)
    "PPIACO":      (80, 200),     # PPI all commodities: 80-200
    "CPIAUCSL":    (200, 350),    # CPI-U: 200-350
    "DCOILWTICO":  (0, 150),      # WTI crude: $0-150
    "DHHNGSP":     (0, 15),       # Henry Hub natural gas: $0-15
    "GPDI":        (1000, 5000),  # Gross Private Domestic Investment ($B): 1T-5T
}

# Approximate contract notional values (June 2026) for dollar-value conversion
# CFTC data gives us contract counts; multiply by these to get USD exposure
CONTRACT_NOTIONALS = {
    "GC": 100 * 3300,        # Gold: 100 oz × ~$3300/oz = $330K
    "SI": 5000 * 33,         # Silver: 5000 oz × ~$33/oz = $165K
    "PL": 50 * 1000,         # Platinum: 50 oz × ~$1000/oz = $50K
    "CL": 1000 * 68,         # WTI Crude: 1000 bbl × ~$68/bbl = $68K
    "NG": 10000 * 3.50,      # Natural Gas: 10K MMBtu × ~$3.50 = $35K
    "RB": 42000 * 2.20,      # RBOB Gasoline: 42K gal × ~$2.20 = $92.4K
    "HO": 42000 * 2.40,      # Heating Oil: 42K gal × ~$2.40 = $100.8K
    "HG": 25000 * 4.60,      # Copper: 25K lbs × ~$4.60/lb = $115K
    "ZC": 5000 * 4.50,       # Corn: 5000 bu × ~$4.50/bu = $22.5K
    "ZW": 5000 * 5.50,       # Wheat: 5000 bu × ~$5.50/bu = $27.5K
    "ZS": 5000 * 10.50,      # Soybeans: 5000 bu × ~$10.50 = $52.5K
    "ZM": 100 * 350,         # Soybean Meal: 100 tons × ~$350 = $35K
    "SB": 112000 * 0.19,     # Sugar: 112K lbs × ~$0.19/lb = $21.3K
    "KC": 37500 * 2.70,      # Coffee: 37.5K lbs × ~$2.70/lb = $101.3K
    "CC": 10 * 6500,         # Cocoa: 10 metric tons × ~$6500 = $65K
    "AL": 25 * 2500,         # Aluminum: 25 metric tons × ~$2500 = $62.5K
    "ST": 20 * 700,          # Steel: 20 short tons × ~$700 = $14K
    "JF": 42000 * 2.20,      # Jet Fuel (proxy RBOB sizing)
    "JH": 42000 * 0.15,      # Jet/Heat spread
}

# Financial futures notional values (TIFF report, June 2026)
# Currencies: contract size × approximate FX rate
# Treasuries: face value at par
# Equities: $multiplier × approximate index level
FINANCIAL_CONTRACT_NOTIONALS = {
    "6E": 125000 * 1.08,      # Euro FX: 125K€ × ~$1.08/€ = $135K
    "6J": 12500000 / 147,     # Japanese Yen: 12.5M¥ ÷ ~147¥/$ = $85K
    "6B": 62500 * 1.26,       # British Pound: 62.5K£ × ~$1.26/£ = $78.75K
    "ZT": 200_000,            # 2Y Note: $200K face value
    "ZN": 100_000,            # 10Y Note: $100K face value
    "ZB": 100_000,            # 30Y Bond: $100K face value
    "ES": 50 * 5600,          # S&P E-mini: $50 × ~5600 = $280K
    "NQ": 20 * 21500,         # Nasdaq Mini: $20 × ~21500 = $430K
}

# ── Representational Proxy Portfolios (RPP) ─────────────────────────
# Each narrative tracks a CANONICAL set of highly liquid, causally-linked
# proxy instruments — NOT "total market cap." These are High-Beta Proxy Assets
# selected for narrative sensitivity, institutional accessibility, and daily
# liquidity. See docs/NMC_METHODOLOGY_PITCH.md for VC defense.
#
# Label: "Capital tracked via High-Beta Proxy Assets"
#
# Narrative → Canonical Proxy Portfolio + primary data source
NARRATIVE_PROXY_PORTFOLIO = {
    "usd_debasement_reserve_diversification": {
        "source": "cftc",
        "label": "Precious Metals + Currency Futures",
        "proxies": ["GC=F", "SI=F", "GLD", "SLV", "UUP", "DX=F", "EURUSD=X", "JPYUSD=X"],
        "rationale": "Gold/silver as anti-dollar hedges; DXY and EURUSD as direct currency vectors"
    },
    "critical_resource_control_infrastructure": {
        "source": "cftc",
        "label": "Energy Futures + Uranium",
        "proxies": ["CL=F", "NG=F", "XLE", "URA", "NLR"],
        "rationale": "Crude + natural gas futures; uranium as energy sovereignty play"
    },
    "commodity_supercycle_supply_rebalancing": {
        "source": "cftc",
        "label": "Industrial Metals + Grains",
        "proxies": ["HG=F", "DBC", "COPX", "XME", "WEAT", "CORN"],
        "rationale": "Copper, broad commodities, industrial metals, agricultural futures"
    },
    "supply_chain_resilience_reshoring_defense": {
        "source": "cftc",
        "label": "Defense + Industrial Metals",
        "proxies": ["XLI", "ITA", "PPA", "XME", "FDX", "CAT"],
        "rationale": "Defense primes + industrial metals as deglobalization beneficiaries"
    },
    "monetary_policy_regime_shift_rate_cycle": {
        "source": "fred",
        "label": "Treasury ETFs + Bond Futures",
        "proxies": ["TLT", "SHY", "IEF", "ZN=F", "ZB=F"],
        "rationale": "Duration/dollar sensitivity to rate cycle shifts"
    },
    "china_geoeconomic_expansion": {
        "source": "fred",
        "label": "China Equity ETFs + Currency",
        "proxies": ["FXI", "KWEB", "MCHI", "BABA", "CNY=X"],
        "rationale": "China equity + tech exposure; CNY as policy transmission channel"
    },
    "tech_convergence_platforms_ai_autonomy": {
        "source": "prices",
        "label": "Cloud + Enterprise Tech",
        "proxies": ["MSFT", "AMZN", "GOOGL", "QQQ", "CLOU", "WCLD"],
        "rationale": "Cloud infrastructure + enterprise software as tech consolidation vectors"
    },
    "space_economy_commercialization": {
        "source": "prices",
        "label": "Space + Defense Primes",
        "proxies": ["ARKX", "UFO", "ROKT", "LMT", "NOC"],
        "rationale": "Space ETFs + defense primes with space divisions"
    },
    "gene_editing_biotech_longevity": {
        "source": "prices",
        "label": "Biotech + Gene Editing",
        "proxies": ["ARKG", "XBI", "IBB", "CRSP", "NTLA"],
        "rationale": "Biotech ETFs + gene-editing pure-plays with clinical catalysts"
    },
    "prestige_asset_acquisition_strategic_investment": {
        "source": "prices",
        "label": "Sports Betting + Franchise Ownership",
        "proxies": ["DKNG", "MANU", "BATRK", "DIS"],
        "rationale": "Sports betting operators + publicly traded franchise owners"
    },
    "ai_compute_semiconductor_hegemony": {
        "source": "prices",
        "label": "Semiconductor + AI Infrastructure",
        "proxies": ["NVDA", "SMH", "AMD", "ASML", "TSM"],
        "rationale": "Chipmakers with direct AI infrastructure exposure"
    },
    "digital_assets_reserves_onchain_finance": {
        "source": "prices",
        "label": "Crypto + Institutional On-Ramps",
        "proxies": ["BTC-USD", "COIN", "MSTR", "ETH-USD"],
        "rationale": "Bitcoin + Ethereum; institutional exchange and treasury exposure"
    },
}

# Backward-compatible alias
NARRATIVE_DATA_SOURCE = {nid: cfg["source"] for nid, cfg in NARRATIVE_PROXY_PORTFOLIO.items()}


# -- helpers ---------------------------------------------------------
def load_json(path):
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def fix_ownership(path_str):
    if sys.platform != "linux":
        return
    try:
        import pwd, grp
        uid = pwd.getpwnam("gazzetta").pw_uid
        gid = grp.getgrnam("gazzetta").gr_gid
        os.chown(path_str, uid, gid)
    except (KeyError, OSError):
        pass


# -- capital computation ---------------------------------------------
def compute_cftc_capital(narrative_id, cftc_data):
    """
    Convert CFTC speculative net positioning to dollar-value capital at stake.
    Uses managed_money_net (specs) as the primary signal.
    """
    positions = cftc_data.get("positions_by_narrative", {}).get(narrative_id)
    if not positions:
        return 0, "TIER_3"

    total_usd = 0
    for ticker in positions.get("contracts", []):
        contract = cftc_data.get("positions_by_contract", {}).get(ticker, {})
        if contract.get("status") != "ok":
            continue
        mm_net = abs(contract.get("managed_money_net", 0) or 0)
        notional = CONTRACT_NOTIONALS.get(ticker, 100_000)
        total_usd += mm_net * notional

    fidelity = "TIER_1" if total_usd > 0 else "TIER_3"
    return total_usd, fidelity


def compute_cftc_financial_capital(narrative_id, cftc_fin):
    """
    Convert TIFF financial futures speculative positioning to dollar-value capital.
    Uses Lev_Money_net (leveraged money = hedge funds/CTAs) as primary signal.
    """
    positions = cftc_fin.get("positions_by_narrative", {}).get(narrative_id)
    if not positions:
        return 0, "TIER_3"

    total_usd = 0
    for ticker in positions.get("contracts", []):
        contract = cftc_fin.get("positions_by_contract", {}).get(ticker, {})
        if contract.get("status") != "ok":
            continue
        mm_net = abs(contract.get("managed_money_net", 0) or 0)
        notional = FINANCIAL_CONTRACT_NOTIONALS.get(ticker, 100_000)
        total_usd += mm_net * notional

    fidelity = "TIER_1" if total_usd > 0 else "TIER_3"
    return total_usd, fidelity


def compute_fred_capital(narrative_id, fred_data):
    """
    Derive capital-flow proxy from FRED macro series.
    Uses key series relevant to each narrative.
    """
    series = fred_data.get("series", {})
    regime = fred_data.get("macro_regime", "UNKNOWN")

    # Narrative → relevant FRED series + scaling factors
    narrative_series = {
        "monetary_policy_regime_shift_rate_cycle": ["DGS10", "T10Y2Y", "DFEDTARU", "UNRATE"],
        "china_geoeconomic_expansion": ["DEXCHUS", "BOPGSTB", "INDPRO"],
        "usd_debasement_reserve_diversification": ["DTWEXBGS", "DEXUSEU", "DEXJPUS"],
        "supply_chain_resilience_reshoring_defense": ["BOPGSTB", "GPDI", "INDPRO"],
        "commodity_supercycle_supply_rebalancing": ["PPIACO", "CPIAUCSL", "DCOILWTICO"],
        "critical_resource_control_infrastructure": ["DCOILWTICO", "DHHNGSP", "PPIACO"],
    }

    keys = narrative_series.get(narrative_id, [])
    if not keys:
        return 0, "TIER_3"

    # Sum normalized values (0-1 range) of key series to produce a unitless
    # tension score, then scale to capital-dollar space.
    # This prevents unit mismatches: exchange rates (~7), trade balances (~100K),
    # and indices (~103) are each normalized to their plausible range before averaging.
    norm_total = 0.0
    count = 0
    for key in keys:
        s = series.get(key, {})
        val = s.get("value")
        if val is None:
            continue
        norm_range = FRED_NORM_RANGES.get(key)
        if norm_range:
            lo, hi = norm_range
            span = hi - lo
            if span > 0:
                clamped = max(lo, min(hi, val))
                norm_total += (clamped - lo) / span
                count += 1

    if count == 0:
        return 0, "TIER_3"

    norm_avg = norm_total / count

    # FRED series are normalized to [0,1] — scaling to capital-dollar space
    # Base: $10B × normalized average
    if narrative_id == "monetary_policy_regime_shift_rate_cycle":
        capital = norm_avg * 10_000_000_000     # yield curve tension → up to $10B
    elif narrative_id == "china_geoeconomic_expansion":
        capital = norm_avg * 5_000_000_000       # CNY/trade tension → up to $5B
    elif narrative_id == "usd_debasement_reserve_diversification":
        capital = norm_avg * 8_000_000_000       # dollar index tension → up to $8B
    else:
        capital = norm_avg * 3_000_000_000       # generic macro → up to $3B

    # Regime modifier
    regime_mod = {
        "INVERSION": 1.5,
        "TIGHTENING": 1.3,
        "ACCOMMODATIVE": 1.2,
        "EASING": 1.0,
        "NEUTRAL": 0.8,
    }.get(regime, 0.8)

    capital *= regime_mod
    fidelity = "TIER_2"
    return capital, fidelity


def compute_prices_capital(narrative_id, prices_data):
    """
    Fallback: use ETF AUM from market_prices.json.
    This is the pre-existing method; CFTC/FRED override when available.
    """
    narrative_tickers = {
        "tech_convergence_platforms_ai_autonomy": ["CLOU", "WCLD", "ARTY", "BOTZ"],
        "space_economy_commercialization": ["ARKX", "UFO", "ROKT", "MARS"],
        "gene_editing_biotech_longevity": ["ARKG", "XBI", "IBB"],
        "prestige_asset_acquisition_strategic_investment": ["STAD", "DKNG"],
        "china_geoeconomic_expansion": ["FXI", "MCHI", "ASHR", "KWEB"],
        "ai_compute_semiconductor_hegemony": ["SMH", "SOXX", "QQQ"],
        "digital_assets_reserves_onchain_finance": [],  # handled separately
    }

    tickers = narrative_tickers.get(narrative_id, [])
    if not tickers:
        # digital_assets_reserves_onchain_finance: use BTC market cap proxy
        if narrative_id == "digital_assets_reserves_onchain_finance":
            # Estimate from BTC at ~$65K with active trading float ~5%
            return 64_000 * 19_700_000 * 0.05, "TIER_3"
        return 0, "TIER_3"

    # Sum AUM from market_prices.json for these tickers
    total_aum = 0
    for t in tickers:
        info = prices_data.get(t, {})
        aum = info.get("aum", 0) or info.get("market_cap", 0) or 0
        total_aum += aum

    # ETF AUM is total passive — active positioning is fraction
    active_share = 0.15  # ~15% of ETF AUM is active positioning
    capital = total_aum * active_share
    fidelity = "TIER_3"
    return capital, fidelity


def get_asset_base(narrative_id, cftc, cftc_fin, fred, prices):
    """Return (capital_at_stake_base_usd, fidelity_tier) for a narrative.
    Data source priority: CFTC > CFTC Financial > FRED > Prices."""
    source = NARRATIVE_DATA_SOURCE.get(narrative_id, "prices")

    # Tier 1a: Physical CFTC — highest fidelity for commodity narratives
    if source == "cftc":
        capital, fidelity = compute_cftc_capital(narrative_id, cftc)
        if capital > 0:
            return capital, fidelity
        # Fall through to financial CFTC for dollar_decline (precious metals + currencies)

    # Tier 1b: Financial CFTC — for dollar_decline, rate_cycle, tech_convergence
    capital_fin, fidelity_fin = compute_cftc_financial_capital(narrative_id, cftc_fin)
    if capital_fin > 0:
        # Merge with physical CFTC if both exist (e.g., dollar_decline has gold + euro fx)
        capital_phys, _ = compute_cftc_capital(narrative_id, cftc)
        total = capital_phys + capital_fin
        return total, "TIER_1"

    # Tier 1c: Physical CFTC as secondary source for non-cftc narratives
    if source != "cftc":
        capital, fidelity = compute_cftc_capital(narrative_id, cftc)
        if capital > 0:
            return capital, fidelity

    # Tier 2: FRED — macro overlay
    if source == "fred":
        capital, fidelity = compute_fred_capital(narrative_id, fred)
        if capital > 0:
            return capital, fidelity

    # Tier 3: ETF AUM fallback
    return compute_prices_capital(narrative_id, prices)


def compute_tier(gap, materiality_pass):
    if not materiality_pass:
        return "SETTLING"
    if gap >= 65:
        return "BREAKING"
    if gap >= 40:
        return "ACTIVE"
    return "SETTLING"


# -- main ------------------------------------------------------------
def main():
    print("[calc_capital] Computing Capital at Stake + RCI Alpha + Materiality Gate...")

    stories_data = load_json(STORIES_FILE)
    cftc = load_json(CFTC_FILE)
    cftc_fin = load_json(CFTC_FINANCIAL_FILE)
    fred = load_json(FRED_FILE)
    prices = load_json(PRICES_FILE)

    all_stories = stories_data.get("all_stories", [])
    if not all_stories:
        print("[-] No stories found.")
        sys.exit(0)

    processed = 0
    material_count = 0
    narrative_accum = {}  # {nid: {"capital_bases": [], "fidelity": tier}}

    # Pre-compute story counts per narrative for per-story division.
    # The asset_base (total CFTC positioning, ETF AUM, etc.) represents the
    # ENTIRE narrative's structural capital, not one story's. Dividing by
    # story_count keeps the sum bounded to actual market reality.
    story_counts = {}
    for story in all_stories:
        nid = story.get("narrative_id", "")
        if nid and nid != "unassigned":
            story_counts[nid] = story_counts.get(nid, 0) + 1

    for story in all_stories:
        nid = story.get("narrative_id", "")
        gap = int(story.get("contradiction_gap", 0))

        # 1. Get asset base from best available source
        asset_base, fidelity = get_asset_base(nid, cftc, cftc_fin, fred, prices)

        # 2. Per-story division: asset_base ÷ story_count
        n_stories = story_counts.get(nid, 1)
        per_story_base = asset_base / max(n_stories, 1)

        multiplier = FIDELITY_MULTIPLIERS.get(fidelity, 0.5)

        # 3. Capital at stake = per_story_base × (gap/100) × fidelity
        capital_usd = per_story_base * (gap / 100.0) * multiplier

        # 4. Hard cap — single story cannot exceed $10B regardless of math
        capital_usd = min(capital_usd, MAX_CAPITAL_PER_STORY)

        # 5. Materiality gate — disabled (all stories pass)
        is_material = True

        # 6. Update story fields
        story["capital_at_stake_usd"] = int(capital_usd)
        story["capital_base_usd"] = int(per_story_base)
        story["data_fidelity"] = fidelity
        story["materiality_pass"] = is_material
        story["tier"] = compute_tier(gap, is_material)

        processed += 1
        if is_material:
            material_count += 1

        # Accumulate for narrative alpha
        if nid and nid != "unassigned" and asset_base > 0:
            if nid not in narrative_accum:
                narrative_accum[nid] = {"capital_bases": [], "fidelity": fidelity}
            narrative_accum[nid]["capital_bases"].append(asset_base)
            narrative_accum[nid]["fidelity"] = fidelity  # latest wins

    # -- Narrative Alpha: median-gap capital per narrative --
    narrative_alpha = {}
    for nid in sorted(narrative_accum.keys()):
        bases = narrative_accum[nid]["capital_bases"]
        fid = narrative_accum[nid]["fidelity"]
        mult = FIDELITY_MULTIPLIERS.get(fid, 0.5)

        # Median capital base × fidelity multiplier
        median_base = statistics.median(bases) if bases else 0
        total_cap = median_base * mult

        # Circuit breaker: cap narrative aggregate at $10T
        if total_cap > MAX_NARRATIVE_CAPITAL:
            print(f"  [calc_capital] ⚠ CIRCUIT BREAKER: {nid} capital ${total_cap:,.0f} "
                  f"exceeds ${MAX_NARRATIVE_CAPITAL:,.0f} cap — clamping to $10T")
            total_cap = MAX_NARRATIVE_CAPITAL

        narrative_alpha[nid] = {
            "total_capital_usd": int(total_cap),
            "story_count": len(bases),
            "median_capital_base_usd": int(median_base),
            "data_fidelity": fid,
        }

    stories_data["all_stories"] = all_stories
    stories_data["narrative_alpha"] = narrative_alpha

    # Atomic write
    tmp_path = STORIES_FILE.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(stories_data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, STORIES_FILE)

    fix_ownership(str(STORIES_FILE))

    cftc_ok = cftc.get("status") == "ok"
    cftc_fin_ok = cftc_fin.get("status") == "ok"
    fred_ok = fred.get("status") == "ok"
    print(
        f"[+] {processed} stories processed. {material_count} passed materiality gate."
    )
    print(
        f"[+] Data sources: CFTC={'OK' if cftc_ok else 'DEGRADED'}, "
        f"CFTC_Fin={'OK' if cftc_fin_ok else 'DEGRADED'}, "
        f"FRED={'OK' if fred_ok else 'DEGRADED'}, "
        f"Prices={'OK' if prices else 'DEGRADED'}"
    )
    print(f"[+] Narrative alpha computed for {len(narrative_alpha)} narratives.")


if __name__ == "__main__":
    main()
