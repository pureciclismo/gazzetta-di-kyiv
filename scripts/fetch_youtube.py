#!/usr/bin/env python3
"""
fetch_youtube.py — YouTube channel monitor for the Gazzetta Sovereign Vault.

Pulls latest video metadata (title, description, publish time) from 13 macro/
institutional channels. Uses YouTube Data API v3. Stores to data/vault/youtube/YYYY-MM/.

Channels monitored:
  Jordi Visser Labs, Raoul Pal (The Journey Man), a16z, WEF, Bloomberg Markets,
  Bloomberg Business, All-In Podcast, Real Vision Finance, Peter Diamandis,
  ARK Invest, Zeihan on Geopolitics, Capital Flows Research, Forward Guidance

Usage:
  python3 scripts/fetch_youtube.py
  python3 scripts/fetch_youtube.py --max-results 3   # per channel
  python3 scripts/fetch_youtube.py --hours 48          # fetch last 48h only
"""

import json, os, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
VAULT = PROJECT / "data" / "vault" / "youtube"
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
API_URL = "https://www.googleapis.com/youtube/v3"

# ── Channel registry: @handle → display name ──────────────────────
CHANNELS = {
    "@JordiVisserLabs":        "Jordi Visser Labs",
    "@RaoulPalTJM":            "Raoul Pal / The Journey Man",
    "@a16z":                   "a16z",
    "@wef":                    "World Economic Forum",
    "@markets":                "Bloomberg Markets",
    "@business":               "Bloomberg Business",
    "@allin":                  "All-In Podcast",
    "@RealVisionFinance":      "Real Vision Finance",
    "@peterdiamandis":         "Peter Diamandis",
    "@ARKInvest2015":          "ARK Invest",
    "@ZeihanonGeopolitics":    "Zeihan on Geopolitics",
    "@CapitalFlowsResearch":   "Capital Flows Research",
    "@ForwardGuidanceBW":      "Forward Guidance",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_call(endpoint: str, params: dict) -> dict:
    """Call YouTube Data API v3 with exponential backoff on quota errors."""
    params["key"] = YOUTUBE_API_KEY
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{API_URL}/{endpoint}?{qs}"

    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            if e.code == 403 and "quota" in body.lower():
                print(f"  [youtube] Quota exceeded, waiting {2**attempt * 10}s...")
                time.sleep(2 ** attempt * 10)
                continue
            print(f"  [youtube] HTTP {e.code}: {body[:200]}")
            return {}
        except Exception as e:
            print(f"  [youtube] API error: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt * 5)
            else:
                return {}
    return {}


def resolve_channel_id(handle):
    """Resolve a @handle to a YouTube channel ID."""
    if handle.startswith("UC"): return handle
    data = api_call("channels", {"part": "id", "forHandle": handle})
    items = data.get("items", [])
    if items:
        return items[0]["id"]
    # Fallback: search
    data2 = api_call("search", {"part": "snippet", "q": handle.strip("@"), "type": "channel", "maxResults": 1})
    items2 = data2.get("items", [])
    if items2:
        return items2[0]["snippet"]["channelId"]
    return None


def fetch_latest_videos(channel_id: str, max_results: int = 5) -> list:
    """Fetch most recent videos for a channel via playlistItems."""
    # Get uploads playlist ID
    ch_data = api_call("channels", {"part": "contentDetails", "id": channel_id})
    ch_items = ch_data.get("items", [])
    if not ch_items:
        return []
    uploads_id = ch_items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
    if not uploads_id:
        return []

    # Get latest videos
    pl_data = api_call("playlistItems", {
        "part": "snippet,contentDetails",
        "playlistId": uploads_id,
        "maxResults": max_results,
    })
    items = pl_data.get("items", [])
    videos = []
    for item in items:
        snippet = item.get("snippet", {})
        videos.append({
            "video_id": snippet.get("resourceId", {}).get("videoId", ""),
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "published_at": snippet.get("publishedAt", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "url": f"https://youtube.com/watch?v={snippet.get('resourceId', {}).get('videoId', '')}",
        })
    return videos


def fetch_all(max_per_channel: int = 5, hours_back: int = 72) -> dict:
    """Fetch latest videos from all registered channels."""
    if not YOUTUBE_API_KEY:
        print("[youtube] ERROR: YOUTUBE_API_KEY not set. Get a key at https://console.cloud.google.com/apis/credentials")
        return {"error": "YOUTUBE_API_KEY not set", "videos": [], "fetched_at": now_iso()}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    all_videos = []
    channel_errors = []

    for handle, display_name in CHANNELS.items():
        print(f"  [youtube] {display_name} ({handle})...", end=" ", flush=True)
        channel_id = resolve_channel_id(handle)
        if not channel_id:
            print("CHANNEL NOT FOUND")
            channel_errors.append(handle)
            continue

        videos = fetch_latest_videos(channel_id, max_per_channel)
        # Filter by recency
        recent = []
        for v in videos:
            try:
                pub = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
                if pub >= cutoff:
                    recent.append(v)
            except (ValueError, TypeError):
                recent.append(v)  # Keep if unparseable

        print(f"{len(recent)} recent videos")
        all_videos.extend(recent)
        time.sleep(0.5)  # Polite rate limiting

    result = {
        "fetched_at": now_iso(),
        "hours_back": hours_back,
        "total_videos": len(all_videos),
        "channels_with_errors": channel_errors,
        "channels_monitored": len(CHANNELS),
        "videos": sorted(all_videos, key=lambda v: v.get("published_at", ""), reverse=True),
    }
    return result


def save_vault(data: dict):
    """Save raw fetch to data/vault/youtube/YYYY-MM/latest.json."""
    now = datetime.now(timezone.utc)
    month_dir = VAULT / now.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    # Save as latest.json
    latest_path = month_dir / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [youtube] Wrote {data['total_videos']} videos to {latest_path}")

    # Also write a flat summary for the ingestion pipeline
    summary_path = PROJECT / "data" / "youtube_intel" / "latest.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "fetched_at": data["fetched_at"],
        "videos": [
            {
                "title": v["title"],
                "description": v["description"],
                "url": v["url"],
                "channel": v["channel_title"],
                "published_at": v["published_at"],
            }
            for v in data["videos"]
        ],
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="YouTube macro channel monitor")
    ap.add_argument("--max-results", type=int, default=5, help="Max videos per channel")
    ap.add_argument("--hours", type=int, default=72, help="Hours back to fetch")
    args = ap.parse_args()

    print(f"[youtube] Fetching {len(CHANNELS)} channels, max {args.max_results} videos each, last {args.hours}h...")
    data = fetch_all(max_per_channel=args.max_results, hours_back=args.hours)
    save_vault(data)
    print(f"[youtube] Done: {data['total_videos']} videos from {len(CHANNELS) - len(data.get('channels_with_errors', []))} channels")
