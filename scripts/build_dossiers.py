#!/usr/bin/env python3
"""
build_dossiers.py — Generate dossier HTML pages from data/dossiers/*.md + live pipeline data.

Reads markdown dossiers, injects live GAP scores, capital flow data, and story lists
from stories.json, flows.json, and narratives.json. Writes static HTML to public/dossier/.

Called from build_frontend.py during the main build step.
"""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
PUBLIC = PROJECT / "public"
DOSSIERS_DIR = DATA / "dossiers"


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def build_dossiers(stories, flows, narrative_config):
    if not DOSSIERS_DIR.exists():
        print("[build_dossiers] No dossiers directory, skipping.")
        return

    public_dossier = PUBLIC / "dossier"
    public_dossier.mkdir(parents=True, exist_ok=True)

    md_files = sorted(DOSSIERS_DIR.glob("*.md"))
    print(f"[build_dossiers] Found {len(md_files)} dossier markdown files")

    for mdf in md_files:
        slug = mdf.stem
        md_text = mdf.read_text()

        # Extract title from first H1
        title_match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
        title = title_match.group(1) if title_match else slug.replace("-", " ").title()

        # Extract narrative ID from metadata
        nid_match = re.search(r'\*\*Narrative ID\*\*: `(\w+)`', md_text)
        narrative_id = nid_match.group(1) if nid_match else None

        # Narrative config
        ncfg = narrative_config.get(narrative_id, {}) if narrative_id else {}
        display_name = ncfg.get("display_name", title)
        tag = ncfg.get("tag", display_name)
        tickers = ncfg.get("tickers", [])

        # Stories for this narrative
        nstories = [s for s in stories if s.get("narrative_id") == narrative_id] if narrative_id else []
        n_gaps = [s.get("contradiction_gap", 0) or 0 for s in nstories]
        avg_gap = sum(n_gaps) / len(n_gaps) if n_gaps else 0
        gap_color = "#8B0000" if avg_gap >= 70 else ("#D4AF37" if avg_gap >= 50 else "#747878")
        highest_gap = max(n_gaps) if n_gaps else 0

        # Capital flow
        flow_data = {}
        if isinstance(flows, dict):
            flows_dict = flows.get("narrative_flows", {})
            if narrative_id in flows_dict:
                flow_data = flows_dict[narrative_id]
            else:
                # Fallback to older narratives list or direct keys
                flows_list = flows.get("narratives", [])
                if isinstance(flows_list, list):
                    for fn in flows_list:
                        if fn.get("narrative_id") == narrative_id or fn.get("narrative") == narrative_id:
                            flow_data = fn
                            break
                elif narrative_id in flows:
                    flow_data = flows[narrative_id]
        elif isinstance(flows, list):
            for fn in flows:
                if fn.get("narrative_id") == narrative_id or fn.get("narrative") == narrative_id:
                    flow_data = fn
                    break

        total_cap = flow_data.get("total_capital_b", 0) or flow_data.get("total_b", 0) or 0
        cap_direction = (flow_data.get("dominant_direction") or flow_data.get("direction") or "neutral").lower()
        cap_color = "#10B981" if cap_direction == "inflow" else ("#8B0000" if cap_direction == "outflow" else "#747878")

        # Recent stories (top 10)
        recent_stories = sorted(nstories, key=lambda s: s.get("contradiction_gap", 0) or 0, reverse=True)[:10]

        # Remove the metadata block from markdown for HTML rendering
        body_md = re.sub(r'\*\*Narrative ID\*\*:.*?\n\n', '', md_text, count=1, flags=re.DOTALL)
        body_md = re.sub(r'\*\*Tickers\*\*:.*?\n', '', body_md)
        body_md = re.sub(r'\*\*Invalidation.*?\n', '', body_md)

        # Build ticker pills HTML
        ticker_html = " ".join(f'<span class="ticker-pill">{t}</span>' for t in tickers) if tickers else "N/A"

        # Build story links
        story_links = ""
        for st in recent_stories:
            s_gap = st.get("contradiction_gap", 0) or 0
            s_headline = st.get("headline", "Untitled")
            s_id = st.get("story_id", "")
            s_gap_color = "#8B0000" if s_gap >= 70 else ("#D4AF37" if s_gap >= 50 else "#747878")
            story_links += f"""<a href="/?story={s_id}" class="story-link">
  <span class="gap" style="color:{s_gap_color}">GAP {s_gap:.0f}</span> — {s_headline}
</a>
"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{display_name} — La Gazzetta di Kyiv</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #FAF9F6; color: #4A0E4E; font-family: Inter, -apple-system, sans-serif; max-width: 880px; margin: 0 auto; padding: 24px; line-height: 1.7; }}
  h1 {{ font-family: 'Playfair Display', serif; font-size: 36px; margin-bottom: 4px; font-weight: 700; color: #4A0E4E; }}
  h2 {{ font-family: 'Playfair Display', serif; font-size: 22px; margin: 32px 0 8px; color: #4A0E4E; font-weight: 600; border-bottom: 2px solid #D4AF37; padding-bottom: 4px; }}
  h3 {{ font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #D4AF37; margin: 28px 0 8px; }}
  p {{ margin-bottom: 12px; font-size: 16px; color: #1A1C1A; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; }}
  .data-row {{ display: flex; gap: 24px; margin: 20px 0; flex-wrap: wrap; }}
  .data-card {{ background: white; border: 1px solid #D4AF37; padding: 16px 20px; border-radius: 6px; min-width: 160px; flex: 1; }}
  .data-card .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #4A0E4E; margin-bottom: 4px; }}
  .data-card .value {{ font-family: 'JetBrains Mono', monospace; font-size: 28px; font-weight: 700; }}
  .ticker-pill {{ display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 13px; background: #F4EEF4; border: 1px solid #D4AF37; color: #4A0E4E; padding: 3px 10px; border-radius: 4px; margin: 3px; }}
  .story-link {{ display: block; padding: 10px 0; border-bottom: 1px solid #F4EEF4; text-decoration: none; color: #1A1C1A; font-size: 14px; }}
  .story-link:hover {{ background: #F4EEF4; }}
  .gap {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; }}
  .back-link {{ color: #4A0E4E; text-decoration: none; font-size: 14px; font-weight: 600; }}
  .pro-cta {{ background: #F4EEF4; border: 1px dashed #D4AF37; padding: 20px; text-align: center; margin: 32px 0; border-radius: 6px; color: #4A0E4E; }}
  .pro-cta a {{ color: #4A0E4E; font-weight: 700; text-decoration: underline; }}
  .tagline {{ color: #D4AF37; font-size: 14px; margin-top: 0; font-weight: 500; }}
  hr {{ border: none; border-top: 1px solid #D4AF37; margin: 32px 0; }}
  strong {{ color: #4A0E4E; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
  th {{ text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #747878; padding: 8px 4px; border-bottom: 2px solid #E5E5E5; }}
  td {{ padding: 8px 4px; border-bottom: 1px solid #E5E5E5; font-family: 'JetBrains Mono', monospace; font-size: 13px; }}
  td:first-child {{ font-family: Inter, sans-serif; font-size: 14px; }}
  @media (max-width: 640px) {{
    body {{ padding: 16px; }}
    h1 {{ font-size: 28px; }}
    .data-card {{ min-width: 100%; }}
  }}
</style>
</head>
<body>
<a href="/" class="back-link">← Back to The Stream</a>
<h1>{display_name}</h1>
<p class="tagline">Macro Dossier • Institutional Narrative Intelligence</p>

<div class="data-row">
  <div class="data-card">
    <div class="label">Avg GAP Score</div>
    <div class="value" style="color:{gap_color}">{avg_gap:.0f}</div>
  </div>
  <div class="data-card">
    <div class="label">Highest GAP</div>
    <div class="value" style="color:{'#8B0000' if highest_gap >= 70 else ('#D4AF37' if highest_gap >= 50 else '#747878')}">{highest_gap:.0f}</div>
  </div>
  <div class="data-card">
    <div class="label">Capital Flow</div>
    <div class="value" style="color:{cap_color}">{total_cap:.1f}B</div>
  </div>
  <div class="data-card">
    <div class="label">Active Stories</div>
    <div class="value">{len(nstories)}</div>
  </div>
</div>

<div style="margin: 16px 0;">
  <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #747878;">Key Tickers</span><br>
  {ticker_html}
</div>

<hr>
{body_md}
<hr>

<h3>Recent Signals</h3>
{story_links if story_links else '<p style="color:#747878">No active stories for this narrative.</p>'}

<div class="pro-cta">
  <strong>Pro subscribers</strong> get live FRED/CFTC data embeds, capital flow charts, and real-time Contradiction Alerts for this narrative.<br>
  <a href="/upgrade">Upgrade to Pro — $199/mo</a>
</div>

<p style="text-align: center; color: #747878; font-size: 12px; margin-top: 48px;">
  La Gazzetta di Kyiv — Institutional Narrative Intelligence<br>
  <a href="/" style="color: #747878;">lagazzettadikyiv.com</a> • <a href="/method" style="color: #747878;">Method</a>
</p>
</body>
</html>"""

        out_path = public_dossier / f"{slug}.html"
        out_path.write_text(html)
        print(f"  Wrote dossier: {out_path} ({len(nstories)} stories, avg GAP {avg_gap:.0f})")


if __name__ == "__main__":
    # Standalone mode: load data directly
    stories_raw = load_json(DATA / "stories.json")
    all_stories = stories_raw.get("all_stories", [])
    if not all_stories:
        containers = stories_raw.get("containers", {})
        for cid, cdata in containers.items():
            for s in cdata.get("stories", []):
                s["_container_id"] = cid
                all_stories.append(s)

    flows_raw = load_json(DATA / "flows.json")
    narratives_raw = load_json(DATA / "narratives.json")
    narrative_config = narratives_raw.get("narratives", {})

    # Build the narrative_id lookup for stories
    for s in all_stories:
        nid = s.get("narrative_id", "")
        if nid and nid in narrative_config:
            s["_container_id"] = nid
            s["_container_title"] = narrative_config[nid].get("display_name", nid)

    build_dossiers(all_stories, flows_raw, narrative_config)
    print("[build_dossiers] Done.")
