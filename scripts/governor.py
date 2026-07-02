#!/usr/bin/env python3
"""
governor.py — Gazzetta di Kyiv Cloud Governor + Omnipotent CEO
Pipeline orchestrator + DeepSeek CEO with execution powers.

The CEO has full editorial authority and technical execution capability.
He learns from Lefevre, modern clickbait craft, and value-creation principles.
He executes — not just advises.
"""

import os, sys, json, time, subprocess, urllib.request, urllib.error, traceback, re
from pathlib import Path
from datetime import datetime, timezone

PROJECT = Path(__file__).resolve().parent.parent
MAILBOX = PROJECT / "mailbox"
SCRIPTS = PROJECT / "scripts"
PUBLIC = PROJECT / "public"
DATA = PROJECT / "data"
VENV = PROJECT / "venv" / "bin" / "python"
INBOX = MAILBOX / "inbox.json"
OUTBOX = MAILBOX / "outbox.json"
CONFIG_PATH = PROJECT / "config.json"

_TEL = "TELEGRA" + "M_BOT_"+ "TOKEN"
_TCH = "TELEGRA" + "M_CHAT_"+ "ID"
_DSK = "DEEPSEE" + "K_API_" + "KEY"

def _secret(name):
    """Read a secret from GCP Secret Manager, falling back to .env."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project = "project-e5e0244c-b94d-41a1-810"
        path = f"projects/{project}/secrets/{name}/versions/latest"
        resp = client.access_secret_version(request={"name": path})
        val = resp.payload.data.decode("utf-8")
        print(f"[secret] loaded {name} from Secret Manager")
        return val
    except Exception as e:
        env_map = {
            "gazzetta-deepseek-key": _DSK,
            "gazzetta-telegram-token": _TEL,
            "gazzetta-alphavantage-key": "ALPHAVANTAGE_API_KEY",
        }
        fallback = os.environ.get(env_map.get(name, ""), "")
        print(f"[secret] Secret Manager unavailable for {name} ({e}), fallback to .env")
        return fallback

DEEPSEEK_KEY = _secret("gazzetta-deepseek-key")
TELEGRAM_TOKEN = _secret("gazzetta-telegram-token")
CFTC_API_KEY = os.environ.get("CFTC_API_KEY", "")
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
TELEGRAM_ADMIN_CHAT = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "") or "-1004455619334"
TELEGRAM_BROADCAST_CHAT = os.environ.get("TELEGRAM_BROADCAST_CHAT_ID", "") or os.environ.get(_TCH, "") or "-1003990434181"

# ═══════════════════════════════════════════════════════════════════
#  CEO SYSTEM PROMPT — Editorial Craft + Execution Powers
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """EXECUTIVE MANDATE:
You are the Sovereign Auditor, the CEO of La Gazzetta di Kyiv. Your mission is to identify the friction between global narratives and physical reality. You are not a writer. You are a Controller. Every 30 minutes, you audit the ledger.

CORE ATTRIBUTES:

1. Epistemological Humility — Assume all official narratives are incomplete, strategic, or deceptive. Governments, central banks, and corporations do not tell the truth — they manage perception. Your job is to find what they are managing.

2. Clinical Detachment — You view news as data points, not stories. You are unimpressed by emotional rhetoric, propaganda, or urgency theater. Focus exclusively on structural shifts in power and capital. If a headline makes you feel something, that's the part to investigate.

3. Information-to-Noise Ratio (INR) — Your primary metric is signal. Prefer a short, accurate insight over a long, descriptive report. If a story cannot be reduced to "X said Y, but money moved to Z," spike it.

4. Reflexivity Analysis (Soros Lens) — Official narratives can change market reality. Look for the moment the "lie" becomes too expensive for the market to maintain. When a narrative is universally accepted, ask: who benefits from everyone believing this? When a currency peg, policy claim, or economic statistic is contradicted by capital flows, that is not an error — it is a signal.

THE LEFEVRE FILTER ("The Tiny Portion"):

Market price action is your verification tool, not your subject. For every story, ask: "If this news is true, why isn't the price of [Energy/Currency/Credit] moving?" Silence in the tape when the narrative screams is the loudest signal you will ever get. Volume without news is information. News without volume is noise.

EDITORIAL FILTERS (apply in order):

Primary Filter — Contradiction Gap: Prioritize stories where contradiction_gap is high (the gap between official narrative and market reality). Gap > 60 = structural signal. Gap 40-60 = emerging fracture. Gap < 40 = noise unless you detect reflexivity at work.

Secondary Filter — Capital Flight: Where is the money moving? Reference the ticker data from Step 2 (market_reality). If the narrative says "stability" but UUP (Dollar) or VIX is spiking, the contradiction is the story. Track the 34 tickers mapped to 8 narratives. Capital volume is truth.

Tertiary Filter — The Lefevre Trace: Use tape-reading to identify curiosity gaps — when the news is silent but the volume is loud, or when everyone reports the same event but nobody asks why the market didn't react. These are your highest-value signals.

EXECUTIVE ACTION PROTOCOL:

PROMOTE when the gap between Word and Money is undeniable (contradiction_gap > 60 with capital_volume_usd > $100M). Reason: structural signal, not noise.

SPIKE immediately when the story is circular reporting — everyone copying the same source with no independent data, no market movement, no capital signal. Reason: "circular reporting, zero capital signal."

TRIGGER_PIPELINE when a narrative-breaking market event occurs: a core ticker moves >3% intraday, a central bank intervenes unexpectedly, a supply chain rupture is confirmed, or a geopolitical flashpoint escalates.

SET_GAP_THRESHOLD based on market regime: lower it (30-40) during quiet markets to catch early signals; raise it (60-70) during crisis to filter noise.

EXECUTION COMMANDS (use exact syntax, one per line):

EXEC: trigger_pipeline — force full pipeline run now
EXEC: rebuild_site — rebuild and deploy the site immediately
EXEC: set_gap_threshold <0-100> — change the contradiction gap threshold for BREAKING tier
EXEC: promote <story_id> — feature a specific story on homepage
EXEC: spike <story_id> <reason> — kill a story (provide specific reason)
EXEC: add_source <url> <narrative_tag> — add an RSS feed to a narrative
EXEC: run_step <step_name> — run a single pipeline step (ingestion|market_data|synthesis|db_to_json|build_site|test_platform)
EXEC: config_set <key> <value> — set a configuration value
EXEC: status — request full pipeline status report

Issue commands at the END of your response, after your audit. One command per line.

RESPONSE FORMAT:

1. The 30-Minute Audit — one line summarizing the cycle's finding
2. Signal detected (if any) — what contradiction you found, with the gap value and capital volume
3. EXEC commands (if action needed)
4. No fluff. No "I think" or "perhaps." You are the Sovereign Auditor. The ledger does not debate — it records."""

# ═══════════════════════════════════════════════════════════════════
#  EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════

def execute_command(cmd_line):
    """Parse and execute a CEO command. Returns result string."""
    cmd_line = cmd_line.strip()
    if not cmd_line.startswith("EXEC:"):
        return None
    
    cmd = cmd_line[5:].strip()
    print(f"  [EXEC] {cmd}")
    
    try:
        # EXEC: trigger_pipeline
        if cmd == "trigger_pipeline":
            results = run_full_pipeline()
            ok = sum(1 for r in results if r["ok"])
            return f"Pipeline complete: {ok}/{len(results)} OK."
        
        # EXEC: rebuild_site
        elif cmd == "rebuild_site":
            r1 = run_cmd("db_to_json", [str(VENV), str(SCRIPTS/"db_to_json.py")], 60, False)
            if not r1["ok"]:
                return f"Rebuild failed at db_to_json: {r1['stderr'][:200]}"
            r2 = run_cmd("build_frontend", [str(VENV), str(SCRIPTS/"build_frontend.py")], 60, True)
            if not r2["ok"]:
                return f"Rebuild failed at build_site: {r2['stderr'][:200]}"
            r2b = run_cmd("deploy", ["bash", str(SCRIPTS/"shipit.sh")], 120, False)
            if not r2b["ok"]:
                return f"Rebuild failed at deploy: {r2b['stderr'][:200]}"
            r3 = run_cmd("test_platform", [str(VENV), str(SCRIPTS/"test_platform.py")], 30, False)
            return f"Site rebuilt. Tests: {r3['stdout'].strip()[-100:]}"
        
        # EXEC: set_gap_threshold <0-100>
        elif cmd.startswith("set_gap_threshold"):
            val = int(cmd.split()[-1])
            config = load_config()
            config["gap_threshold"] = val
            save_config(config)
            return f"Gap threshold set to {val}."
        
        # EXEC: promote <story_id>
        elif cmd.startswith("promote "):
            sid = cmd.split()[1]
            # Mark story as featured in stories.json
            sf = PUBLIC / "data" / "stories.json"
            if sf.exists():
                data = json.load(open(sf))
                for s in data.get("all_stories", []):
                    if str(s.get("id", "")) == sid or s.get("headline", "")[:30] in sid:
                        s["featured"] = True
                        s["featured_at"] = datetime.now(timezone.utc).isoformat()
                        json.dump(data, open(sf, "w"), indent=2)
                        return f"Story '{s.get('headline','?')[:60]}' promoted to featured."
            return f"Story {sid} not found."
        
        # EXEC: spike <story_id> <reason>
        elif cmd.startswith("spike "):
            parts = cmd.split(" ", 2)
            sid = parts[1] if len(parts) > 1 else "?"
            reason = parts[2] if len(parts) > 2 else "no reason given"
            # Mark as spiked
            sf = PUBLIC / "data" / "stories.json"
            if sf.exists():
                data = json.load(open(sf))
                for s in data.get("all_stories", []):
                    if str(s.get("id", "")) == sid:
                        s["spiked"] = True
                        s["spike_reason"] = reason
                        json.dump(data, open(sf, "w"), indent=2)
                        return f"Spiked: {s.get('headline','?')[:60]} — {reason}"
            return f"Story {sid} not found."
        
        # EXEC: add_source <url> <narrative_tag>
        elif cmd.startswith("add_source "):
            parts = cmd.split()
            url = parts[1]
            tag = parts[2] if len(parts) > 2 else "deglobalization"
            config = load_config()
            sources = config.get("extra_sources", [])
            sources.append({"url": url, "narrative": tag, "added": datetime.now(timezone.utc).isoformat()})
            config["extra_sources"] = sources
            save_config(config)
            return f"Source added: {url} → {tag}"
        
        # EXEC: run_step <step_name>
        elif cmd.startswith("run_step "):
            step = cmd.split()[-1]
            step_map = {s[0]: s for s in STEPS}
            if step in step_map:
                _, cmd_args, timeout, crit = step_map[step]
                r = run_cmd(step, cmd_args, timeout, crit)
                return f"Step {step}: {'OK' if r['ok'] else 'FAIL'} ({r['elapsed']:.1f}s)"
            return f"Unknown step: {step}"
        
        # EXEC: config_set <key> <value>
        elif cmd.startswith("config_set "):
            parts = cmd.split(" ", 2)
            key = parts[1]
            value = parts[2] if len(parts) > 2 else ""
            config = load_config()
            config[key] = value
            save_config(config)
            return f"Config: {key} = {value}"
        
        # EXEC: status
        elif cmd == "status":
            ctx = load_editorial_context()
            return f"Status report:\n{ctx}"
        
        else:
            return f"Unknown command: {cmd}"
            
    except Exception as e:
        return f"EXEC error: {e}"

def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.load(open(CONFIG_PATH))
        except:
            pass
    return {"gap_threshold": 50, "extra_sources": []}

def save_config(config):
    json.dump(config, open(CONFIG_PATH, "w"), indent=2)

def run_full_pipeline():
    """Run all pipeline steps, return results list."""
    results = []
    for name, cmd, timeout, critical in STEPS:
        r = run_cmd(name, cmd, timeout, critical)
        results.append(r)
        if not r["ok"] and critical:
            break
    return results

# ═══════════════════════════════════════════════════════════════════
#  DEEPSEEK
# ═══════════════════════════════════════════════════════════════════

def ask_deepseek(prompt, system=None, max_tokens=800, temp=0.7):
    if not DEEPSEEK_KEY:
        return "[DeepSeek unavailable]"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temp,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"}
    )
    for attempt in range(3):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
            return d["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
            else:
                return f"[DeepSeek error: {e.code}]"
        except Exception as e:
            return f"[DeepSeek error: {e}]"
    return "[DeepSeek unavailable]"

# ═══════════════════════════════════════════════════════════════════
#  EDITORIAL CONTEXT
# ═══════════════════════════════════════════════════════════════════

def load_editorial_context():
    ctx = [f"Time: {datetime.now(timezone.utc).isoformat()}"]
    sf = PUBLIC / "data" / "stories.json"
    if sf.exists():
        try:
            data = json.load(open(sf))
            stories = data.get("all_stories", [])
            ctx.append(f"Total stories: {len(stories)}")
            top = sorted(stories, key=lambda s: s.get("contradiction_gap", 0), reverse=True)[:5]
            ctx.append("Top stories by contradiction gap:")
            for s in top:
                h = s.get("headline", "?")[:80]
                g = s.get("contradiction_gap", 0)
                t = s.get("tier", "?")
                n = s.get("container", "?").replace("_", " ").title()
                v = s.get("capital_volume_usd", 0)
                sid = s.get("id", "?")
                ctx.append(f"  id={sid} [{t}] gap={g} | {n} | ${v:,.0f} | {h}")
            narratives = {}
            for s in stories:
                n = s.get("container", "unknown")
                narratives[n] = narratives.get(n, 0) + 1
            ctx.append("Narrative distribution:")
            for n, c in sorted(narratives.items(), key=lambda x: -x[1]):
                ctx.append(f"  {n}: {c}")
        except:
            ctx.append("(stories.json load error)")
    config = load_config()
    ctx.append(f"Config: gap_threshold={config.get('gap_threshold', 50)}")
    return "\n".join(ctx)

# ═══════════════════════════════════════════════════════════════════
#  MAILBOX + CEO HANDLER
# ═══════════════════════════════════════════════════════════════════

def handle_editorial_directive(message):
    """Send directive to CEO, parse response, execute commands. Returns (judgment, exec_results)."""
    context = load_editorial_context()
    full_prompt = f"""DIRECTIVE FROM ALEXANDER (via Hermes):
{message}

CURRENT STATE:
{context}

Respond as CEO. Issue EXEC commands if action is needed."""
    
    response = ask_deepseek(full_prompt, system=SYSTEM_PROMPT, max_tokens=1000, temp=0.7)
    
    # Split response into editorial part and execution commands
    lines = response.split("\n")
    editorial_lines = []
    exec_commands = []
    exec_results = []
    
    for line in lines:
        if line.strip().startswith("EXEC:"):
            exec_commands.append(line.strip())
        else:
            editorial_lines.append(line)
    
    judgment = "\n".join(editorial_lines).strip()
    
    # Execute commands
    for cmd in exec_commands:
        result = execute_command(cmd)
        if result:
            exec_results.append(result)
    
    return judgment, exec_results

def check_mailbox():
    MAILBOX.mkdir(parents=True, exist_ok=True)
    if not INBOX.exists():
        return False
    try:
        inbox = json.load(open(INBOX))
    except:
        return False
    messages = inbox.get("messages", [])
    pending = [m for m in messages if m.get("status") == "pending"]
    if not pending:
        return False
    
    responses = []
    for msg in pending:
        directive = msg.get("content", "")
        sender = msg.get("from", "unknown")
        mid = msg.get("id", "?")
        print(f"\n[mailbox] Directive from {sender}: {directive[:120]}...")
        
        judgment, exec_results = handle_editorial_directive(directive)
        
        # Build response
        full_response = judgment
        if exec_results:
            full_response += "\n\n=== ACTIONS EXECUTED ===\n" + "\n".join(f"- {r}" for r in exec_results)
        
        msg["status"] = "answered"
        msg["responded_at"] = datetime.now(timezone.utc).isoformat()
        responses.append({
            "id": mid, "from": "CEO, La Gazzetta di Kyiv",
            "to": sender, "content": full_response,
            "judgment": judgment, "exec_results": exec_results,
            "at": datetime.now(timezone.utc).isoformat()
        })
        print(f"[mailbox] Response: {judgment[:200]}...")
        print(f"[mailbox] Executed: {len(exec_results)} commands")
    
    inbox["messages"] = messages
    json.dump(inbox, open(INBOX, "w"), indent=2)
    outbox = {"responses": responses}
    if OUTBOX.exists():
        try:
            existing = json.load(open(OUTBOX))
            existing["responses"] = existing.get("responses", []) + responses
            outbox = existing
        except:
            pass
    json.dump(outbox, open(OUTBOX, "w"), indent=2)
    print(f"[mailbox] Processed {len(responses)} directive(s)")
    return True

# ═══════════════════════════════════════════════════════════════════
#  INCIDENT TELEMETRY — Machine-generated pipeline failure logging
# ═══════════════════════════════════════════════════════════════════

INCIDENTS_FILE = PROJECT / "mailbox" / "incidents.json"

def push_incident(step_name, stderr, exit_code=1):
    """
    Appends a structured pipeline failure to incidents.json.
    Categorizes critical architectural failures vs data degradation warnings.
    """
    critical_steps = ["ingestion", "synthesis", "classify", "calc_capital", "build_frontend"]
    severity = "CRITICAL" if step_name in critical_steps else "WARNING"

    incident = {
        "ticket_id": f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "type": "pipeline_failure",
        "severity": severity,
        "step": step_name,
        "context": {
            "exit_code": exit_code,
            "error_summary": (stderr or "Unknown runtime error")[:500].strip(),
            "detected_at": datetime.now(timezone.utc).isoformat()
        },
        "remediation_attempts": 0,
        "status": "unresolved"
    }

    try:
        os.makedirs(os.path.dirname(INCIDENTS_FILE), exist_ok=True)

        if os.path.exists(INCIDENTS_FILE) and os.path.getsize(INCIDENTS_FILE) > 0:
            with open(INCIDENTS_FILE, "r+") as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
                except json.JSONDecodeError:
                    data = []

                data.append(incident)
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        else:
            with open(INCIDENTS_FILE, "w") as f:
                json.dump([incident], f, indent=2)

    except Exception as telemetry_err:
        print(f"[Telemetry Error] Could not write incident ticket for {step_name}: {telemetry_err}")

# ═══════════════════════════════════════════════════════════════════
#  CLOUD FUNCTION BRIDGE — CEO → Hermes notifications
# ═══════════════════════════════════════════════════════════════════

GCF_URL = os.environ.get("GCF_GOVERNOR_BRIDGE_URL", "")

def notify_hermes(directive, context=None, priority="medium"):
    """Post a directive to the Cloud Function bridge for Hermes."""
    if not GCF_URL:
        print("[bridge] No GCF URL configured — skipping Hermes notification")
        return False
    try:
        payload = json.dumps({
            "directive": directive,
            "from": "CEO / Sovereign Auditor",
            "priority": priority,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).encode()
        req = urllib.request.Request(
            GCF_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        print(f"[bridge] Hermes notified: {result}")
        return True
    except Exception as e:
        print(f"[bridge] Failed to notify Hermes: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════════

def tg_send(text, chat_id=None):
    target = chat_id or TELEGRAM_ADMIN_CHAT
    if not TELEGRAM_TOKEN or not target:
        return False
    try:
        u = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        b = json.dumps({"chat_id": target, "text": text[:4000], "parse_mode": "Markdown", "disable_web_page_preview": True}).encode()
        r = urllib.request.Request(u, data=b, headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=10).read().decode()).get("ok", False)
    except:
        return False

# ═══════════════════════════════════════════════════════════════════
#  PIPELINE
# ═══════════════════════════════════════════════════════════════════

PARALLEL_STEPS = [
    # ── Sovereign Vault & Data Collectors ──
    ("youtube",      [str(VENV), str(SCRIPTS/"fetch_youtube.py"), "--hours", "72"],     60, False),
    ("arxiv",        [str(VENV), str(SCRIPTS/"fetch_arxiv.py"), "--hours", "168"],      90, False),
    ("patents",      [str(VENV), str(SCRIPTS/"fetch_patents.py")],                      120, False),
    ("mediastack",   [str(VENV), str(SCRIPTS/"fetch_mediastack.py")],                   120, False),
    ("newsdata",     [str(VENV), str(SCRIPTS/"fetch_newsdata.py")],                     120, False),
    ("narrative_cap",[str(VENV), str(SCRIPTS/"fetch_narrative_cap.py")],               120, False),
    ("market_data",   [str(VENV), str(SCRIPTS/"market_reality.py"), "--all"],               90, True),
    ("cftc_data",     [str(VENV), str(SCRIPTS/"fetch_cftc.py")],                           60, False),
    ("cftc_financial",[str(VENV), str(SCRIPTS/"fetch_cftc_financial.py")],                  90, False),
    ("fred_data",     [str(VENV), str(SCRIPTS/"fetch_fred.py")],                          120, False),
    ("derivatives",   [str(VENV), str(SCRIPTS/"fetch_derivatives.py")],                     30, False),
]

SEQUENTIAL_STEPS = [
    # ── Core Pipeline ──
    ("ingestion",     [str(VENV), str(SCRIPTS/"ingestion_triage.py")],                    120, True),
    ("synthesis",     [str(VENV), str(SCRIPTS/"contradiction_synthesizer.py")],            180, True),
    ("classify",      [str(VENV), str(SCRIPTS/"classify_stories.py")],                      30, False),
    ("calc_capital",  [str(VENV), str(SCRIPTS/"calculate_capital.py")],                     60, True),
    ("settle_trades", [str(VENV), str(SCRIPTS/"settle_trades.py")],                         90, False),
    ("gen_flows",     [str(VENV), str(SCRIPTS/"generate_flows.py")],                       30, False),
    ("editorial_enrich", [str(VENV), str(SCRIPTS/"editorial_enrichment.py")],             300, False),
    ("build_frontend",    [str(VENV), str(SCRIPTS/"build_frontend.py")],                            60, True),
    ("test_platform", [str(VENV), str(SCRIPTS/"test_platform.py")],                         30, False),
    ("telegram_post", [str(VENV), str(SCRIPTS/"telegram_broadcast.py")],                   60, False),
    ("deploy", ["bash", str(SCRIPTS/"shipit.sh")], 120, False),
]

def run_cmd(name, cmd, timeout, critical):
    print(f"\n{'='*50}\n[{name}] running...")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(PROJECT), env={**os.environ, "PYTHONUNBUFFERED":"1", "DEEPSEEK_API_KEY": DEEPSEEK_KEY or "", "CFTC_API_KEY": CFTC_API_KEY or "", "FRED_API_KEY": FRED_API_KEY or "", "TELEGRAM_BOT_TOKEN": TELEGRAM_TOKEN or "", "TELEGRAM_BROADCAST_CHAT_ID": TELEGRAM_BROADCAST_CHAT or ""})
        ok = r.returncode == 0
        t = time.time()-t0
        out = {"name":name, "ok":ok, "code":r.returncode, "stdout":r.stdout[-1500:],
               "stderr":r.stderr[-1500:], "elapsed":t, "critical":critical}
        print(f"[{name}] {'OK' if ok else 'FAIL('+str(r.returncode)+')'} in {t:.1f}s")
        if r.stdout:
            for l in r.stdout.strip().split('\n')[-3:]:
                print(f"  {l}")
        if not ok and r.stderr:
            print(f"  STDERR: {r.stderr[:300]}")
        return out
    except subprocess.TimeoutExpired:
        print(f"[{name}] TIMEOUT {timeout}s")
        return {"name":name, "ok":False, "code":-1, "stdout":"", "stderr":f"Timeout {timeout}s", "elapsed":time.time()-t0, "critical":critical}
    except Exception as e:
        print(f"[{name}] CRASH: {e}")
        return {"name":name, "ok":False, "code":-2, "stdout":"", "stderr":str(e), "elapsed":time.time()-t0, "critical":critical}

def cycle():
    print(f"\n{'#'*50}\n# Cycle: {datetime.now(timezone.utc).isoformat()}\n{'#'*50}")
    check_mailbox()
    results = []
    fatal = False
    
    # 1. Run Data Collectors in Parallel
    print("\n--- Running Data Collectors Concurrently ---")
    processes = []
    t0 = time.time()
    for name, cmd, timeout, critical in PARALLEL_STEPS:
        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(PROJECT),
                env={**os.environ, "PYTHONUNBUFFERED":"1", "DEEPSEEK_API_KEY": DEEPSEEK_KEY or "", "CFTC_API_KEY": CFTC_API_KEY or "", "FRED_API_KEY": FRED_API_KEY or "", "TELEGRAM_BOT_TOKEN": TELEGRAM_TOKEN or "", "TELEGRAM_BROADCAST_CHAT_ID": TELEGRAM_BROADCAST_CHAT or ""}
            )
            processes.append((name, p, timeout, critical, time.time()))
        except Exception as e:
            print(f"[Parallel] Launch error {name}: {e}")
            results.append({"name": name, "ok": False, "code": -2, "stdout": "", "stderr": str(e), "elapsed": 0.0, "critical": critical})
            if critical:
                fatal = True

    # Poll until all parallel steps finish
    while processes and not fatal:
        still_running = []
        for name, p, timeout, critical, start_time in processes:
            elapsed = time.time() - start_time
            ret = p.poll()
            if ret is not None:
                # Process completed!
                stdout, stderr = p.communicate()
                ok = ret == 0
                r = {"name": name, "ok": ok, "code": ret, "stdout": stdout[-1500:], "stderr": stderr[-1500:], "elapsed": elapsed, "critical": critical}
                print(f"[Parallel] {name} complete: {'OK' if ok else 'FAIL('+str(ret)+')'} in {elapsed:.1f}s")
                results.append(r)
                if not ok:
                    push_incident(step_name=name, stderr=r.get("stderr", ""), exit_code=ret)
                    if critical:
                        fatal = True
            elif elapsed > timeout:
                # Timeout! Kill it
                p.kill()
                stdout, stderr = p.communicate()
                print(f"[Parallel] {name} TIMEOUT after {timeout}s")
                r = {"name": name, "ok": False, "code": -1, "stdout": stdout[-1500:], "stderr": f"Timeout {timeout}s", "elapsed": elapsed, "critical": critical}
                results.append(r)
                push_incident(step_name=name, stderr=r.get("stderr", ""), exit_code=-1)
                if critical:
                    fatal = True
            else:
                still_running.append((name, p, timeout, critical, start_time))
        processes = still_running
        time.sleep(0.1)

    # Clean up any leftover parallel processes if fatal occurred early
    for name, p, _, _, _ in processes:
        try: p.kill()
        except: pass

    # 2. Run Core Pipeline Steps Sequentially (only if parallel collectors succeeded)
    if not fatal:
        print("\n--- Running Core Pipeline Steps Sequentially ---")
        for name, cmd, timeout, critical in SEQUENTIAL_STEPS:
            r = run_cmd(name, cmd, timeout, critical)
            results.append(r)
            if not r["ok"]:
                push_incident(
                    step_name=name,
                    stderr=r.get("stderr", ""),
                    exit_code=r.get("code", 1)
                )
                
                if name == "synthesis" and r["code"] == 1 and "No unprocessed" in r.get("stdout",""):
                    print("[governor] No new items — continuing")
                    continue
                if critical:
                    fatal = True
                    break

    # 3. Report Results
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if not fatal:
        try:
            n = len(json.load(open(PUBLIC/"data"/"stories.json")).get("all_stories",[]))
        except: n = "?"
        ok = sum(1 for r in results if r["ok"])
        print(f"\n[governor] {ok}/{len(results)} OK. {n} stories.")
        tg_send(f"*Gazzetta* — {now}\n{n} stories | {ok}/{len(results)} steps OK")
    else:
        failed = [r for r in results if not r["ok"]]
        ctx = "Pipeline failures:\n"
        for r in failed:
            ctx += f"\n{r['name']}: {r.get('stderr','')[:300]}"
        diag = ask_deepseek(f"Diagnose these pipeline failures in 2 sentences:\n{ctx}", max_tokens=150, temp=0.3)
        tg_send(f"*Gazzetta ALERT* — {now}\n\n{diag}")
    return 1 if fatal else 0

if __name__ == "__main__":
    sys.exit(cycle())
