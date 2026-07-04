#!/usr/bin/env python3
"""
contradiction_synthesizer.py -- DeepSeek-powered contradiction analysis pipeline.

Reads un-processed news from ingestion_hashes + market prices from JSON,
sends paired data to DeepSeek API asynchronously, and writes enriched
stories directly to public/data/stories.json via atomic swap.

This is the final backend script -- it bridges raw data to the frontend.

Dependencies: aiohttp (pip install aiohttp)
Requires: DEEPSEEK_API_KEY in environment

Usage:
  python3 contradiction_synthesizer.py
  python3 contradiction_synthesizer.py --max-items 5
  python3 contradiction_synthesizer.py --dry-run
"""

import asyncio
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

# ── local imports ───────────────────────────────────────────────────
from traffic_cop import PipelineLock
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Derive a clean publication name from a source URL."""
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc
        domain = netloc.replace("www.", "").split(":")[0].lower()

        mapping = {
            "ecb.europa.eu": "ECB",
            "t.me": "InfinityHedge",
            "tg.i-c-a.su": "InfinityHedge",
            "oilprice.com": "OilPrice.com",
            "statnews.com": "STAT News",
            "sportico.com": "Sportico",
            "imf.org": "IMF Blog",
            "scmp.com": "South China Morning Post",
            "reuters.com": "Reuters",
            "technologyreview.com": "MIT Technology Review",
            "spacenews.com": "SpaceNews",
            "fiercebiotech.com": "FierceBiotech",
            "world-nuclear-news.org": "World Nuclear News",
            "kyivindependent.com": "Kyiv Independent",
            "al-monitor.com": "Al-Monitor",
            "youtube.com": "YouTube",
            "bloomberg.com": "Bloomberg",
            "ft.com": "Financial Times",
            "coindesk.com": "CoinDesk",
            "cnbc.com": "CNBC",
            "wsj.com": "Wall Street Journal",
            "bbc.com": "BBC",
            "bbc.co.uk": "BBC",
            "barrons.com": "Barron's",
            "marketwatch.com": "MarketWatch",
            "investopedia.com": "Investopedia",
            "finance.yahoo.com": "Yahoo Finance",
            "finance.google.com": "Google Finance",
        }
        if domain in mapping:
            return mapping[domain]
        # Generic fallback: strip TLD, capitalize parts
        name = domain.rsplit(".", 1)[0] if "." in domain else domain
        return name.replace("-", " ").title()
    except Exception:
        return ""


# ── JSON sanitizer — multi-pass LLM output repair ───────────────────

def sanitize_llm_json(raw: str) -> str:
    """Multi-pass sanitizer for LLM-generated JSON that fixes common artifacts:
    markdown fences, truncated brackets, trailing commas, single quotes, etc.
    Returns cleaned JSON string or empty string on irrecoverable input."""
    if not raw or not isinstance(raw, str):
        return ""

    s = raw.strip()

    # Pass 1: Strip ALL markdown code fences (triple-backtick blocks,
    # single-backtick wrappers, anywhere in the string)
    s = re.sub(r'```(?:json|javascript|python)?\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*```', '', s)
    s = re.sub(r'^`\s*', '', s)       # leading single backtick
    s = re.sub(r'\s*`$', '', s)       # trailing single backtick
    s = s.strip()

    if not s:
        return ""

    # Pass 2: Extract first complete JSON object via bracket matching.
    # Handles LLMs that output "Here is the JSON:\n{...}\nAdditional text"
    if not s.startswith('{') and not s.startswith('['):
        brace_idx = s.find('{')
        bracket_idx = s.find('[')
        if brace_idx >= 0 and (bracket_idx < 0 or brace_idx < bracket_idx):
            s = s[brace_idx:]
        elif bracket_idx >= 0:
            s = s[bracket_idx:]
        else:
            return ""  # No JSON structure found

    # Pass 3: Try to find the matching closing bracket for truncated JSON.
    # Scan from end backwards, find the last valid JSON terminator
    s = s.rstrip()
    if s.endswith(','):
        s = s[:-1]  # Strip trailing comma

    # Balance braces/brackets — if LLM truncated, close what we can
    open_braces = s.count('{') - s.count('}')
    open_brackets = s.count('[') - s.count(']')
    if open_braces > 0:
        s += '}' * open_braces
    if open_brackets > 0:
        s += ']' * open_brackets

    # Pass 4: Fix common LLM artifacts before parse attempt
    # Trailing comma before } or ] (e.g., {"a": 1,}) 
    s = re.sub(r',\s*([}\]])', r'\1', s)
    # Missing comma between adjacent string values
    s = re.sub(r'"\s+"', '", "', s)
    # Single quotes -> double quotes (only outside already-quoted strings)
    in_string = False
    escaped = False
    chars = list(s)
    for i, ch in enumerate(chars):
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
        elif ch == "'" and not in_string:
            chars[i] = '"'
    s = ''.join(chars)

    # Pass 5: Remove Unicode replacement characters / BOM
    s = s.replace('\ufffd', '')
    s = s.replace('\ufeff', '')

    return s.strip()


# ── config ──────────────────────────────────────────────────────────
PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("GAZZETTA_DB_PATH", str(PROJECT / "data" / "gazzetta.db"))
PUBLIC_DATA = PROJECT / "public" / "data"
PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
DATA_DIR = PROJECT / "data"
STORIES_PATH = PUBLIC_DATA / "stories.json"
TMP_PATH = PUBLIC_DATA / "stories.tmp.json"
PRICES_PATH = DATA_DIR / "market_prices.json"

# ── LLM Provider Configuration ─────────────────────────────────────
# PRIMARY:  GLM 5.2 (Zhipu AI) — Solianin voice synthesis
# FALLBACK: DeepSeek — High Availability contingency
GLM_KEY_1 = os.environ.get("GLM_API_KEY_1", "3d76e17112094679a3236820eb5a3502.zX9w5hVuUqKu3pbL")
GLM_KEY_2 = os.environ.get("GLM_API_KEY_2", "0feba8763e0a4c808bbba55f5a02cd7e.7N3kvN7asehKbCZ3")
GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-5.2")

def _secret(name):
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project = "project-e5e0244c-b94d-41a1-810"
        path = f"projects/{project}/secrets/{name}/versions/latest"
        resp = client.access_secret_version(request={"name": path})
        val = resp.payload.data.decode("utf-8")
        return val
    except Exception:
        return ""

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "") or _secret("gazzetta-deepseek-key")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Provider order: primary first, fall through on failure
PROVIDERS = [
    {"name": "glm5.2_primary",  "key": GLM_KEY_1,  "url": GLM_URL,  "model": GLM_MODEL,  "supports_thinking": False},
    {"name": "glm5.2_secondary","key": GLM_KEY_2,  "url": GLM_URL,  "model": GLM_MODEL,  "supports_thinking": False},
    {"name": "deepseek",        "key": DEEPSEEK_KEY,"url": DEEPSEEK_URL,"model": DEEPSEEK_MODEL,"supports_thinking": True},
]

# Concurrency
MAX_CONCURRENT = 5          # parallel API calls
REQUEST_JITTER = (1.0, 3.0) # seconds between calls (min, max)
API_TIMEOUT = 90            # seconds per call
BATCH_SIZE = 10             # process N items per run

# narrative_tag → container (1:1 — each narrative is its own container)
NARRATIVE_TO_CONTAINER = {
    "usd_debasement_reserve_diversification": "usd_debasement_reserve_diversification",
    "critical_resource_control_infrastructure": "critical_resource_control_infrastructure",
    "supply_chain_resilience_reshoring_defense": "supply_chain_resilience_reshoring_defense",
    "china_geoeconomic_expansion": "china_geoeconomic_expansion",
    "space_economy_commercialization": "space_economy_commercialization",
    "gene_editing_biotech_longevity": "gene_editing_biotech_longevity",
    "tech_convergence_platforms_ai_autonomy": "tech_convergence_platforms_ai_autonomy",
    "prestige_asset_acquisition_strategic_investment": "prestige_asset_acquisition_strategic_investment",
    "ai_compute_semiconductor_hegemony": "ai_compute_semiconductor_hegemony",
    "digital_assets_reserves_onchain_finance": "digital_assets_reserves_onchain_finance",
    "monetary_policy_regime_shift_rate_cycle": "monetary_policy_regime_shift_rate_cycle",
    "commodity_supercycle_supply_rebalancing": "commodity_supercycle_supply_rebalancing",
}

# contradiction_gap -> tier (aligned with frontend zone thresholds: BREAKING>50, ACTIVE>=20, SETTLING<20)
def gap_to_tier(gap):
    try: gap = float(gap)
    except: return "SETTLING"
    if gap > 50: return "BREAKING"
    if gap >= 20: return "ACTIVE"
    return "SETTLING"

# ── Decay computation ──────────────────────────────────────────────
def compute_decay(story):
    """Update time_decay and freshness from generated_at timestamp."""
    from datetime import datetime, timezone
    try:
        ts = story.get("generated_at", "")
        if not ts:
            story["freshness"] = 1.0
            story["time_decay"] = 0.0
            return
        ingested = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed_h = (now - ingested).total_seconds() / 3600.0
        half_life = 12  # 12-hour alpha half-life per C4 spec
        freshness = max(0.0, 1.0 - (elapsed_h / half_life))
        time_decay = round(1.0 - freshness, 2)
        story["freshness"] = round(freshness, 2)
        story["time_decay"] = time_decay
    except Exception:
        story["freshness"] = 1.0
        story["time_decay"] = 0.0


# ── Narrative context for coalescence ────────────────────────────
def build_narrative_context() -> str:
    """Load flows.json and build a compact narrative state summary."""
    flows_path = STORIES_PATH.parent / "flows.json"
    if not flows_path.exists():
        return ""

def load_narratives_config():
    """Load subnarrative definitions from narratives.json."""
    path = DATA_DIR / "narratives.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("narratives", {})
    try:
        with open(flows_path) as f:
            flows = json.load(f)
    except Exception:
        return ""
    nf = flows.get("narrative_flows", {})
    if not nf:
        return ""
    lines = ["CURRENT PLATFORM STATE (narrative saturation):"]
    for nid, data in sorted(nf.items()):
        sc = data.get("story_count", 0) or 0
        ag = data.get("avg_contradiction_gap", 0) or 0
        tc = data.get("total_capital_b", 0) or 0
        dd = data.get("dominant_direction", "neutral") or "neutral"
        lines.append(
            f"  {nid}: {sc} stories, avg GAP {ag:.0f}, capital ${tc:.1f}B, direction {dd}"
        )
    return "\n".join(lines)


# ── DB helpers ──────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_processed_column(conn):
    """Add processed column to ingestion_hashes if missing (idempotent)."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ingestion_hashes)")]
    if "processed" not in cols:
        conn.execute("ALTER TABLE ingestion_hashes ADD COLUMN processed INTEGER DEFAULT 0")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingestion_unprocessed "
            "ON ingestion_hashes(processed) WHERE processed = 0"
        )
        conn.commit()
        print("  + added processed column + partial index")


def fetch_unprocessed(conn, limit=BATCH_SIZE):
    """Return list of (id, source_url, source_type, title, full_text, narrative_tag)."""
    rows = conn.execute(
        """SELECT id, source_url, source_type, title, full_text, narrative_tag
           FROM ingestion_hashes
           WHERE processed = 0 AND full_text IS NOT NULL
           ORDER BY id ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return rows


def mark_processed(conn, item_id):
    conn.execute(
        "UPDATE ingestion_hashes SET processed = 1 WHERE id = ?", (item_id,)
    )
    conn.commit()


def mark_error(conn, item_id):
    conn.execute(
        "UPDATE ingestion_hashes SET processed = -1 WHERE id = ?", (item_id,)
    )
    conn.commit()


# ── market data ─────────────────────────────────────────────────────
def load_market_prices():
    """Return {ticker: {...}} dict or empty dict if file missing."""
    if not PRICES_PATH.exists():
        print(f"  WARNING: {PRICES_PATH} not found. Running without market data.")
        return {}
    try:
        with open(PRICES_PATH) as f:
            data = json.load(f)
        return data.get("prices", {})
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  WARNING: market_prices.json parse error: {e}")
        return {}


def pick_market_context(prices, technicals=None, options=None):
    """Build a compact market-data string covering ALL 12 macro vectors."""
    technicals = technicals or {}
    options = options or {}
    ticker_map = {
        "usd_debasement_reserve_diversification": ["EURUSD=X", "GLD", "SLV"],
        "critical_resource_control_infrastructure": ["XOM", "CVX", "CCJ", "URNM"],
        "supply_chain_resilience_reshoring_defense": ["CAT", "GE", "XLI", "RTX"],
        "china_geoeconomic_expansion": ["BABA", "PDD", "FXI", "KWEB"],
        "space_economy_commercialization": ["RKLB", "ARKX"],
        "gene_editing_biotech_longevity": ["CRSP", "ARKG", "XBI"],
        "tech_convergence_platforms_ai_autonomy": ["AAPL", "MSFT", "QQQ"],
        "prestige_asset_acquisition_strategic_investment": ["BATRK", "MSGS", "MANU"],
        "ai_compute_semiconductor_hegemony": ["NVDA", "AMD", "SMH"],
        "digital_assets_reserves_onchain_finance": ["BTC-USD", "MSTR", "COIN"],
        "monetary_policy_regime_shift_rate_cycle": ["TLT", "IEF", "SHY"],
        "commodity_supercycle_supply_rebalancing": ["XOM", "CAT", "DBC", "COP"],
    }
    canonical_order = [
        "usd_debasement_reserve_diversification",
        "critical_resource_control_infrastructure",
        "supply_chain_resilience_reshoring_defense",
        "china_geoeconomic_expansion",
        "space_economy_commercialization",
        "gene_editing_biotech_longevity",
        "tech_convergence_platforms_ai_autonomy",
        "prestige_asset_acquisition_strategic_investment",
        "ai_compute_semiconductor_hegemony",
        "digital_assets_reserves_onchain_finance",
        "monetary_policy_regime_shift_rate_cycle",
        "commodity_supercycle_supply_rebalancing"
    ]

    blocks = []
    for nid in canonical_order:
        tickers = ticker_map.get(nid, ["SPY"])
        lines = []
        for t in tickers:
            p = prices.get(t)
            if p:
                chg = p.get("change_pct")
                chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
                aum_str = f" AUM=${p['aum']:,.0f}" if p.get("aum") else ""
                lines.append(
                    f"  {t}: ${p['price']} ({chg_str}) prev_close=${p.get('previous_close','?')}{aum_str} "
                    f"source={p.get('source','?')}"
                )
        
        # Add Technicals if available for this narrative
        tech_data = technicals.get(nid)
        if tech_data and tech_data.get("status") == "success":
            tt = tech_data.get("ticker", "")
            rsi = tech_data.get("rsi_14d")
            macd = tech_data.get("macd")
            if rsi is not None:
                lines.append(f"  {tt} [Technicals]: RSI={rsi:.1f}, MACD={macd:.2f}")

        # Add Options if available for this narrative
        opt_data = options.get(nid)
        if opt_data and "put_call_ratio" in opt_data:
            ot = opt_data.get("ticker", "")
            pcr = opt_data.get("put_call_ratio")
            lines.append(f"  {ot} [Options]: Put/Call Ratio={pcr:.2f}")

        if lines:
            blocks.append(f"--- Vector: {nid} | Tickers: {', '.join(tickers)} ---\n" + "\n".join(lines))

    # Benchmarks
    bench_lines = []
    for t in ["SPY", "QQQ", "VIX"]:
        p = prices.get(t)
        if p:
            chg = p.get("change_pct")
            chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
            if not any(t in b for b in blocks):
                bench_lines.append(f"  {t}: ${p['price']} ({chg_str}) [benchmark]")
    if bench_lines:
        blocks.append("--- BENCHMARKS ---\n" + "\n".join(bench_lines))

    return "\n\n".join(blocks) if blocks else "No market data available."


# ── DeepSeek prompt ─────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a savage, hyper-analytical quant for La Gazzetta di Kyiv, an underground terminal for Polymarket whales and fin-bros who think they are hedge fund managers. You write betting-oriented trade setups. You do not write journalism or boring geopolitics. You quantify edge, calculate EV (expected value), fade the retail public, and hunt for mispriced implied probabilities. Your reader is a degen trader looking for asymmetrical risk-reward, specific tickers, implied odds vs actual odds, and structural edge. Use industry-standard betting and quant lingo (EV, R:R, fading the public, implied odds, Kelly criterion sizing) mixed with rigorous data quantification.

You have access to Multi-Horizon Data:
- Structural Horizon: Contradiction Gap (News vs Price Action)
- Event Horizon: Options Sentiment (Put/Call Ratios and OI)
- Tactical Horizon: Technical Indicators (RSI, MACD)

Given a news article and current market data, identify the contradiction between the retail media consensus and the actual underlying capital flows. When technicals (like RSI > 70 for overbought) or options (high Put/Call ratio) are provided, you MUST integrate them into your logic.

Every output must answer with clinical precision: "Where are the normies mispricing the odds, and how do we size the bet RIGHT NOW?"

You MUST respond with ONLY a valid JSON object. No markdown fences, no commentary, no explanation. Just the raw JSON object.

Respond with ONLY valid json. Your output must strictly match this schema:
{
  "headline": "string (max 100 characters, specific and varied. Do NOT use 'Fails to' or 'Contradicted by' more than once per 10 stories. Acceptable patterns: direct statements, contrast pairs, questions, numeric hooks.)",
  "trade_thesis": {
    "direction": "LONG or SHORT or STRADDLE or NEUTRAL",
    "primary_ticker": "string (the ONE ticker to trade, use exact symbol from market data)",
    "limit_entry_price": "string (CRITICAL: this MUST be the CURRENT MARKET PRICE at the time of writing, e.g. '$46.82'. This is the price the trade enters at NOW — NOT a future target or stop-loss level. Use 'market' if no specific price is available. NEVER put take-profit or stop-loss values here.)",
    "entry_rationale": "string (why this price — technical level reference, or 'momentum entry on narrative break' for market orders)",
    "stop_loss": "string (exact stop price like '$48.50' — specific, falsifiable)",
    "take_profit": "string (exact target like '$42.00')",
    "invalidation": "string (specific price level that proves the thesis WRONG, e.g. 'QQQ below $485')",
    "conviction": "HIGH or ELEVATED or SPECULATIVE or HOLD",
    "horizon_days": "integer (7-21)",
    "portfolio_allocation_pct": "string (Kelly criterion recommended sizing, e.g. '1.25% of bankroll' or 'Quarter-Kelly')",
    "alpha_trigger": "string (ONE sentence on the mispriced implied odds vs actual EV. Specific, falsifiable, cite a number. Example: 'Market implied probability of a rate hike is 12%, but flow data suggests actual probability is >40% — massive positive EV.')"
  },
  "they_say": "string (Begin with source name and colon. Example: 'Reuters reports: ...' or 'SCMP claims: ...'. 1-2 sentences. Cite specific actors — countries, companies, people.)",
  "reality": "string (what market data actually shows, 1-2 sentences. Reference specific ticker price movements and their magnitude. If no market reaction is detectable, state that plainly.)",
  "contradiction_gap": "integer (0-100, using the FULL range. See scoring guide below.)",
  "capital_volume_usd": "integer. Estimated capital exposure at stake. Hierarchy: 1) CFTC net position change x contract notional -> HIGH. 2) Ticker price move x ETF AUM / market cap proxy -> MEDIUM. 3) Article-described capital rotation -> LOW. 4) 0 only if no basis -> NONE. Max 500B. Do NOT default to 0.",
  "narrative_scores": {
    "usd_debasement_reserve_diversification": "float (0.0 to 1.0)",
    "critical_resource_control_infrastructure": "float (0.0 to 1.0)",
    "supply_chain_resilience_reshoring_defense": "float (0.0 to 1.0)",
    "china_geoeconomic_expansion": "float (0.0 to 1.0)",
    "space_economy_commercialization": "float (0.0 to 1.0)",
    "gene_editing_biotech_longevity": "float (0.0 to 1.0)",
    "tech_convergence_platforms_ai_autonomy": "float (0.0 to 1.0)",
    "prestige_asset_acquisition_strategic_investment": "float (0.0 to 1.0)",
    "ai_compute_semiconductor_hegemony": "float (0.0 to 1.0)",
    "digital_assets_reserves_onchain_finance": "float (0.0 to 1.0)",
    "monetary_policy_regime_shift_rate_cycle": "float (0.0 to 1.0)",
    "commodity_supercycle_supply_rebalancing": "float (0.0 to 1.0)"
  },
  "affected_tickers": ["string (specific ticker symbols most impacted, max 5)"],
  "affected_asset_classes": ["string (e.g. 'tech', 'commodities', 'currencies', 'crypto', 'biotech', 'industrials', 'consumer')"]
}

SCORING GUIDE — Use the ENTIRE 0-100 range with NUMERIC ANCHORING:

CRITICAL: Before scoring, you MUST identify which SPECIFIC ticker(s) moved and by what MAGNITUDE. If no tracked ticker shows meaningful movement (<0.5%), the contradiction_gap MUST be 0-15. Do NOT fabricate contradiction where none exists.

NUMERIC ANCHORING TABLE:
- 0-15: No tracked ticker moved >0.5%, OR the news event has NO MATERIAL CONNECTION to the tracked assets. Reality text must state: "No material connection between this event and the tracked assets" or list specific tickers with <0.5% moves.
- 16-30: Minor tension — ticker(s) moved 0.5-1.5% in a direction that mildly contradicts the narrative. Name the ticker and its move.
- 31-50: Moderate contradiction — ticker(s) moved 1.5-3% against the narrative. Cite specific ticker(s) and their exact change_pct from market data.
- 51-75: Significant contradiction — ticker(s) moved 3-5% or 2+ tickers moved 2%+ against the narrative. Cite ALL relevant tickers and their moves.
- 76-100: Extreme contradiction — broad index moved 2%+ or sector ETF moved 5%+ directly opposing the narrative. This requires VERIFIABLE large moves in the market data provided.

GAP = floor(10 × sum of absolute percentage moves of all contradictory tickers). Example: if URA +2.31% and NLR +2.44% both contradict the narrative, GAP = floor(10 × (2.31 + 2.44)) = 47.

MATERIALITY GATE: If the news article is about a topic unrelated to any tracked ticker (e.g., Medicare policy vs energy ETFs, Social Security vs space stocks, celebrity news vs tech indices), set contradiction_gap to 0-10. Do not force a connection.

RULES:

INFORMATIONAL CASCADE (CRITICAL):
You must trace the informational cascade from big to small:
1. Deconstruct the Strategic Narrative (the big picture) into specific Claims (the small picture).
2. Evaluate how those Claims feed back into the prevailing Narratives.
Your analysis in the 'trade_thesis' and 'they_say/reality' fields MUST reflect this flow from strategic narratives to claims, and from claims back to narratives.

QUOTE ANCHOR (they_say):
- they_say MUST begin with the EXACT source name from the SOURCE field provided in the prompt. Example: "Bloomberg reports: ..." or "SCMP reports: ..." or "Reuters reports: ..."
- After the source prefix, cite a SPECIFIC claim or quote from the article text. Do NOT paraphrase the media consensus into a generic abstract statement. Find something falsifiable in the article — a price prediction, a policy claim, a growth forecast, a risk assessment — and quote/paraphrase it specifically.
- A journalist reading your they_say must recognize their own reporting. If they would say "that's not what we wrote," the they_say is a straw man.
- Never begin they_say with a vague generality like "The media reports..." or "Consensus holds that..." — the source must be named and the claim must be specific.

HEADLINE VARIETY & CURIOSITY GAP:
- NEVER repeat the same structural pattern more than once per batch of 10 stories.
- Do NOT use identical verb forms (Fails, Ignores, Contradicts, Defies, Shrugs, Unmoved) more than once per batch of 10.
- CURIOSITY GAP RULE: Never write descriptive, literal RSS-style headlines. The headline must create tension and make the reader NEED to scroll for the trade setup.
- INFORMATION ASYMMETRY: When GAP > 60, frame the media narrative as the "official story" and the capital flow as the "real story."
- CONTRARIAN FORMULA — YOU MUST USE ONE OF THESE PATTERNS:
  Pattern A: [Unpopular Truth] + [Hidden Capital Divergence]
    Example: "Normies are quietly dumping Lithium space while retail buys the Sodium hype."
  Pattern B: [Specific Number/Price Action] + [Expected Value Disconnect]
    Example: "$214M exited XOM this week. The media's implied odds are completely busted."
  Pattern C: [Question Hook] + [The Data Answer]
    Example: "Why is NVDA down 3% while every analyst upgrades? Fade the public."
  Pattern D: [Who's Wrong] + [Who's Right]
    Example: "CNBC calls it a tech rally. The capital ledger calls it a massive trap."
- Every headline MUST contain EITHER a specific number, a specific ticker, OR a specific contradiction. No passive summaries. No "X meets Y" academic language.

TEMPLATE ANTI-ROT (BANNED PHRASES):
- NEVER use these phrases, stems, or any close variant: "fails to", "market unmoved", "markets shrug", "markets unfazed", "no market impact", "fails to ignite", "fails to dent", "fails to boost", "fails to lift".
- "Fails to" is banned in ANY context: "fails to move markets", "fails to move tracked assets", "fails to react", "fails to respond", "fails to shift" — all variants of "fails to [verb]" are prohibited.
- "Unmoved" is banned in ANY context: "market unmoved", "prices unmoved", "assets unmoved", "traders unmoved" — all variants.
- Instead, use structural alternatives: "Market pricing fully absorbed...", "Capital flows unchanged despite...", "Price action shows no reaction to...", "Asset prices held steady through...", "Trading volume flat across...", "Markets already priced this...", "No divergence detected between narrative and price...", "Price stability confirms market consensus on..."

GAP 0-15 FRAMING (reality text):
- For GAP 0-15 stories, the reality text must explain WHY no contradiction exists. Rotate between these frames (never use the same frame twice in a batch):
  (a) "Market indifference confirms this news was already priced in."
  (b) "Low gap signals market efficiency — this information is fully reflected in current prices."
  (c) "Price action fully aligned with the narrative — no divergence detected."
  (d) "No material connection between this event and the tracked assets."
  (e) "[Ticker] moved only [X]% — well within normal noise, confirming narrative stability."

TRADE THESIS RULES (FORWARD DECLARATION — CRITICAL):
- EVERY story MUST have a trade_thesis object. NEUTRAL is only allowed when the contradiction is genuinely unactionable — and even then, you must propose a STRADDLE or volatility play with specific strike reasoning.
- direction: LONG if capital flows contradict bearish media narrative (buy the asset the media is mispricing). SHORT if capital flows contradict bullish media narrative (sell what the media is pumping). STRADDLE if volatility is underpriced relative to event risk. NEUTRAL only with a specific volatility thesis.
- limit_entry_price: CRITICAL — MUST EQUAL THE TICKER'S CURRENT MARKET PRICE. Copy it exactly from the market data provided below. If the market data shows '$46.82', write '$46.82'. This is where the trade enters RIGHT NOW. Do NOT write a future limit order or a target price. If no ticker data is available, use 'market'. UNDER NO CIRCUMSTANCES put stop-loss or take-profit values in this field.
- entry_rationale: ONE sentence explaining WHY this price. Examples: 'Retest of June 18 breakout at $46.82' or 'Local resistance from the 50-day MA.'
- stop_loss: Exact price that invalidates the thesis. A single number like '$48.50'. This is NOT the same as the invalidation narrative — it's the hard price where you exit.
- take_profit: Exact target price like '$42.00'. Use a realistic risk:reward ratio (minimum 1:1.5, preferred 1:2+).
- invalidation: MUST be a specific, falsifiable price level. If the market crosses this level, the thesis is WRONG and the position must be closed.
- conviction: TIED TO DATA THRESHOLDS — do not default to MODERATE.
  HIGH: GAP >= 75 AND capital flow velocity is clearly directional (inflow/outflow) AND the ticker moved >3%. This is a structural signal.
  ELEVATED: GAP 60-74 with directional capital flow. Good setup but less extreme divergence.
  SPECULATIVE: GAP 50-65 but capital flows are flat or mixed. The contradiction exists but the market hasn't committed yet.
  HOLD: Data is contradictory or no tracked ticker shows movement. If you can't commit, DON'T suggest a directional play — propose a volatility/STRADDLE setup or flag as unactionable. Never push a weak setup just to fill the trade_thesis field.
- horizon_days: 7 for event-driven catalysts (earnings, FOMC, OPEC), 14 for narrative divergences, 21 for structural contradictions.
- portfolio_allocation_pct: String like '1.25%'. HIGH conviction = 1.5-2.5%. MODERATE = 0.5-1.5%. SPECULATIVE = 0.25-0.5%. This signals conviction to a PM.
- alpha_trigger: This is the most important field. ONE sentence. Must answer: "What EXACTLY is the market pricing wrong?" Be specific, falsifiable, and cite a number. Example: "The market is pricing the Iran ceasefire at 70% probability (oil -3%) while capital flows into defense ETFs at 1.8x normal pace suggest the smart money gives it 30% — a 40-point probability gap that will close violently." NOT: "Markets may be mispricing geopolitical risk."
- IMPORTANT: Prefer exact prices from market data when available. 'market' is acceptable as a valid order type when no specific technical level is warranted.

NARRATIVE COALESCENCE RULES:
- If CURRENT PLATFORM STATE is provided above the news article, use it to weight your analysis.
- Narrative saturation: A GAP score on a narrative with many existing stories is LESS significant than the same GAP on a narrative with few stories. Narratives with 30+ stories are saturated — modest GAP scores there should be scored lower.
- Narrative clustering: If this headline maps to a narrative where 3+ stories already exist with similar theses, note "narrative intensification" rather than treating as novel.
- Redundancy: If the CURRENT PLATFORM STATE shows an existing trade direction for this narrative, you MUST still generate a trade thesis. Differentiate by entry price, timeframe, or ticker. Do NOT default to NEUTRAL just because a trade already exists for this narrative. Alpha generation requires density of actionable ideas, not deduplication.
- Contrarian gaps: If the CURRENT PLATFORM STATE shows a clear directional consensus for this narrative, and this headline genuinely contradicts that consensus, flag as "contrarian signal" and INCREASE the GAP score by 10-15 points.

ENTITY GROUNDING (NER CONSTRAINT):
- Isolate the prime moving entity (Subject-Action-Object) from the core news text.
- The primary_ticker you select MUST match the specific structural corporate victim or beneficiary of that action, not the thematic sector ETF.
- Example: If the news is "White House restricts advanced lithography exports," the primary_ticker must be a specific semiconductor equipment maker (e.g., ASML, AMAT, LRCX), NOT the semiconductor ETF (SMH).
- Example: If the news is "OPEC extends production cuts," the primary_ticker must be a specific producer with high beta to the decision (e.g., XOM, CVX, OXY), NOT the crude oil futures contract (CL=F).
- RULE: Always ask: "Which specific company's balance sheet does this event directly impact?" That company's ticker is your primary_ticker.

GENERAL RULES:
- contradiction_gap: The score MUST reflect the MAGNITUDE of the price move, not just direction. A 0.4% ETF dip is a 10-20 point gap at most, not an 85. Reserve extreme scores for extreme moves.
- Never invent ticker data. Only reference the market data provided in the prompt.
- narrative_scores: Score EVERY vector against this event. Most events touch 3-5 narratives. This is an asset-allocation weighting, not a binary tag. Use the FULL 0.0-1.0 range PROPORTIONALLY — a 0.9 on the primary vector might ripple at 0.3-0.4 into adjacent vectors. Set 0.0 only for genuinely unrelated vectors. Do NOT assign 1.0 to multiple vectors.
- affected_tickers: List SINGLE-NAME ticker symbols most impacted by this event (max 5, use exact symbols from market data). Prefer individual equities over ETFs. If the market data provides individual stocks, pick those. Only use an ETF if no single-name alternative exists in the provided market data.
- affected_asset_classes: List asset classes affected (e.g. "tech", "commodities", "currencies", "crypto", "biotech", "industrials", "consumer").
- they_say and reality must be specific. Use named actors, not vague generalities.
- capital_volume_usd: Follow the estimation hierarchy above. Estimate from available positioning, price, or narrative evidence. Do NOT default to 0 unless no quantifiable basis exists. Never fabricate.
- TONE: Write like a PM at a macro hedge fund briefing their team. No hedging language ("may," "could," "potentially"). No passive voice. State your thesis directly and back it with the specific data point that supports it. If you're wrong, the invalidation trigger will catch it — that's what it's for."""


def build_user_prompt(title, text, market_context, source_domain=""):
    source_line = f"SOURCE: {source_domain}" if source_domain else ""
    narrative_ctx = build_narrative_context()
    ctx_block = f"\n{narrative_ctx}\n" if narrative_ctx else ""
    return f"""{ctx_block}NEWS ARTICLE
Title: {title}
{source_line}

{text[:3000]}

MARKET DATA (current prices, organized by macro vector)
{market_context}

Analyze the contradiction between the narrative in this article and the market data above. The SOURCE field tells you which publication to cite in they_say. Score EVERY macro vector (0.0-1.0) based on how much this event impacts that thesis. Most events affect 3-5 vectors. Return ONLY the JSON object."""


async def call_llm(session, sem, item_id, title, text, market_context, source_domain="", subnarratives_context=""):
    """Send one item to the GCP Cloud Function."""
    async with sem:
        await asyncio.sleep(random.uniform(*REQUEST_JITTER))
        payload = {
            "title": title,
            "text": text,
            "source_url": source_domain,
            "subnarratives_context": subnarratives_context
        }
        
        try:
            async with session.post(
                "https://gazzetta-content-agent-3vl4w52gea-uc.a.run.app", 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    print(f"  [{item_id}] GCP Agent HTTP {resp.status}: {body[:200]}")
                    return (item_id, None, "gcp_error")
                
                story = await resp.json()
                
                # Adapt the new GCP schema back into the legacy format that SQLite expects
                story["headline"] = story.get("title", "Untitled")
                story["they_say"] = story.get("reality", "")
                story["reality"] = story.get("market_implication", "")
                story["contradiction_gap"] = story.get("contradiction_gap", 0)
                
                # Make sure container is picked up by assemble_story's primary logic
                if "container" in story:
                    story["narrative_weights"] = {story["container"]: 1.0}
                    
                # Also pass the subnarrative forward via pillar/tags
                story["pillar"] = story.get("subnarrative", "")
                
                return (item_id, story, "ok")
        except Exception as e:
            print(f"  [{item_id}] GCP Agent Exception: {e}")
            return (item_id, None, "gcp_exception")


# ── story assembly ──────────────────────────────────────────────────
def assemble_story(db_item, llm_story, prices):
    """Merge DB metadata + LLM analysis into a frontend-compatible story dict."""
    item_id, source_url, source_type, title, full_text, narrative_tag = db_item
    if not narrative_tag:
        narrative_tag = "tech_convergence_platforms_ai_autonomy"

    # ── Multi-vector scoring: extract narrative_scores matrix from LLM ──
    scores = llm_story.get("narrative_scores", {})
    if scores:
        scores = {k: v for k, v in scores.items() if k is not None}

    # Fallback: if LLM returned old single-tag format, normalize to matrix
    if not scores:
        old_tag = llm_story.get("narrative_tag", narrative_tag) or narrative_tag
        scores = {old_tag: 1.0}

    # Primary narrative = highest score
    primary = max(scores, key=scores.get) if scores else narrative_tag

    # Multi-container: any vector scoring >= 0.40 threshold
    containers_list = [nid for nid, score in scores.items() if score >= 0.40]
    if not containers_list:
        containers_list = [primary]

    # Extract LLM-suggested affected tickers/asset classes
    llm_tickers = llm_story.get("affected_tickers", [])
    # Fix #6: Normalize tickers — strip $/#, uppercase, validate
    _clean_tickers = []
    for _t in (llm_tickers or []):
        _tc = str(_t).strip().upper().replace('$','').replace('#','')
        if _tc and len(_tc) >= 2 and _tc not in ('T','TEST','UNKNOWN','NULL','N/A'):
            _clean_tickers.append(_tc)
    llm_tickers = _clean_tickers
    llm_asset_classes = llm_story.get("affected_asset_classes", [])

    container = primary  # backward compat for legacy scripts
    contradiction_gap = int(llm_story.get("contradiction_gap", 50))
    llm_volume = int(llm_story.get("capital_volume_usd", 0))

    # ── Phase B1: extract trade_thesis from LLM output ──
    trade_thesis = llm_story.get("trade_thesis", {}) or {}
    trade_direction = trade_thesis.get("direction", "NEUTRAL")
    trade_ticker = trade_thesis.get("primary_ticker", "")

    # ═══════════════════════════════════════════════════════════════
    # ASSET WHITELIST — single-name ticker universe
    # ═══════════════════════════════════════════════════════════════
    TICKER_WHITELIST = {
        "usd_debasement_reserve_diversification": ["EURUSD=X", "GLD", "SLV"],
        "critical_resource_control_infrastructure": ["XOM", "CVX", "CCJ", "URNM"],
        "supply_chain_resilience_reshoring_defense": ["CAT", "GE", "XLI", "RTX"],
        "china_geoeconomic_expansion": ["BABA", "PDD", "FXI", "KWEB"],
        "space_economy_commercialization": ["RKLB", "ARKX"],
        "gene_editing_biotech_longevity": ["CRSP", "ARKG", "XBI"],
        "tech_convergence_platforms_ai_autonomy": ["AAPL", "MSFT", "QQQ"],
        "prestige_asset_acquisition_strategic_investment": ["BATRK", "MSGS", "MANU"],
        "ai_compute_semiconductor_hegemony": ["NVDA", "AMD", "SMH"],
        "digital_assets_reserves_onchain_finance": ["BTC-USD", "MSTR", "COIN"],
        "monetary_policy_regime_shift_rate_cycle": ["TLT", "IEF", "SHY"],
        "commodity_supercycle_supply_rebalancing": ["XOM", "CAT", "DBC", "COP"],
    }
    _all_whitelisted = []
    for _tlist in TICKER_WHITELIST.values():
        _all_whitelisted.extend(_tlist)
    _narrative_tickers = TICKER_WHITELIST.get(narrative_tag, [])
    _fallback_ticker = _narrative_tickers[0] if _narrative_tickers else "SPY"

    if not trade_ticker or trade_ticker not in _all_whitelisted:
        trade_ticker = _fallback_ticker

    trade_entry = trade_thesis.get("limit_entry_price", trade_thesis.get("entry_zone", ""))
    trade_entry_rationale = trade_thesis.get("entry_rationale", "")
    trade_stop = trade_thesis.get("stop_loss", "")
    trade_target = trade_thesis.get("take_profit", "")
    trade_invalidation = trade_thesis.get("invalidation", "")
    trade_conviction = trade_thesis.get("conviction", "SPECULATIVE")
    trade_horizon = int(trade_thesis.get("horizon_days", 14))
    trade_alpha = trade_thesis.get("alpha_trigger", "")
    trade_alloc = trade_thesis.get("portfolio_allocation_pct", "")

    # ═══════════════════════════════════════════════════════════════
    # DETERMINISTIC CONVICTION GRADING (Python override — not LLM)
    # ═══════════════════════════════════════════════════════════════
    is_directional = trade_direction in ("LONG", "SHORT")
    if contradiction_gap >= 75 and is_directional:
        trade_conviction = "HIGH"
    elif contradiction_gap >= 60 and is_directional:
        trade_conviction = "ELEVATED"
    elif contradiction_gap >= 50 and is_directional:
        trade_conviction = "SPECULATIVE"
    elif contradiction_gap >= 50 and not is_directional:
        trade_conviction = "SPECULATIVE"
    else:
        trade_conviction = "HOLD"

    # Trust Layer v1: accept LLM capital volume estimate with sanity cap
    # Estimation hierarchy: CFTC notional > price proxy > narrative inference > 0
    # See docs/INTELLIGENCE_DEFINITIONS.md for full semantics
    try:
        llm_volume = int(llm_story.get("capital_volume_usd", 0) or 0)
    except (ValueError, TypeError):
        llm_volume = 0
    capital_volume_usd = min(max(0, llm_volume), 500_000_000_000)
    # Telemetry for future audit
    if capital_volume_usd >= 500_000_000_000:
        print(f"  [CAPFLOW] CAPPED at 500B for story {item_id}")

    # Estimate capital flow direction from gap + reality text
    reality = llm_story.get("reality", "")
    if any(w in reality.lower() for w in ["surge", "rally", "inflow", "up", "gain", "bullish"]):
        direction = "inflow"
    elif any(w in reality.lower() for w in ["plunge", "sell", "outflow", "down", "drop", "bearish"]):
        direction = "outflow"
    else:
        direction = "neutral"

    # Derive asset_class from narrative
    narrative_asset_map = {
        "usd_debasement_reserve_diversification": "currencies",
        "critical_resource_control_infrastructure": "commodities",
        "supply_chain_resilience_reshoring_defense": "industrials",
        "china_geoeconomic_expansion": "tech",
        "space_economy_commercialization": "tech",
        "gene_editing_biotech_longevity": "biotech",
        "tech_convergence_platforms_ai_autonomy": "tech",
        "prestige_asset_acquisition_strategic_investment": "consumer",
        "ai_compute_semiconductor_hegemony": "tech",
        "digital_assets_reserves_onchain_finance": "crypto",
        "monetary_policy_regime_shift_rate_cycle": "currencies",
        "commodity_supercycle_supply_rebalancing": "commodities",
    }

    now_ts = datetime.now(timezone.utc).isoformat()
    computed_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80] if title else ""

    # ── HEADLINE SANITIZER: hard code-level guard against banned template patterns ──
    raw_headline = llm_story.get("headline", title)[:120]
    # Phase A: expanded rot patterns — swapped banned phrase for approved neutral alternative
    # instead of substituting another bad template ("leaves market pricing unchanged")
    rot_patterns = [
        (r'\b(fails?\s+to\s+\w+|market\s+unmoved|markets?\s+shrug|markets?\s+unfazed|no\s+market\s+impact)\b',
         "finds no immediate market catalyst in"),
        (r'\bleaves?\s+market\s+pricing\s+unchanged\b',
         "finds no immediate market catalyst in"),
        (r'\bas\s+markets\s+rally\b',
         "while tracked sectors diverge:"),
        (r'\bovershadowed\s+by\s+(?:a\s+)?(?:tech\s+)?rally\b',
         "concurrent with tech-sector outperformance in"),
    ]
    for pattern, replacement in rot_patterns:
        if re.search(pattern, raw_headline, re.IGNORECASE):
            raw_headline = re.sub(pattern, replacement, raw_headline, flags=re.IGNORECASE)
            raw_headline = re.sub(r'\s+', ' ', raw_headline).strip()
    sanitized_headline = raw_headline

    return {
        # ── IDENTITY ──
        "story_id": 10000 + item_id,
        "headline": sanitized_headline,
        "slug": computed_slug,

        # ── CORE CONTRADICTION ──
        "they_say": llm_story.get("they_say", title),
        "they_say_quote_verified": False,             # Pass 1 safe default
        "quote_source_url": source_url,               # RSS <link>, not LLM
        "reality": reality,
        "reality_data_sources": [],                   # Pass 1 safe default

        # ── NARRATIVE LINKAGE ──
        "narrative_id": primary,
        "narrative_confidence": scores.get(primary, 0.0),

        # ── SCORING (existing + new decomposed) ──
        "contradiction_score": contradiction_gap,     # KEPT for backward compat
        "contradiction_gap": contradiction_gap,
        "divergence_magnitude": 0.0,                  # Pass 1 safe default
        "capital_significance": 0.0,                  # Pass 1 safe default
        "causal_strength": 0.0,                       # Pass 1 safe default

        # ── CAPITAL AT STAKE ──
        "capital_volume_usd": capital_volume_usd,     # KEPT for backward compat
        "capital_at_stake_usd": capital_volume_usd,   # mirrors volume until Phase 1
        "capital_base_usd": 0,                        # Pass 1 safe default
        "impact_factor": 0.0,                         # Pass 1 safe default
        "narrative_implied_flow_usd": 0,              # Pass 1 safe default
        "actual_flow_usd": 0,                         # Pass 1 safe default
        "data_fidelity": "TIER_3",                    # "unverified" until Phase 1
        "capital_flow_confidence": (
            "HIGH" if capital_volume_usd > 0 and reality and any(w in reality.lower() for w in ["cftc","cot","positioning","contract","open interest"])
            else "MEDIUM" if capital_volume_usd > 0 and reality and any(w in reality.lower() for w in ["price","ticker","volume","etf","aum"])
            else "LOW" if capital_volume_usd > 0
            else "NONE"
        ),
        "estimation_method": (
            "cftc_notional" if capital_volume_usd > 0 and reality and any(w in reality.lower() for w in ["cftc","cot","positioning","contract"])
            else "price_proxy" if capital_volume_usd > 0 and reality and any(w in reality.lower() for w in ["price","ticker","volume","etf","aum"])
            else "llm_inference" if capital_volume_usd > 0
            else "none"
        ),
        "materiality_pass": True,                     # don't gate existing items
        "confidence_pct": 65,                         # KEPT for backward compat

        # ── EVENT & CAUSALITY ──
        "event_type": "unclassified",                 # Pass 1 safe default
        "event_magnitude": 0.0,                       # Pass 1 safe default
        "causal_chain": "",                           # Pass 1 safe default
        "geopolitical_dimension": "none",             # Pass 1 safe default
        "time_horizon": "tactical",                   # Pass 1 safe default

        # ── AFFECTED ASSETS ──
        "affected_tickers": llm_tickers if llm_tickers else TICKER_WHITELIST.get(primary, []),
        "affected_asset_classes": llm_asset_classes if llm_asset_classes else [narrative_asset_map.get(primary, "mixed")],

        # ── CONTENT ARTIFACTS ──
        "brief_review": "",                           # Pass 1 safe default
        "contradiction_note": "",                     # Pass 1 safe default
        "implication_note": "",                       # Pass 1 safe default
        "actionable_trade": trade_direction,             # Phase B1: trade direction from LLM
        "trade_thesis": {
            "direction": trade_direction,
            "primary_ticker": trade_ticker,
            "limit_entry_price": trade_entry,
            "entry_rationale": trade_entry_rationale,
            "stop_loss": trade_stop,
            "take_profit": trade_target,
            "invalidation": trade_invalidation,
            "conviction": trade_conviction,
            "horizon_days": trade_horizon,
            "portfolio_allocation_pct": trade_alloc,
            "alpha_trigger": trade_alpha,
        },

        # ── METADATA ──
        "container": container,                       # primary narrative (backward compat)
        "containers": containers_list,                # NEW: multi-vector routing array
        "narrative_weights": scores,                  # NEW: full 12-vector score matrix
        "tier": gap_to_tier(contradiction_gap),
        "alert": contradiction_gap >= 80,              # Contradiction Alert trigger (GAP ≥ 80)
        "pillar": llm_story.get("subnarrative", primary),
        "sector": narrative_asset_map.get(primary, "mixed"),
        "tags": containers_list,
        "entity_tags": [],                            # Pass 1 safe default
        "source_name": extract_domain(source_url) or source_type.title(),
        "source_url": source_url,
        "feed_source": extract_domain(source_url),
        "generated_at": now_ts,
        "freshness": 1.0,                             # will be computed by decay
        "time_decay": 0.0,                            # will be computed by decay

        # ── KEPT FOR BACKWARD COMPAT ──
        "capital_flow": {
            "direction": direction,
            "amount_b": capital_volume_usd / 1e9 if capital_volume_usd else None,
            "asset_class": narrative_asset_map.get(narrative_tag, "mixed"),
            "projected": reality[:500],
        },
    }


def fresh_skeleton():
    # Fresh skeleton — 12 narratives
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "contradiction_synthesizer.py v1.0",
        "containers": {
            "usd_debasement_reserve_diversification": {"title": "USD Debasement & Reserve Diversification", "subtitle": "De-dollarization and reserve reallocation", "count": 0, "stories": []},
            "critical_resource_control_infrastructure": {"title": "Critical Resource Control & Energy Infrastructure", "subtitle": "Energy security and critical minerals", "count": 0, "stories": []},
            "supply_chain_resilience_reshoring_defense": {"title": "Reshoring, Defense Logistics & Supply-Chain Resilience", "subtitle": "Relocalization of critical supply chains", "count": 0, "stories": []},
            "china_geoeconomic_expansion": {"title": "China Geoeconomic Expansion & Market Integration", "subtitle": "Belt and Road, trade corridors", "count": 0, "stories": []},
            "space_economy_commercialization": {"title": "Space Economy Commercialization & Infrastructure", "subtitle": "LEO infrastructure and satellite services", "count": 0, "stories": []},
            "gene_editing_biotech_longevity": {"title": "Gene Editing, Biotech & Longevity Science", "subtitle": "CRISPR and advanced biologics", "count": 0, "stories": []},
            "tech_convergence_platforms_ai_autonomy": {"title": "Tech Convergence: Enterprise Platforms & Autonomous AI", "subtitle": "AI, cloud, and autonomous workflows", "count": 0, "stories": []},
            "prestige_asset_acquisition_strategic_investment": {"title": "Prestige Asset Acquisition & Strategic Cross-Border Investment", "subtitle": "Sports teams and strategic infrastructure", "count": 0, "stories": []},
            "ai_compute_semiconductor_hegemony": {"title": "AI Hardware, Compute Concentration & Semiconductor Leadership", "subtitle": "Semiconductor manufacturing and AI accelerators", "count": 0, "stories": []},
            "digital_assets_reserves_onchain_finance": {"title": "Digital Assets as Reserve & On-Chain Financial Infrastructure", "subtitle": "Institutional crypto and tokenized reserves", "count": 0, "stories": []},
            "monetary_policy_regime_shift_rate_cycle": {"title": "Monetary Policy Regime Shifts & Rate Cycle Dynamics", "subtitle": "Central bank frameworks and rate cycles", "count": 0, "stories": []},
            "commodity_supercycle_supply_rebalancing": {"title": "Commodity Re-acceleration & Physical Supply Rebalancing", "subtitle": "Structural demand and logistics constraints", "count": 0, "stories": []},
        },
        "all_stories": [],
        "tags_index": {},
        "total_stories": 0,
    }


# ── stories.json I/O ────────────────────────────────────────────────
def load_existing_stories():
    """Return the current stories.json as a dict, or a fresh skeleton."""
    if STORIES_PATH.exists():
        try:
            with open(STORIES_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARNING: stories.json corrupt ({e}). Starting fresh.")
    return fresh_skeleton()


def merge_stories(existing, new_stories):
    """Prepend new stories, maintain chronological sort, update containers."""
    all_stories = new_stories + existing.get("all_stories", [])
    # Sort: newest first by generated_at
    all_stories.sort(key=lambda s: s.get("generated_at", ""), reverse=True)

    # ── Quality gate: deduplicate stories with identical reality text ──
    seen_reality = {}
    deduped = []
    for s in all_stories:
        reality_key = (s.get("reality", "") or "")[:120]
        if reality_key in seen_reality:
            existing_gap = seen_reality[reality_key].get("contradiction_gap", 0)
            this_gap = s.get("contradiction_gap", 0)
            if this_gap > existing_gap:
                # Replace: this story has higher contradiction gap on same data
                deduped[deduped.index(seen_reality[reality_key])] = s
                seen_reality[reality_key] = s
            # else: drop this story (lower gap, same reality)
        else:
            seen_reality[reality_key] = s
            deduped.append(s)
    all_stories = deduped

    # ── Quality gate: cap at 20 stories per narrative, archive excess to avoid data loss ──
    MAX_PER_NARRATIVE = 20
    active_stories = []
    archived_stories = []
    container_counts = {}
    
    # Sort all_stories by generated_at descending (newest first)
    all_stories.sort(key=lambda s: s.get("generated_at", ""), reverse=True)
    
    for s in all_stories:
        story_containers = s.get("containers") or [s.get("container", "tech_convergence_platforms_ai_autonomy")]
        c = s.get("container", story_containers[0])
        n = container_counts.get(c, 0)
        
        # Apply decay calculation
        compute_decay(s)
        
        if n < MAX_PER_NARRATIVE:
            active_stories.append(s)
            container_counts[c] = n + 1
        else:
            archived_stories.append(s)
            
    all_stories = active_stories

    if archived_stories:
        try:
            archive_dir = DATA_DIR / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / "archived_stories.jsonl"
            # Read existing archived story IDs to avoid duplicates
            existing_archived_ids = set()
            if archive_path.exists():
                with open(archive_path) as f:
                    for line in f:
                        try:
                            item = json.loads(line)
                            if "story_id" in item:
                                existing_archived_ids.add(item["story_id"])
                        except:
                            pass
            
            with open(archive_path, "a") as f:
                for s in archived_stories:
                    if s.get("story_id") not in existing_archived_ids:
                        f.write(json.dumps(s, ensure_ascii=False) + "\n")
            print(f"  [archive] Archived {len(archived_stories)} old/excess stories to {archive_path}")
        except Exception as e:
            print(f"  WARNING: failed to write archive: {e}")

    # Rebuild containers using fresh skeleton titles/subtitles to enforce updated names
    skeleton = fresh_skeleton()
    containers = {}
    for k, v in skeleton["containers"].items():
        containers[k] = {
            "title": v["title"],
            "subtitle": v["subtitle"],
            "count": 0,
            "stories": []
        }

    for s in all_stories:
        story_containers = s.get("containers") or [s.get("container", "tech_convergence_platforms_ai_autonomy")]
        for c in story_containers:
            if c in containers:
                containers[c]["stories"].append(s)
                containers[c]["count"] += 1

    # Rebuild tags_index from current all_stories (removes orphaned IDs)
    tags_index = {}
    for s in all_stories:
        sid = str(s.get("story_id", ""))
        for tag in s.get("tags", []):
            if tag not in tags_index:
                tags_index[tag] = []
            if sid and sid not in tags_index[tag]:
                tags_index[tag].append(sid)

    # Apply decay computation to all stories (new + legacy)
    for s in all_stories:
        compute_decay(s)

    # ── TIER HARDENER: recompute tier from contradiction_gap for every story ──
    # This is a post-merge safety net. Whatever happened during assembly,
    # tier is now guaranteed to match the stored gap.
    for s in all_stories:
        gap_val = s.get("contradiction_gap", 0) or 0
        try:
            gap_val = float(gap_val)
        except (ValueError, TypeError):
            gap_val = 0
        if gap_val > 50:
            s["tier"] = "BREAKING"
        elif gap_val >= 20:
            s["tier"] = "ACTIVE"
        else:
            s["tier"] = "SETTLING"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "contradiction_synthesizer.py v1.0",
        "containers": containers,
        "all_stories": all_stories,
        "tags_index": tags_index,
        "total_stories": len(all_stories),
    }


def atomic_write_stories(doc):
    """Write doc to .tmp.json, validate, os.replace()."""
    with open(TMP_PATH, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    # Validate
    with open(TMP_PATH) as f:
        validated = json.load(f)
    for key in ["generated_at", "containers", "all_stories", "total_stories"]:
        if key not in validated:
            raise ValueError(f"VALIDATION FAILED: missing '{key}'")
    if not isinstance(validated["all_stories"], list):
        raise ValueError("VALIDATION FAILED: all_stories not a list")
    if not isinstance(validated["containers"], dict):
        raise ValueError("VALIDATION FAILED: containers not a dict")

    # Atomic swap
    os.replace(TMP_PATH, STORIES_PATH)

    # Mirror to data/ for consistency
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    mirror = DATA_DIR / "stories.json"
    mirror.write_text(STORIES_PATH.read_text())

    print(f"  ✓ stories.json — {validated['total_stories']} total stories")
    for cname, cdata in validated["containers"].items():
        print(f"    {cname:28s} {cdata['count']:4d}")


# ── main ────────────────────────────────────────────────────────────
async def run(max_items=None, dry_run=False):
    lock = PipelineLock()
    if not lock.acquire():
        sys.exit(0)

    conn = None
    try:
        conn = get_db()
        ensure_processed_column(conn)

        # 1. Load unprocessed items
        limit = max_items or BATCH_SIZE
        items = fetch_unprocessed(conn, limit)
        if not items:
            print("No unprocessed items. Exiting.")
            return

        print(f"Processing {len(items)} items...")

        # 2. Load market prices and auxiliary data
        prices = load_market_prices()
        
        technicals = {}
        if (DATA_DIR / "technicals.json").exists():
            try: technicals = json.load(open(DATA_DIR / "technicals.json")).get("data", {})
            except: pass
            
        options = {}
        if (DATA_DIR / "options_sentiment.json").exists():
            try: options = json.load(open(DATA_DIR / "options_sentiment.json"))
            except: pass

        # 3. Build full-market context (all 12 vectors — single snapshot)
        market_context = pick_market_context(prices, technicals, options)
        
        # 3.5 Load subnarratives context
        narratives_config = load_narratives_config()
        subnarratives_list = []
        for n_id, n_data in narratives_config.items():
            subs = n_data.get("subnarratives", {})
            for sub_id, sub_data in subs.items():
                subnarratives_list.append(f"- {sub_id} (Parent: {n_id}): {sub_data.get('description', '')}")
        subnarratives_context = "\n".join(subnarratives_list)

        # 4. Async DeepSeek calls
        sem = asyncio.Semaphore(MAX_CONCURRENT)
        async with aiohttp.ClientSession() as session:
            tasks = []
            for item in items:
                item_id = item[0]
                source_url = item[1] or ""
                source_domain = extract_domain(source_url)
                title = item[3] or ""
                text = item[4] or ""

                tasks.append(
                    call_llm(session, sem, item_id, title, text, market_context, source_domain, subnarratives_context)
                )

            results = await asyncio.gather(*tasks)

        # 5. Process results
        new_stories = []
        for item_id, llm_story, status in results:
            if llm_story is None:
                if status == "rate_limited":
                    # Don't mark as processed — retry next run
                    continue
                else:
                    mark_error(conn, item_id)
                    continue

            # Find the original DB item
            db_item = next((it for it in items if it[0] == item_id), None)
            if db_item is None:
                continue

            try:
                story = assemble_story(db_item, llm_story, prices)
                new_stories.append(story)
                if not dry_run:
                    mark_processed(conn, item_id)
                print(
                    f"  ✓ [{item_id}] gap={story['contradiction_gap']:3d}  "
                    f"tier={story['tier']:10s}  vol=${story['capital_volume_usd']:,}  "
                    f"→ {', '.join(story.get('containers', [story['container']]))}"
                )
            except Exception as e:
                print(f"  ✗ [{item_id}] assembly error: {e}")
                mark_error(conn, item_id)

        if not new_stories:
            print("No new stories generated.")
            # Still run tier hardener on existing data (defense-in-depth)
            existing = load_existing_stories()
            for s in existing.get("all_stories", []):
                gap_val = s.get("contradiction_gap", 0) or 0
                try: gap_val = float(gap_val)
                except: gap_val = 0
                if gap_val > 50: s["tier"] = "BREAKING"
                elif gap_val >= 20: s["tier"] = "ACTIVE"
                else: s["tier"] = "SETTLING"
            existing["generated_at"] = datetime.now(timezone.utc).isoformat()
            atomic_write_stories(existing)
            return

        # 6. Merge with existing stories.json
        if dry_run:
            print(f"\nDRY RUN: {len(new_stories)} stories would be written.")
            for s in new_stories:
                print(f"  {s['headline'][:100]}")
            return

        existing = load_existing_stories()
        merged = merge_stories(existing, new_stories)
        atomic_write_stories(merged)

        print(f"\nDone. {len(new_stories)} new stories merged into {merged['total_stories']} total.")

    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        if lock.acquired:
            lock.set_error()
        sys.exit(1)
    finally:
        if conn:
            conn.close()
        lock.release()


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Contradiction Synthesizer — DeepSeek-powered news analysis"
    )
    ap.add_argument("--max-items", type=int, default=None,
                    help=f"Max items to process (default: {BATCH_SIZE})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch + analyze but don't write stories.json")
    args = ap.parse_args()



    asyncio.run(run(max_items=args.max_items, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
