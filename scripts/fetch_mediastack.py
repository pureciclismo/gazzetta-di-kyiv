#!/usr/bin/env python3
"""
fetch_mediastack.py — Mediastack API news collector for La Gazzetta di Kyiv.
Queries real-time geopolitical/macro news aligned with our 12 narratives and
feeds them into the SQLite database triage (ingestion_hashes table).

Features:
  - Cache/rate gate: runs once every 4 hours by default to protect 10k monthly quota.
  - Dedup: computes SHA-256 hashes of articles to prevent duplicate database entries.
  - Narrative alignment: uses targeted keywords for each narrative.

Usage:
  python3 scripts/fetch_mediastack.py
  python3 scripts/fetch_mediastack.py --force       # bypass the 4h time gate
  python3 scripts/fetch_mediastack.py --dry-run     # print queries/results without DB writes
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
STATE_FILE = PROJECT / "data" / "mediastack_state.json"
MEDIASTACK_KEY = os.environ.get("MEDIASTACK_API_KEY", "6fd03d0ce12a1572d37c10802c9138bb")
MIN_INTERVAL_HOURS = 4

# Map the 12 narratives to highly relevant search keywords for Mediastack API
NARRATIVE_QUERIES = {
    "usd_debasement_reserve_diversification": "de-dollarization",
    "critical_resource_control_infrastructure": "energy security",
    "supply_chain_resilience_reshoring_defense": "reshoring",
    "china_geoeconomic_expansion": "Belt and Road",
    "space_economy_commercialization": "SpaceX LEO",
    "gene_editing_biotech_longevity": "CRISPR gene",
    "tech_convergence_platforms_ai_autonomy": "autonomous AI",
    "prestige_asset_acquisition_strategic_investment": "sovereign wealth fund",
    "ai_compute_semiconductor_hegemony": "semiconductor GPU",
    "digital_assets_reserves_onchain_finance": "stablecoin reserves",
    "monetary_policy_regime_shift_rate_cycle": "interest rates",
    "commodity_supercycle_supply_rebalancing": "commodity supercycle",
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

def fetch_mediastack_news(keywords: str, limit: int = 15) -> list:
    """Fetch news from Mediastack API for given keywords."""
    params = {
        "access_key": MEDIASTACK_KEY,
        "languages": "en",
        "limit": limit,
        "keywords": keywords,
    }
    url = f"http://api.mediastack.com/v1/news?{urllib.parse.urlencode(params)}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GazzettaMediastack/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                if "error" in data:
                    print(f"  ⚠ Mediastack API error: {data['error']}", file=sys.stderr)
                    return []
                return data.get("data", [])
        except Exception as e:
            print(f"  ⚠ Request failed (attempt {attempt+1}/3): {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
            
    return []

def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if not MEDIASTACK_KEY:
        print("❌ MEDIASTACK_API_KEY not set.", file=sys.stderr)
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
        print(f"⏭ Skipping Mediastack fetch — last run {elapsed:.1f}h ago (wait {remaining:.1f}h or use --force)")
        return 0

    print(f"[mediastack] Initializing news collection for {len(NARRATIVE_QUERIES)} narratives...")
    
    conn = get_db()
    ensure_tables(conn)

    total_fetched = 0
    total_new = 0

    for idx, (narrative, query) in enumerate(NARRATIVE_QUERIES.items()):
        if idx > 0:
            time.sleep(1.5)  # Pace requests to avoid HTTP 429 Rate Limit
        print(f"  Querying [{narrative}] with keywords: '{query}'...")
        articles = fetch_mediastack_news(query)
        narrative_new = 0
        
        for art in articles:
            title = art.get("title")
            url = art.get("url")
            desc = art.get("description") or ""
            source = art.get("source") or "Unknown"
            
            if not title or not url:
                continue
                
            total_fetched += 1
            full_text = f"{title}\n\n{desc}\n\nSource: {source}"
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
        print(f"\n✅ Mediastack fetch complete: {total_new} new items ingested out of {total_fetched} processed.")
    else:
        print(f"\n🔍 Dry run complete: {total_new} new items would have been ingested.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
