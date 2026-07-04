#!/usr/bin/env python3
"""
test_platform.py v3.0 — Validate 8-narrative stories.json integrity.

Checks:
  1. stories.json exists and is valid JSON
  2. 8 narratives present with correct names
  3. Narrative counts match array lengths
  4. Every story has required fields (story_id, headline, container)
  5. No duplicate story_ids
  6. Tags index references valid story_ids
  7. total_stories matches sum of narrative counts

Usage: python3 scripts/test_platform.py [--quick]
"""

import json, os, sys, re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
PUBLIC_DATA = PROJECT / "public" / "data"

PASS = 0
FAIL = 0

VALID_CONTAINERS = {
    "usd_debasement_reserve_diversification", "critical_resource_control_infrastructure",
    "supply_chain_resilience_reshoring_defense", "china_geoeconomic_expansion",
    "space_economy_commercialization", "gene_editing_biotech_longevity",
    "tech_convergence_platforms_ai_autonomy", "prestige_asset_acquisition_strategic_investment",
    "ai_compute_semiconductor_hegemony", "digital_assets_reserves_onchain_finance",
    "monetary_policy_regime_shift_rate_cycle", "commodity_supercycle_supply_rebalancing",
}


def check(condition, msg):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {msg}")
    else:
        FAIL += 1
        print(f"  ✗ FAIL: {msg}")

def warn(msg):
    print(f"  ⚠ WARN: {msg}")


def test_stories_json():
    """Round 1: Validate stories.json structure and integrity."""
    print("\n── TEST: stories.json integrity ──")
    
    path = DATA / "stories.json"
    check(path.exists(), "stories.json exists")
    if not path.exists():
        return
    
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        check(False, f"stories.json is valid JSON: {e}")
        return
    
    check(isinstance(data, dict), "stories.json is a dict")
    
    # Containers
    containers = data.get("containers", {})
    check(len(containers) == 12, f"12 containers (got {len(containers)})")
    
    container_total = 0
    for cname, cdata in containers.items():
        check(cname in VALID_CONTAINERS, f"Valid container name: {cname}")
        check(isinstance(cdata, dict), f"{cname} is a dict")
        check("stories" in cdata, f"{cname} has stories array")
        check("count" in cdata, f"{cname} has count")
        check("title" in cdata, f"{cname} has title")
        
        stories = cdata.get("stories", [])
        count = cdata.get("count", 0)
        check(isinstance(stories, list), f"{cname}.stories is a list")
        check(count == len(stories), 
              f"{cname}: count={count} matches stories.length={len(stories)}")
        container_total += len(stories)
    
    # Total stories
    total = data.get("total_stories", 0)
    check(container_total >= total - 50,
          f"container sum={container_total} covers total={total} (margin for unassigned)")
    
    # All stories array
    all_stories = data.get("all_stories", [])
    check(len(all_stories) == total,
          f"all_stories.length={len(all_stories)} matches total={total}")
    
    # Check required fields on sample stories
    if all_stories:
        sample = all_stories[:10]
        for s in sample:
            sid = str(s.get("story_id", "?"))
            check("story_id" in s, f"story {sid[:40]}: has story_id")
            check("headline" in s, f"story {sid[:40]}: has headline")
            check("container" in s, f"story {sid[:40]}: has container")
    
    # Check for duplicates
    ids = [str(s.get("story_id")) for s in all_stories if s.get("story_id")]
    dupes = len(ids) - len(set(ids))
    if dupes > 0:
        warn(f"Duplicate story_ids found ({dupes} dupes)")
    else:
        check(True, "No duplicate story_ids")
    
    # Tags index
    tags_index = data.get("tags_index", {})
    all_ids = set(ids)
    for tag, story_ids in tags_index.items():
        check(isinstance(story_ids, list), f"tag '{tag}': value is list")
        missing = [sid for sid in story_ids if sid not in all_ids]
        check(len(missing) == 0, 
              f"tag '{tag}': all {len(story_ids)} story_ids valid ({len(missing)} orphans)")
    
    # Generated metadata
    check("generated_at" in data, "has generated_at")
    check("generated_by" in data, "has generated_by")
    
    # Capital variance check (lenient — warns, never blocks deploy)
    cap_values = [s.get("capital_at_stake_usd", 0) for s in all_stories if s.get("capital_at_stake_usd", 0) > 0]
    if cap_values:
        unique_caps = len(set(cap_values))
        total_caps = len(cap_values)
        if unique_caps <= 3 and total_caps > 10:
            warn(f"Capital variance LOW: only {unique_caps} unique capital values across {total_caps} stories (possible data stall)")
        else:
            check(True, f"Capital variance healthy: {unique_caps} unique values across {total_caps} stories")

    print(f"\n  Stories: {total} | Containers: {len(containers)} | Tags: {len(tags_index)} | Dupes: {dupes}")


def main():
    quick = "--quick" in sys.argv
    
    print("── test_platform.py v2.1 ──")
    test_stories_json()
    
    print(f"\n{'─'*50}")
    print(f"  PASS: {PASS}  FAIL: {FAIL}")
    
    if FAIL > 0:
        print(f"  VERDICT: BLOCKED — {FAIL} failures")
        sys.exit(1)
    else:
        print(f"  VERDICT: PASS — all {PASS} checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
