#!/usr/bin/env python3
"""
fetch_newsdata.py — NewsData.io API news collector for La Gazzetta di Kyiv.
Queries geopolitical and macroeconomic news matching our 12 macro narratives
and stores them in gazzetta.db (ingestion_hashes table) for LLM synthesis.

Features:
  - Cache/rate gate: runs once every 4 hours to protect API limits.
  - Dedup: SHA-256 hashes of articles.
  - Narrative alignment: maps queries targeted to our 12 macro-contradictions.
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# -- config ----------------------------------------------------------
PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("GAZZETTA_DB_PATH", str(PROJECT / "data" / "gazzetta.db"))
STATE_FILE = PROJECT / "data" / "newsdata_state.json"
NEWSDATA_KEY = os.environ.get("NEWSDATA_API_KEY", "pub_d321fd4abba542f2b6eab3c7658756e2")
MIN_INTERVAL_HOURS = 4

# Target search queries for the 12 narratives
NARRATIVE_QUERIES = {
    "usd_debasement_reserve_diversification": "de-dollarization OR BRICS currency",
    "critical_resource_control_infrastructure": "energy infrastructure security OR gas pipeline",
    "supply_chain_resilience_reshoring_defense": "reshoring OR nearshoring defense manufacturing",
    "china_geoeconomic_expansion": "China Belt and Road geoeconomic",
    "space_economy_commercialization": "satellite constellation LEO commercial space",
    "gene_editing_biotech_longevity": "CRISPR gene therapy longevity biotech",
    "tech_convergence_platforms_ai_autonomy": "autonomous AI agent drone robotics",
    "prestige_asset_acquisition_strategic_investment": "sovereign wealth fund acquisition",
    "ai_compute_semiconductor_hegemony": "semiconductor GPU fabrication supply chain",
    "digital_assets_reserves_onchain_finance": "stablecoin CBDC digital asset reserve",
    "monetary_policy_regime_shift_rate_cycle": "interest rate hike Fed central bank",
    "commodity_supercycle_supply_rebalancing": "commodity supercycle uranium copper lithium",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_hashes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hash          TEXT NOT NULL UNIQUE,
    source_url    TEXT NOT NULL,
    source_type   TEXT NOT NULL CHECK (source_type IN ('rss','youtube','manual')),
    title         TEXT,
    text_preview  TEXT,
    full_text     TEXT,
    narrative_tag TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
)
"""

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def ensure_tables(conn):
    conn.execute(CREATE_TABLE_SQL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_hash ON ingestion_hashes(hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_source ON ingestion_hashes(source_url)")
    conn.commit()

def hash_exists(conn, sha256_hex):
    row = conn.execute("SELECT 1 FROM ingestion_hashes WHERE hash=?", (sha256_hex,)).fetchone()
    return row is not None

def save_ingestion(conn, h, url, stype, title, text, narrative=None):
    if hash_exists(conn, h):
        return False
    preview = text[:500] if text else ""
    conn.execute(
        """INSERT INTO ingestion_hashes
           (hash, source_url, source_type, title, text_preview, full_text, narrative_tag)
           VALUES (?,?,?,?,?,?,?)""",
        (h, url, stype, title, preview, text, narrative),
    )
    conn.commit()
    return True

def sha256(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def fetch_newsdata_news(query: str) -> list:
    """Fetch news from NewsData.io API for the given query."""
    params = {
        "apikey": NEWSDATA_KEY,
        "language": "en",
        "q": query,
    }
    url = f"https://newsdata.io/api/1/news?{urllib.parse.urlencode(params)}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GazzettaNewsData/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                if data.get("status") == "error":
                    err = data.get("results", {}).get("message") or "Unknown API error"
                    print(f"  ⚠ NewsData.io error: {err}", file=sys.stderr)
                    return []
                return data.get("results", [])
        except Exception as e:
            print(f"  ⚠ Request failed (attempt {attempt+1}/3): {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
            
    return []

def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if not NEWSDATA_KEY:
        print("❌ NEWSDATA_API_KEY not set.", file=sys.stderr)
        return 1

    # -- Cache/Rate gate check ---------------------------------------
    state = load_state()
    last_fetch_str = state.get("last_fetch", "1970-01-01T00:00:00Z")
    
    try:
        last_dt = datetime.fromisoformat(last_fetch_str.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
    except Exception:
        elapsed = float("inf")

    if elapsed < MIN_INTERVAL_HOURS and not force and not dry_run:
        remaining = MIN_INTERVAL_HOURS - elapsed
        print(f"Skip NewsData.io fetch — last run {elapsed:.1f}h ago (wait {remaining:.1f}h or use --force)")
        return 0

    print(f"[newsdata] Initializing news collection for {len(NARRATIVE_QUERIES)} narratives...")
    
    conn = get_db()
    ensure_tables(conn)

    total_fetched = 0
    total_new = 0

    for idx, (narrative, query) in enumerate(NARRATIVE_QUERIES.items()):
        if idx > 0:
            time.sleep(2.0)  # Rate pacing
        print(f"  Querying [{narrative}] with search term: '{query}'...")
        articles = fetch_newsdata_news(query)
        narrative_new = 0
        
        for art in articles:
            title = art.get("title")
            url = art.get("link")
            desc = art.get("description") or ""
            content = art.get("content") or ""
            source = art.get("source_id") or "Unknown"
            
            if not title or not url:
                continue
                
            total_fetched += 1
            full_text = f"{title}\n\n{desc}\n\n{content}\n\nSource: {source}"
            h = sha256(full_text)
            
            if dry_run:
                if not hash_exists(conn, h):
                    narrative_new += 1
                    total_new += 1
                    print(f"    [DRY-RUN NEW] {title[:80]} ({url})")
            else:
                if save_ingestion(conn, h, url, "rss", title, full_text, narrative):
                    narrative_new += 1
                    total_new += 1
                    print(f"    [SAVED] {title[:80]}")
                    
        print(f"  -> [{narrative}] processed: {len(articles)} articles, +{narrative_new} new items")

    conn.close()

    if not dry_run:
        state["last_fetch"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        save_state(state)
        print(f"\n✅ NewsData.io fetch complete: {total_new} new items ingested out of {total_fetched} processed.")
    else:
        print(f"\n🔍 Dry run complete: {total_new} new items would have been ingested.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
