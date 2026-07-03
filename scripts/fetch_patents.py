#!/usr/bin/env python3
"""
fetch_patents.py — Google Patents monitor for the Gazzetta Sovereign Vault.

Uses SerpAPI's google_patents engine to pull patent filings aligned with our
12 macro narratives. Free tier: 250 searches/month → we run 60 targeted queries
per cycle (~weekly), each returning up to 100 patents with date filtering.

Strategy:
  - 12 narratives × 5 queries = 60 queries/cycle
  - num=100 (max) → up to 6,000 patents/cycle
  - before:priority:YYYYMMDD filter → only patents filed since last cycle
  - ~4 cycles/month = 240 searches → 10-credit buffer

Output: data/vault/raw/patents/YYYY-WW/batch.json

Usage:
  python3 scripts/fetch_patents.py
  python3 scripts/fetch_patents.py --dry-run    # show queries without API calls
  python3 scripts/fetch_patents.py --reset      # clear state, full re-fetch
"""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
VAULT = PROJECT / "data" / "vault" / "raw" / "patents"
STATE_FILE = PROJECT / "data" / "patent_state.json"
SERPAPI_KEYS = [k.strip() for k in os.environ.get("SERPAPI_API_KEY", "").split(",") if k.strip()]
API_BASE = "https://serpapi.com/search"

# ── 12 narratives → 5 targeted patent queries each (60 total) ──────────
QUERIES = {
    "compute-hegemony": [
        "GPU architecture machine learning accelerator",
        "high bandwidth memory HBM semiconductor interconnect",
        "neural processing unit NPU edge inference chip",
        "photonic computing optical processor",
        "wafer scale integration chiplet advanced packaging",
    ],
    "eurasia-capital-architecture": [
        "cross border payment settlement blockchain BRICS",
        "central bank digital currency CBDC architecture",
        "alternative financial messaging SWIFT system",
        "digital yuan e-CNY payment infrastructure",
        "multilateral currency swap clearing mechanism",
    ],
    "physical-resource-revaluation": [
        "rare earth element extraction separation processing",
        "lithium direct extraction brine DLE technology",
        "critical mineral processing beneficiation",
        "deep sea mining nodule collection system",
        "urban mining e-waste metal recovery",
    ],
    "decentralized-capital-architecture": [
        "blockchain consensus mechanism proof stake",
        "multi-party computation MPC cryptographic custody",
        "decentralized exchange automated market maker AMM",
        "zero knowledge proof ZK rollup scaling",
        "smart contract formal verification security",
    ],
    "industrial-reshoring-defense": [
        "advanced semiconductor fabrication manufacturing",
        "autonomous drone swarm military defense system",
        "additive manufacturing 3D printing aerospace",
        "hypersonic vehicle propulsion thermal protection",
        "directed energy weapon laser defense system",
    ],
    "sovereign-liquidity-migration": [
        "sovereign wealth fund portfolio optimization",
        "government bond market microstructure liquidity",
        "central bank reserve management diversification",
        "treasury management real time gross settlement",
        "sovereign credit default swap pricing model",
    ],
    "energy-sovereignty": [
        "nuclear fusion reactor magnetic confinement tokamak",
        "small modular reactor SMR advanced nuclear",
        "grid scale battery energy storage long duration",
        "green hydrogen electrolyzer production catalyst",
        "geothermal enhanced deep closed loop system",
    ],
    "longevity-bioreality": [
        "mRNA vaccine therapeutic delivery lipid nanoparticle",
        "CRISPR gene editing therapeutic base prime",
        "senolytic senescent cell clearance aging",
        "cellular reprogramming epigenetic rejuvenation Yamanaka",
        "longevity biomarker biological age clock methylation",
    ],
    "liquidity-regime-transition": [
        "quantitative trading market making algorithm",
        "high frequency trading FPGA hardware acceleration",
        "portfolio risk management tail hedging strategy",
        "treasury yield curve modeling term structure",
        "market microstructure order flow toxicity prediction",
    ],
    "orbital-industrialization": [
        "satellite constellation low earth orbit communication",
        "reusable rocket launch vehicle propulsive landing",
        "in space manufacturing microgravity material processing",
        "space debris removal active deorbit capture",
        "orbital servicing refueling docking satellite",
    ],
    "enterprise-intelligence-consolidation": [
        "large language model transformer architecture training",
        "retrieval augmented generation RAG enterprise knowledge",
        "autonomous AI agent multi-step reasoning planning",
        "neural network model compression quantization distillation",
        "foundation model fine-tuning instruction alignment RLHF",
    ],
    "trophy-asset-financialization": [
        "real world asset tokenization blockchain fractional",
        "fine art authentication provenance blockchain NFT",
        "collectible alternative asset valuation appraisal model",
        "private equity secondary market liquidity tokenization",
        "luxury real estate fractional ownership platform",
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    """Load persistent state: last fetch date per narrative."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


SERPER_KEY = os.environ.get("SERPER_API_KEY", "1d8f654b3acd549d0ed5138a490fed098ce877bf")
SEARCHSPACE_KEY = os.environ.get("SEARCHSPACE_API_KEY", "")
SERPSTACK_KEY = os.environ.get("SERPSTACK_API_KEY", "8a9ea98d21ba017c3fcd402913a732ef")

def _fetch_serpapi(query: str, start: int = 0, num: int = 100) -> dict:
    """Call SerpAPI google_patents engine with key pooling."""
    if not SERPAPI_KEYS:
        return {"organic_results": [], "search_information": {}, "error": "No SerpAPI keys"}
        
    for api_key in SERPAPI_KEYS:
        params = {
            "engine": "google_patents",
            "q": query,
            "num": str(num),
            "start": str(start),
            "api_key": api_key,
        }
        qs = urllib.parse.urlencode(params)
        url = f"{API_BASE}?{qs}"

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GazzettaVault/1.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode())
                    if "error" in data:
                        print(f"  ⚠ SerpAPI error: {data['error']}", file=sys.stderr)
                        # If invalid key, try next key, else return
                        if "Invalid API key" in data['error'] or "Searches limit reached" in data['error']:
                            break # break attempt loop, try next key
                        return {"organic_results": [], "search_information": {}, "error": data["error"]}
                    return data
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:500] if e.fp else ""
                print(f"  ⚠ HTTP {e.code}: {body}", file=sys.stderr)
                if e.code == 429:
                    time.sleep(2 ** attempt)
                    continue
                # If unauthorized/quota, break to next key
                if e.code in [401, 403]:
                    break
                return {"organic_results": [], "search_information": {}, "error": f"HTTP {e.code}"}
            except Exception as e:
                print(f"  ⚠ Request failed (attempt {attempt+1}/3): {e}", file=sys.stderr)
                time.sleep(2 ** attempt)

    return {"organic_results": [], "search_information": {}, "error": "max retries or quota exceeded on all keys"}

def _fetch_serper(query: str, start: int = 0, num: int = 100) -> dict:
    """Call Serper.dev Patents search API."""
    url = "https://google.serper.dev/patents"
    headers = {
        "X-API-KEY": SERPER_KEY,
        "Content-Type": "application/json",
        "User-Agent": "GazzettaVault/1.0"
    }
    payload = json.dumps({
        "q": query,
        "num": num
    }).encode("utf-8")
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                
                organic_results = []
                for item in data.get("organic", []):
                    pub_num = item.get("publicationNumber", "")
                    patent_id = pub_num or item.get("link", "").split("/patent/")[-1].split("/")[0]
                    organic_results.append({
                        "patent_id": patent_id,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "assignee": item.get("assignee", ""),
                        "inventor": item.get("inventor", ""),
                        "priority_date": item.get("priorityDate", ""),
                        "filing_date": item.get("filingDate", ""),
                        "grant_date": item.get("grantDate", ""),
                        "publication_date": item.get("publicationDate", ""),
                        "publication_number": pub_num,
                        "patent_link": item.get("link", ""),
                        "language": item.get("language", ""),
                        "thumbnail": item.get("thumbnailUrl", ""),
                    })
                return {
                    "organic_results": organic_results,
                    "search_information": {"total_results": len(organic_results)}
                }
        except Exception as e:
            print(f"  ⚠ Serper request failed (attempt {attempt+1}/3): {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
            
    return {"organic_results": [], "error": "Serper max retries"}

def _fetch_searchspace(query: str, start: int = 0, num: int = 100) -> dict:
    """Call SearchSpace search API as fallback."""
    url = "https://q.searchspace.io/v1/search"
    headers = {
        "authorization": f"Bearer {SEARCHSPACE_KEY}",
        "content-type": "application/json",
        "User-Agent": "GazzettaVault/1.0"
    }
    full_query = f"{query} site:patents.google.com"
    payload = json.dumps({
        "query": full_query,
        "top_k": num
    }).encode("utf-8")
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                
                organic_results = []
                for item in data.get("results", []):
                    link = item.get("url", "")
                    patent_id = ""
                    if "/patent/" in link:
                        patent_id = link.split("/patent/")[-1].split("/")[0]
                    organic_results.append({
                        "patent_id": patent_id,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "assignee": "",
                        "inventor": "",
                        "priority_date": "",
                        "filing_date": "",
                        "grant_date": "",
                        "publication_date": "",
                        "publication_number": patent_id,
                        "patent_link": link,
                        "language": "en",
                        "thumbnail": "",
                    })
                return {
                    "organic_results": organic_results,
                    "search_information": {"total_results": len(organic_results)}
                }
        except Exception as e:
            print(f"  ⚠ SearchSpace request failed (attempt {attempt+1}/3): {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
            
    return {"organic_results": [], "error": "SearchSpace max retries"}

def _fetch_serpstack(query: str, num: int = 100) -> dict:
    """Call Serpstack search API as fallback."""
    url = f"https://api.serpstack.com/search?access_key={SERPSTACK_KEY}&query={urllib.parse.quote(query)}+site:patents.google.com&num={num}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GazzettaVault/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                
                organic_results = []
                for item in data.get("organic_results", []):
                    link = item.get("url", "")
                    patent_id = ""
                    if "/patent/" in link:
                        patent_id = link.split("/patent/")[-1].split("/")[0]
                    else:
                        continue
                    organic_results.append({
                        "patent_id": patent_id,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "assignee": "",
                        "inventor": "",
                        "priority_date": "",
                        "filing_date": "",
                        "grant_date": "",
                        "publication_date": "",
                        "publication_number": patent_id,
                        "patent_link": link,
                        "language": "en",
                        "thumbnail": "",
                    })
                return {
                    "organic_results": organic_results,
                    "search_information": {"total_results": len(organic_results)}
                }
        except Exception as e:
            print(f"  ⚠ Serpstack request failed (attempt {attempt+1}/3): {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
            
    return {"organic_results": [], "error": "Serpstack max retries"}

def fetch_patents(query: str, start: int = 0, num: int = 100) -> dict:
    """Try Serper.dev Patents, fallback to SerpAPI, fallback to Serpstack, fallback to SearchSpace."""
    if SERPER_KEY:
        print("  Attempting Serper Patents...")
        res = _fetch_serper(query, start, num)
        if res and not res.get("error") and len(res.get("organic_results", [])) > 0:
            return res
        print("  Serper failed or returned no results, trying SerpAPI fallback...")
        
    if SERPAPI_KEYS:
        print("  Attempting SerpAPI...")
        res = _fetch_serpapi(query, start, num)
        if res and not res.get("error") and len(res.get("organic_results", [])) > 0:
            return res
        print("  SerpAPI fallback failed or returned no results, trying Serpstack...")

    if SERPSTACK_KEY:
        print("  Attempting Serpstack...")
        res = _fetch_serpstack(query, num)
        if res and not res.get("error") and len(res.get("organic_results", [])) > 0:
            return res
        print("  Serpstack fallback failed or returned no results, trying SearchSpace...")
        
    if SEARCHSPACE_KEY:
        print("  Attempting SearchSpace...")
        res = _fetch_searchspace(query, start, num)
        if res and not res.get("error"):
            return res
            
    return {"organic_results": [], "search_information": {}, "error": "All patent search engines failed or are unconfigured"}


def extract_patent_fields(patent: dict) -> dict:
    """Extract only the fields we care about from a patent result."""
    return {
        "patent_id": patent.get("patent_id", ""),
        "title": patent.get("title", ""),
        "snippet": patent.get("snippet", ""),
        "assignee": patent.get("assignee", ""),
        "inventor": patent.get("inventor", ""),
        "priority_date": patent.get("priority_date", ""),
        "filing_date": patent.get("filing_date", ""),
        "grant_date": patent.get("grant_date", ""),
        "publication_date": patent.get("publication_date", ""),
        "publication_number": patent.get("publication_number", ""),
        "patent_link": patent.get("patent_link", ""),
        "language": patent.get("language", ""),
        "thumbnail": patent.get("thumbnail", ""),
    }


def main():
    dry_run = "--dry-run" in sys.argv
    reset = "--reset" in sys.argv

    if not SERPAPI_KEYS and not SERPER_KEY and not dry_run:
        print("❌ Neither SERPAPI_API_KEY nor SERPER_API_KEY set in environment.", file=sys.stderr)
        sys.exit(0)

    # Weekly gate: only run once per 7 days (60 calls/cycle × 4 = 240/month, fits free tier)
    min_interval_h = 168  # 7 days
    state = {} if reset else load_state()
    last_full = state.get("_last_full_fetch", "1970-01-01T00:00:00Z")
    try:
        last_dt = datetime.fromisoformat(last_full.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
    except (ValueError, TypeError):
        elapsed = float("inf")

    if elapsed < min_interval_h and not dry_run:
        remaining = min_interval_h - elapsed
        print(f"⏭ Skipping patent fetch — last run {elapsed:.1f}h ago (wait {remaining:.1f}h)")
        print(f"   API calls this month: {state.get('_api_calls_this_month', '?')}/250")
        return

    today = datetime.now(timezone.utc)
    week_label = today.strftime("%Y-W%W")

    if dry_run:
        print(f"🔍 DRY RUN — {len(QUERIES)} narratives, {sum(len(qs) for qs in QUERIES.values())} queries")
        print(f"   Date filter: priority_date >= last fetch per narrative")
        print(f"   Output: {VAULT}/{week_label}/batch.json\n")

    total_patents = 0
    total_new = 0
    all_batches = []
    api_calls = 0

    for narrative_slug, queries in QUERIES.items():
        last_fetch = state.get(narrative_slug, "1970-01-01")
        narrative_patents = []

        for query in queries:
            # Append date filter: only patents filed since last fetch
            if last_fetch != "1970-01-01":
                # Format: before:priority:YYYYMMDD — SerpAPI supports this
                date_str = last_fetch.replace("-", "")[:8]
                full_query = f"{query} after:priority:{date_str}"
            else:
                full_query = query

            if dry_run:
                print(f"  [{narrative_slug}] {full_query[:90]}...")
                continue

            api_calls += 1
            data = fetch_patents(full_query)
            results = data.get("organic_results", [])
            total = int(data.get("search_information", {}).get("total_results", 0))
            new_patents = [extract_patent_fields(p) for p in results]

            narrative_patents.extend(new_patents)
            total_patents += total
            total_new += len(new_patents)

            # Respect rate limit: SerpAPI free tier = 250/hour
            time.sleep(0.25)  # 4 calls/sec max

        if narrative_patents and not dry_run:
            all_batches.append({
                "narrative": narrative_slug,
                "query_count": len(queries),
                "patents_fetched": len(narrative_patents),
                "patents": narrative_patents,
            })

        # Update state for next cycle
        if narrative_patents:
            dates = [p.get("priority_date", "") for p in narrative_patents if p.get("priority_date")]
            if dates:
                state[narrative_slug] = max(dates)

        symbol = "🔍" if dry_run else ("📂" if narrative_patents else "  ")
        print(f"  {symbol} {narrative_slug}: {len(narrative_patents)} new patents")

    if dry_run:
        print(f"\n✅ Dry run complete. {sum(len(qs) for qs in QUERIES.values())} queries ready.")
        return

    # Save batch
    VAULT.mkdir(parents=True, exist_ok=True)
    batch_path = VAULT / week_label / "batch.json"
    batch_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "fetched_at": now_iso(),
        "week": week_label,
        "api_calls": api_calls,
        "narratives": len(all_batches),
        "total_patents_new": total_new,
        "batches": all_batches,
    }
    batch_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    state["_last_full_fetch"] = now_iso()
    save_state(state)

    print(f"\n📊 Patent cycle complete: {total_new} new patents across {len(all_batches)} narratives")
    print(f"   API calls used: {api_calls}/250 this month")
    print(f"   Saved: {batch_path}")


if __name__ == "__main__":
    main()
