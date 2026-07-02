#!/usr/bin/env python3
"""
fetch_newsletters.py — Gmail newsletter intelligence harvester for La Gazzetta di Kyiv.

Runs daily (via Cloud Scheduler → Cloud Run) to:
  1. Fetch the last 24h of newsletters from leonidaseldarov@gmail.com
  2. Detect newsletters by headers + volume patterns
  3. Extract structured intelligence via DeepSeek API
  4. DISCARD any newsletter not matching at least one of the 12 active narratives
  5. Auto-inject high-value items (score ≥ 7) into ingestion_hashes
     so the stories pipeline picks them up automatically
  6. Send Telegram digest of high-value items to _TCH channel

Usage:
    python scripts/fetch_newsletters.py              # production run
    python scripts/fetch_newsletters.py --dry-run    # fetch + detect, skip DeepSeek + writes
    python scripts/fetch_newsletters.py --days=7     # look back 7 days instead of 1
    python scripts/fetch_newsletters.py --test-sample  # process first 3 emails, print output
    python scripts/fetch_newsletters.py --telegram   # send digest to Telegram after run
"""

import argparse
import base64
import email
import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from pathlib import Path
from typing import Optional

import requests
import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from newsletter_prompts import SYSTEM_PROMPT, build_extraction_prompt  # noqa: E402

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("fetch_newsletters")

# ── Config ───────────────────────────────────────────────────────────────────
PROJECT_ID = "project-b7155ed8-61c1-491f-a36"
SECRET_NAME = "gmail-newsletter-token"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
GMAIL_USER = "leonidaseldarov@gmail.com"

# Newsletter detection thresholds
MIN_BODY_LENGTH = 200      # characters — ignore tiny confirmations
MAX_BODY_LENGTH = 80000    # characters — avoid giant attachments
NEWSLETTER_SCORE_THRESHOLD = 0.6  # detection confidence


# ── Secret Manager ───────────────────────────────────────────────────────────
def load_gmail_token() -> dict:
    """Load Gmail OAuth token from Secret Manager or local .gmail_token.json."""
    # Try Secret Manager first (production)
    try:
        from google.cloud import secretmanager  # type: ignore
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        token_data = json.loads(response.payload.data.decode("UTF-8"))
        log.info("Loaded Gmail token from Secret Manager")
        return token_data
    except Exception as e:
        log.warning(f"Secret Manager unavailable ({e}), trying local token file")

    # Fallback: local file (dev/testing)
    local_token = PROJECT_ROOT / ".gmail_token.json"
    if local_token.exists():
        with open(local_token) as f:
            log.info("Loaded Gmail token from local .gmail_token.json")
            return json.load(f)

    raise RuntimeError(
        "No Gmail token found. Run: python scripts/gmail_oauth_setup.py"
    )


def save_refreshed_token(token_data: dict) -> None:
    """Persist a refreshed token back to Secret Manager."""
    try:
        from google.cloud import secretmanager  # type: ignore
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{PROJECT_ID}/secrets/{SECRET_NAME}"
        payload = json.dumps(token_data).encode("UTF-8")
        client.add_secret_version(
            request={"parent": parent, "payload": {"data": payload}}
        )
        log.info("Refreshed token saved to Secret Manager")
    except Exception as e:
        log.warning(f"Could not save refreshed token to Secret Manager: {e}")
        # Save locally as fallback
        local_token = PROJECT_ROOT / ".gmail_token.json"
        with open(local_token, "w") as f:
            json.dump(token_data, f, indent=2)
        os.chmod(local_token, 0o600)


# ── Gmail auth ────────────────────────────────────────────────────────────────
def get_gmail_service():
    """Build and return an authenticated Gmail API service."""
    token_data = load_gmail_token()

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes", ["https://www.googleapis.com/auth/gmail.readonly"]),
    )

    # Refresh if expired
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            log.info("Refreshing expired Gmail token...")
            creds.refresh(Request())
            # Persist the refreshed token
            updated = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes),
            }
            save_refreshed_token(updated)
        else:
            raise RuntimeError("Gmail credentials invalid and cannot be refreshed.")

    service = build("gmail", "v1", credentials=creds)
    log.info(f"Gmail service authenticated for {GMAIL_USER}")
    return service


# ── Email fetching ────────────────────────────────────────────────────────────
def fetch_recent_messages(service, days: int = 1) -> list[dict]:
    """Fetch message IDs from the last N days."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    query = f"after:{since} -category:promotions -is:sent -is:draft"

    log.info(f"Fetching messages since {since} (last {days} day(s))")
    messages = []
    page_token = None

    while True:
        kwargs = {
            "userId": GMAIL_USER,
            "q": query,
            "maxResults": 500,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
        batch = result.get("messages", [])
        messages.extend(batch)
        log.info(f"  → fetched {len(batch)} message IDs (total: {len(messages)})")

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return messages


def get_header(headers: list[dict], name: str) -> str:
    """Extract a header value by name (case-insensitive)."""
    name_lower = name.lower()
    for h in headers:
        if h["name"].lower() == name_lower:
            return h["value"]
    return ""


def decode_subject(raw_subject: str) -> str:
    """Decode RFC2047-encoded email subject."""
    parts = decode_header(raw_subject)
    decoded = []
    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def extract_body(payload: dict, prefer_plain: bool = True) -> str:
    """Recursively extract text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain" and prefer_plain:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            return html_to_text(html)

    # Multipart — recurse
    if "parts" in payload:
        texts = []
        # Prefer plain text parts first
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                t = extract_body(part, prefer_plain=True)
                if t:
                    texts.append(t)
        if texts:
            return "\n".join(texts)
        # Fall back to HTML parts
        for part in payload["parts"]:
            if part.get("mimeType") in ("text/html", "multipart/alternative"):
                t = extract_body(part, prefer_plain=False)
                if t:
                    texts.append(t)
        return "\n".join(texts)

    return ""


def html_to_text(html: str) -> str:
    """Convert HTML to plain text (no external deps — basic regex approach)."""
    # Remove scripts and styles
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode common HTML entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    # Collapse whitespace
    html = re.sub(r"\s{3,}", "\n\n", html)
    return html.strip()


def is_newsletter(headers: list[dict], body: str, subject: str) -> tuple[bool, float]:
    """
    Detect if an email is a newsletter using header signals and heuristics.
    Returns (is_newsletter: bool, confidence: float 0-1)
    """
    score = 0.0
    signals = []

    # Strong signals (headers)
    if get_header(headers, "List-Unsubscribe"):
        score += 0.5
        signals.append("List-Unsubscribe header")

    if get_header(headers, "List-Id"):
        score += 0.3
        signals.append("List-Id header")

    if get_header(headers, "Precedence") in ("bulk", "list"):
        score += 0.2
        signals.append("Precedence: bulk/list")

    if get_header(headers, "X-Mailer") or get_header(headers, "X-Campaign-Id"):
        score += 0.2
        signals.append("ESP headers")

    # Content signals
    body_lower = body.lower()
    if "unsubscribe" in body_lower:
        score += 0.15
        signals.append("unsubscribe link in body")

    if len(body) > 500:
        score += 0.1
        signals.append(f"body length {len(body)}")

    # Negative signals
    sender = get_header(headers, "From").lower()
    if any(domain in sender for domain in ["noreply@", "no-reply@", "newsletter@", "news@", "digest@"]):
        score += 0.2
        signals.append("newsletter sender pattern")

    score = min(score, 1.0)
    result = score >= NEWSLETTER_SCORE_THRESHOLD
    log.debug(f"Newsletter detection: score={score:.2f} → {result} | {', '.join(signals)}")
    return result, score


def fetch_full_message(service, msg_id: str) -> Optional[dict]:
    """Fetch a full message with headers and body."""
    try:
        msg = service.users().messages().get(
            userId=GMAIL_USER,
            id=msg_id,
            format="full",
        ).execute()
        return msg
    except HttpError as e:
        log.error(f"Failed to fetch message {msg_id}: {e}")
        return None


# ── DeepSeek extraction ───────────────────────────────────────────────────────
def extract_intelligence(
    subject: str,
    sender_name: str,
    body_text: str,
    narratives: list[str],
    dry_run: bool = False,
) -> Optional[dict]:
    """Call DeepSeek API to extract structured intelligence from a newsletter."""
    if dry_run:
        return {"dry_run": True, "subject": subject}

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set in environment")

    prompt = build_extraction_prompt(subject, sender_name, body_text, narratives)

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.exceptions.Timeout:
        log.error(f"DeepSeek timeout for: {subject}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        log.error(f"DeepSeek response parse error for '{subject}': {e}")
        return None
    except requests.exceptions.HTTPError as e:
        log.error(f"DeepSeek API error for '{subject}': {e}")
        return None


# ── Storage ───────────────────────────────────────────────────────────────────
def load_config() -> dict:
    """Load project config.yaml."""
    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_narrative_ids(config: dict) -> list[str]:
    """Extract narrative IDs from config.yaml."""
    narratives = config.get("narratives", {})
    return list(narratives.keys())


def load_existing_newsletters() -> dict:
    """Load existing newsletters.json keyed by gmail_id."""
    out_path = PROJECT_ROOT / "data" / "newsletters.json"
    if out_path.exists():
        with open(out_path) as f:
            data = json.load(f)
        return {item["id"]: item for item in data.get("items", [])}
    return {}


def save_newsletters(items: list[dict]) -> None:
    """Write newsletters.json with rolling 30-day window."""
    out_path = PROJECT_ROOT / "data" / "newsletters.json"
    out_path.parent.mkdir(exist_ok=True)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    items = [i for i in items if i.get("received_at", "") >= cutoff]
    items.sort(key=lambda x: x.get("received_at", ""), reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log.info(f"Saved {len(items)} newsletters to {out_path}")


def save_to_db(items: list[dict]) -> None:
    """Upsert newsletter items into gazzetta.db."""
    db_path = Path(os.environ.get("GAZZETTA_DB_PATH", str(PROJECT_ROOT / "data" / "gazzetta.db")))
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS newsletters (
            id TEXT PRIMARY KEY,
            received_at TEXT,
            sender TEXT,
            sender_name TEXT,
            subject TEXT,
            summary TEXT,
            bullets TEXT,
            topics TEXT,
            narrative_matches TEXT,
            links TEXT,
            data_points TEXT,
            value_score INTEGER,
            value_score_reason TEXT,
            language TEXT,
            raw_word_count INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    for item in items:
        cur.execute("""
            INSERT OR REPLACE INTO newsletters
            (id, received_at, sender, sender_name, subject, summary, bullets,
             topics, narrative_matches, links, data_points, value_score,
             value_score_reason, language, raw_word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["id"],
            item.get("received_at"),
            item.get("sender"),
            item.get("sender_name"),
            item.get("subject"),
            item.get("summary"),
            json.dumps(item.get("bullets", [])),
            json.dumps(item.get("topics", [])),
            json.dumps(item.get("narrative_matches", [])),
            json.dumps(item.get("links", [])),
            json.dumps(item.get("data_points", [])),
            item.get("value_score"),
            item.get("value_score_reason"),
            item.get("language", "en"),
            item.get("raw_word_count", 0),
        ))

    conn.commit()
    conn.close()
    log.info(f"Upserted {len(items)} newsletters into gazzetta.db")


# ── Telegram digest ───────────────────────────────────────────────────────────
# ── Story pipeline injection ──────────────────────────────────────────────────
STORY_INJECT_MIN_SCORE = 7  # value_score threshold for story pipeline injection


def inject_into_story_pipeline(items: list[dict], dry_run: bool = False) -> int:
    """
    # Inject high-value newsletter items into ingestion_hashes so the stories
    # pipeline (ingestion_triage.py → intel_to_stories.py) picks them up.
    #
    # Criteria: value_score >= 7 AND at least one narrative_match.
    # (Items with no narrative match are already discarded before this point.)
    #
    # Returns count of newly injected items.
    """
    import hashlib

    eligible = [
        item for item in items
        if (item.get("value_score") or 0) >= STORY_INJECT_MIN_SCORE
    ]

    if not eligible:
        log.info("No items eligible for story pipeline injection")
        return 0

    if dry_run:
        log.info(f"DRY RUN: would inject {len(eligible)} items into story pipeline")
        return 0

    db_path = Path(os.environ.get("GAZZETTA_DB_PATH", str(PROJECT_ROOT / "data" / "gazzetta.db")))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    # Ensure ingestion_hashes table exists (same DDL as ingestion_triage.py)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_hashes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            hash          TEXT NOT NULL UNIQUE,
            source_url    TEXT NOT NULL,
            source_type   TEXT NOT NULL CHECK (source_type IN ('rss','youtube','manual','newsletter')),
            title         TEXT,
            text_preview  TEXT,
            full_text     TEXT,
            narrative_tag TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_hash ON ingestion_hashes(hash)")
    conn.commit()

    injected = 0
    for item in eligible:
        # Narrative tag — always present since we discard non-matched items
        matches = item.get("narrative_matches", [])
        narrative_tag = matches[0] if matches else None

        if not narrative_tag:
            log.warning(f"Skipping injection — no narrative on: {item.get('subject', '')[:60]}")
            continue

        # Build the full text for hashing and story processing
        bullets = "\n".join(f"• {b}" for b in item.get("bullets", []))
        data_points = "\n".join(
            f"[{d.get('source', '?')}] {d.get('stat', '')}" for d in item.get("data_points", [])
        )
        full_text = (
            f"[NEWSLETTER] {item.get('sender_name', '')}\n"
            f"Subject: {item.get('subject', '')}\n"
            f"Date: {item.get('received_at', '')}\n"
            f"Score: {item.get('value_score', '?')}/10\n\n"
            f"Summary:\n{item.get('summary', '')}\n\n"
            f"Key Points:\n{bullets}\n\n"
            f"Data Points:\n{data_points}"
        ).strip()

        content_hash = hashlib.sha256(full_text.encode("utf-8", errors="replace")).hexdigest()

        # Check for duplicate
        existing = conn.execute(
            "SELECT 1 FROM ingestion_hashes WHERE hash=?", (content_hash,)
        ).fetchone()

        if existing:
            log.debug(f"Already in pipeline: {item.get('subject', '')[:60]}")
            continue

        # Compose a source URL from gmail message ID
        source_url = f"gmail://leonidaseldarov@gmail.com/message/{item['id']}"

        conn.execute(
            """INSERT INTO ingestion_hashes
               (hash, source_url, source_type, title, text_preview, full_text, narrative_tag)
               VALUES (?,?,?,?,?,?,?)""",
            (
                content_hash,
                source_url,
                "newsletter",
                item.get("subject", "No subject"),
                full_text[:500],
                full_text,
                narrative_tag,
            ),
        )
        conn.commit()
        injected += 1
        log.info(
            f"  → Pipeline inject [{item.get('value_score')}/10] "
            f"{item.get('sender_name', '')} | {item.get('subject', '')[:50]} "
            f"[narrative: {narrative_tag}]"
        )

    conn.close()
    log.info(f"Story pipeline: injected {injected}/{len(eligible)} eligible items")
    return injected


# ── Auto-categorize non-narrative items ────────────────────────────────────────
# (Removed — unmatched newsletters are now discarded, not categorised.)



def send_telegram_digest(items: list[dict]) -> None:
    """Send a daily digest of high-value newsletters to the Telegram admin channel."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("_TCH") or os.environ.get("TELEGRAM_ADMIN_CHAT_ID")

    if not bot_token or not chat_id:
        log.warning("Telegram credentials not set — skipping digest")
        return

    high_value = [i for i in items if (i.get("value_score") or 0) >= 7]
    high_value.sort(key=lambda x: x.get("value_score", 0), reverse=True)

    if not high_value:
        log.info("No high-value newsletters (score ≥ 7) — skipping Telegram digest")
        return

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    all_count = len(items)
    pipeline_count = sum(1 for i in items if (i.get('value_score') or 0) >= STORY_INJECT_MIN_SCORE)

    lines = [
        f"📰 <b>Newsletter Digest — {today}</b>",
        f"<i>{all_count} narrative-matched newsletters · {len(high_value)} high-value · {pipeline_count} → stories</i>",
        "",
    ]

    for item in high_value[:10]:
        score = item.get("value_score", "?")
        sender = item.get("sender_name", item.get("sender", "Unknown"))
        subject = item.get("subject", "No subject")
        summary = item.get("summary", "")
        narratives = ", ".join(item.get("narrative_matches", []))
        pipeline_flag = " ⚡" if (score or 0) >= STORY_INJECT_MIN_SCORE else ""

        lines.append(f"🔹 <b>[{score}/10{pipeline_flag}] {sender}</b>")
        lines.append(f"   <i>{subject}</i>")
        if summary:
            lines.append(f"   {summary[:200]}")
        lines.append(f"   🏷 {narratives}")
        lines.append("")

    if len(high_value) > 10:
        lines.append(f"<i>...and {len(high_value) - 10} more. See data/newsletters.json</i>")
        lines.append("")

    message = "\n".join(lines)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)

    if resp.ok:
        log.info(f"Telegram digest sent ({len(high_value)} items)")
    else:
        log.error(f"Telegram send failed: {resp.text}")


# ── Main pipeline ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Fetch and analyze newsletter emails")
    parser.add_argument("--dry-run", action="store_true", help="Skip DeepSeek and writes")
    parser.add_argument("--days", type=int, default=1, help="Days to look back (default: 1)")
    parser.add_argument("--test-sample", action="store_true", help="Process first 3 emails only")
    parser.add_argument("--telegram", action="store_true", help="Send Telegram digest after run")
    args = parser.parse_args()

    start_time = time.time()
    log.info("=" * 60)
    log.info("Gazzetta di Kyiv — Newsletter Intelligence Harvester")
    log.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'} | Days: {args.days}")
    log.info("=" * 60)

    # Load config + narratives
    config = load_config()
    narrative_ids = get_narrative_ids(config)
    log.info(f"Loaded {len(narrative_ids)} narratives from config.yaml")

    # Authenticate Gmail
    service = get_gmail_service()

    # Fetch message IDs
    message_refs = fetch_recent_messages(service, days=args.days)
    log.info(f"Total messages to inspect: {len(message_refs)}")

    if args.test_sample:
        message_refs = message_refs[:3]
        log.info("TEST MODE: limited to 3 messages")

    # Load existing newsletters to avoid re-processing
    existing = load_existing_newsletters()
    log.info(f"Existing newsletters in cache: {len(existing)}")

    # Process messages
    results = []
    skipped_existing = 0
    skipped_not_newsletter = 0
    skipped_short = 0
    errors = 0

    for ref in message_refs:
        msg_id = ref["id"]

        # Skip already processed
        if msg_id in existing and not args.dry_run:
            skipped_existing += 1
            continue

        # Fetch full message
        msg = fetch_full_message(service, msg_id)
        if not msg:
            errors += 1
            continue

        headers = msg.get("payload", {}).get("headers", [])
        subject = decode_subject(get_header(headers, "Subject") or "(no subject)")
        sender = get_header(headers, "From") or "unknown"
        sender_name = re.sub(r"<[^>]+>", "", sender).strip().strip('"')
        received_ts = get_header(headers, "Date")

        # Parse received timestamp
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(received_ts).isoformat()
        except Exception:
            received_at = datetime.now(timezone.utc).isoformat()

        # Extract body
        body = extract_body(msg.get("payload", {}))

        if len(body) < MIN_BODY_LENGTH:
            skipped_short += 1
            log.debug(f"Skipping short email: '{subject}' ({len(body)} chars)")
            continue

        # Newsletter detection
        detected, confidence = is_newsletter(headers, body, subject)
        if not detected:
            skipped_not_newsletter += 1
            log.debug(f"Not a newsletter ({confidence:.2f}): '{subject}'")
            continue

        log.info(f"Processing [{confidence:.0%}] → {sender_name}: {subject[:60]}")

        # Extract intelligence via DeepSeek
        intelligence = extract_intelligence(
            subject=subject,
            sender_name=sender_name,
            body_text=body[:MAX_BODY_LENGTH],
            narratives=narrative_ids,
            dry_run=args.dry_run,
        )

        if intelligence is None:
            errors += 1
            continue

        # DISCARD if no narrative match — per editorial policy
        narrative_matches = intelligence.get("narrative_matches", [])
        if not narrative_matches:
            log.info(f"  → No narrative match — discarding: {subject[:60]}")
            skipped_not_newsletter += 1  # reuse counter for discard
            continue

        # Build final record
        record = {
            "id": msg_id,
            "received_at": received_at,
            "sender": sender,
            "sender_name": sender_name,
            "subject": subject,
            "newsletter_confidence": round(confidence, 2),
            "raw_word_count": len(body.split()),
            **intelligence,
        }

        results.append(record)

        if args.test_sample:
            print(json.dumps(record, indent=2, ensure_ascii=False))

        # Rate limiting: DeepSeek allows ~10 req/s
        if not args.dry_run:
            time.sleep(0.2)

    # Summary
    elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info(f"Run complete in {elapsed:.1f}s")
    log.info(f"  Newsletters extracted : {len(results)}")
    log.info(f"  Skipped (existing)    : {skipped_existing}")
    log.info(f"  Skipped (not newsletter): {skipped_not_newsletter}")
    log.info(f"  Skipped (too short)   : {skipped_short}")
    log.info(f"  Errors                : {errors}")
    log.info("=" * 60)

    if results and not args.dry_run:
        # Merge with existing and save
        all_items = list(existing.values()) + results
        save_newsletters(all_items)
        save_to_db(results)

        # Inject high-value items into the stories pipeline
        injected = inject_into_story_pipeline(results, dry_run=False)
        log.info(f"Story pipeline injections: {injected}")

        # Always send Telegram digest (--telegram flag or production env)
        if args.telegram or os.environ.get("GAZZETTA_ENV") == "production":
            send_telegram_digest(results)

    elif args.dry_run:
        inject_into_story_pipeline(results, dry_run=True)
        log.info(f"DRY RUN — would have processed {len(results)} newsletters")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
