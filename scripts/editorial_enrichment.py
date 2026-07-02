#!/usr/bin/env python3
"""
editorial_enrichment.py -- Automated Sovereign Auditor Editorial Enrichment.

Loads public/data/stories.json, filters for stories without editorial reviews,
queries DeepSeek to generate brief_review, contradiction_note, and implication_note,
and writes them back atomically.

Usage:
  python3 scripts/editorial_enrichment.py [--max-items 10] [--enrich-all] [--dry-run]
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

PROJECT = Path(__file__).resolve().parent.parent
PUBLIC_DATA = PROJECT / "public" / "data"
STORIES_PATH = PUBLIC_DATA / "stories.json"
TMP_PATH = PUBLIC_DATA / "stories.tmp.json"
DATA_DIR = PROJECT / "data"

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
        return os.environ.get("DEEPSEEK_API_KEY", "")

GLM_KEY_1 = os.environ.get("GLM_API_KEY_1", "3d76e17112094679a3236820eb5a3502.zX9w5hVuUqKu3pbL")
GLM_KEY_2 = os.environ.get("GLM_API_KEY_2", "0feba8763e0a4c808bbba55f5a02cd7e.7N3kvN7asehKbCZ3")
DEEPSEEK_KEY = _secret("gazzetta-deepseek-key")

PROVIDERS = [
    {
        "name": "deepseek",
        "url": "https://api.deepseek.com/chat/completions",
        "key": DEEPSEEK_KEY,
        "model": "deepseek-chat",
        "json_mode": True
    },
    {
        "name": "glm5.2_primary",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key": GLM_KEY_1,
        "model": "glm-5.2",
        "json_mode": True
    },
    {
        "name": "glm5.2_secondary",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key": GLM_KEY_2,
        "model": "glm-5.2",
        "json_mode": True
    }
]

SYSTEM_PROMPT = """You are the Sovereign Auditor, the omnipotent CEO of La Gazzetta di Kyiv. Your mission is to identify the friction between global narratives and physical reality. You write sharp, cynical, degen-betting-oriented commentary on macro developments. Your tone is clinical, detached, and highly quantitative. 

For the given story, generate the editorial annotations:
1. brief_review: 1-2 sentences of first-person cynical macroeconomic/betting analysis in Solianin's voice. Must reference specific capital flows, edge, or market pricing. Avoid generic statements.
2. contradiction_note: 1-2 sentences detailing the exact friction/gap between official media consensus and the underlying market tape.
3. implication_note: 1 sentence explaining the tactical trade implication (why this trade makes sense or what risk-reward profile is implied).

You MUST respond with a single, valid JSON object. No markdown code blocks, no trailing comments, no wrapper text.
Output schema:
{
  "brief_review": "string",
  "contradiction_note": "string",
  "implication_note": "string"
}"""

def ask_llm(prompt):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    for provider in PROVIDERS:
        key = provider["key"]
        if not key:
            continue
            
        payload = {
            "model": provider["model"],
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        if provider["json_mode"]:
            payload["response_format"] = {"type": "json_object"}
            
        body = json.dumps(payload).encode()
        
        req = urllib.request.Request(
            provider["url"],
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            }
        )
        
        for attempt in range(2):
            try:
                resp = urllib.request.urlopen(req, timeout=45)
                data = json.loads(resp.read().decode())
                content = data["choices"][0]["message"]["content"].strip()
                if content:
                    print(f"  ✓ Success with provider: {provider['name']}")
                    return content
            except urllib.error.HTTPError as e:
                err_body = ""
                try: err_body = e.read().decode()
                except: pass
                print(f"    {provider['name']} HTTP Error {e.code}: {err_body[:200]}")
                if e.code == 429:
                    time.sleep(2 ** attempt)
                else:
                    break
            except Exception as e:
                print(f"    {provider['name']} error: {e}")
                time.sleep(1)
                
    return None

def rebuild_stories_structure(existing, all_stories):
    # Sort: newest first
    all_stories.sort(key=lambda s: s.get("generated_at", ""), reverse=True)
    
    containers = {
        k: {"title": v.get("title", ""), "subtitle": v.get("subtitle", ""),
            "count": 0, "stories": []}
        for k, v in existing.get("containers", {}).items()
    }
    
    for s in all_stories:
        story_containers = s.get("containers") or [s.get("container", "tech_convergence_platforms_ai_autonomy")]
        for c in story_containers:
            if c in containers:
                containers[c]["stories"].append(s)
                containers[c]["count"] += 1
                
    tags_index = {}
    for s in all_stories:
        sid = str(s.get("story_id", ""))
        for tag in s.get("tags", []):
            if tag not in tags_index:
                tags_index[tag] = []
            if sid and sid not in tags_index[tag]:
                tags_index[tag].append(sid)
                
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": existing.get("generated_by", "contradiction_synthesizer.py v1.0"),
        "containers": containers,
        "all_stories": all_stories,
        "tags_index": tags_index,
        "total_stories": len(all_stories)
    }

def main():
    parser = argparse.ArgumentParser(description="Gazzetta Sovereign Auditor Editorial Enrichment")
    parser.add_argument("--max-items", type=int, default=10, help="Max stories to enrich in this run")
    parser.add_argument("--enrich-all", action="store_true", help="Force enrich all stories, overwriting existing")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print but do not save")
    args = parser.parse_args()
    
    if not STORIES_PATH.exists():
        print(f"Stories file not found at {STORIES_PATH}")
        sys.exit(1)
        
    with open(STORIES_PATH) as f:
        data = json.load(f)
        
    all_stories = data.get("all_stories", [])
    if not all_stories:
        print("No stories in stories.json.")
        sys.exit(0)
        
    # Find candidates
    candidates = []
    for s in all_stories:
        has_review = bool(s.get("brief_review"))
        if not has_review or args.enrich_all:
            candidates.append(s)
            
    print(f"Found {len(candidates)} candidates for enrichment (total: {len(all_stories)} stories).")
    
    to_process = candidates[:args.max_items]
    if not to_process:
        print("No stories need enrichment.")
        sys.exit(0)
        
    print(f"Processing {len(to_process)} stories...")
    
    enriched_count = 0
    for idx, story in enumerate(to_process):
        print(f"[{idx+1}/{len(to_process)}] Enriching: {story.get('headline')[:60]}...")
        
        # Build prompt
        prompt = f"""Headline: {story.get('headline')}
They Say: {story.get('they_say')}
Reality: {story.get('reality')}
Trade Thesis: {json.dumps(story.get('trade_thesis', {}))}
Contradiction Gap: {story.get('contradiction_gap')}
Capital Volume: {story.get('capital_volume_usd')}
Affected Tickers: {story.get('affected_tickers')}
"""
        
        response_text = ask_llm(prompt)
        if not response_text:
            print("  Failed to get response from LLM providers. Skipping.")
            continue
            
        try:
            # Parse response
            enriched = json.loads(response_text)
            brief_review = enriched.get("brief_review", "").strip()
            contradiction_note = enriched.get("contradiction_note", "").strip()
            implication_note = enriched.get("implication_note", "").strip()
            
            if not brief_review or not contradiction_note:
                print("  Response JSON missing required fields. Skipping.")
                continue
                
            story["brief_review"] = brief_review
            story["contradiction_note"] = contradiction_note
            story["implication_note"] = implication_note
            story["conclusion"] = implication_note  # Bind to conclusion for legacy support
            
            print(f"  ✓ Enriched successfully.")
            print(f"    Auditor: {brief_review[:100]}...")
            enriched_count += 1
            
            # Simple rate limit safety
            time.sleep(1)
        except Exception as e:
            print(f"  Error parsing response JSON: {e}")
            print(f"  Raw response: {response_text}")
            
    if enriched_count == 0:
        print("No stories were enriched.")
        sys.exit(0)
        
    if args.dry_run:
        print("DRY RUN: changes not saved.")
        sys.exit(0)
        
    # Rebuild and write
    new_data = rebuild_stories_structure(data, all_stories)
    
    with open(TMP_PATH, "w") as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)
        
    os.replace(TMP_PATH, STORIES_PATH)
    
    # Mirror to data/
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    mirror = DATA_DIR / "stories.json"
    mirror.write_text(STORIES_PATH.read_text())
    
    # Update SQLite database if exists
    db_path = Path(os.environ.get("GAZZETTA_DB_PATH", str(PROJECT / "data" / "gazzetta.db")))
    if db_path.exists():
        print(f"Updating SQLite database at {db_path}...")
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            
            updated_db_count = 0
            for story in all_stories:
                if not story.get("brief_review"):
                    continue
                
                sid = str(story.get("story_id") or story.get("id") or "")
                if not sid:
                    continue
                
                row = conn.execute("SELECT full_json FROM stories WHERE id = ?", (sid,)).fetchone()
                if row and row[0]:
                    try:
                        db_story = json.loads(row[0])
                    except Exception:
                        db_story = {}
                else:
                    db_story = {}
                
                # Merge enriched fields
                db_story["brief_review"] = story["brief_review"]
                db_story["contradiction_note"] = story["contradiction_note"]
                db_story["implication_note"] = story["implication_note"]
                db_story["conclusion"] = story["conclusion"]
                
                new_full_json = json.dumps(db_story, ensure_ascii=False)
                conn.execute("UPDATE stories SET full_json = ? WHERE id = ?", (new_full_json, sid))
                updated_db_count += 1
                
            conn.commit()
            conn.close()
            print(f"Successfully updated {updated_db_count} stories in SQLite database.")
        except Exception as e:
            print(f"Error updating SQLite database: {e}")
            
    print(f"Successfully saved {enriched_count} enriched stories to stories.json")

if __name__ == "__main__":
    main()
