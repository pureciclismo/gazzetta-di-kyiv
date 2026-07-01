import json
import random
from datetime import datetime, timezone

def generate_payload():
    narratives = {
        "european_sovereignty": {
            "title": "European Sovereignty & Autonomy",
            "subtitle": "Defense, energy independence, and tech sovereignty",
            "subnarratives": ["defense_industrial_base", "energy_independence", "tech_sovereignty", "supply_chain_nearshoring"]
        },
        "global_realignment": {
            "title": "Global Realignment & Multipolarity",
            "subtitle": "BRICS payments, gold accumulation, and resource control",
            "subnarratives": ["brics_payment_rails", "critical_resource_hoarding", "central_bank_gold_accumulation", "eurasian_infrastructure"]
        }
    }

    templates = [
        {
            "headline": "Massive €{amount}B Defense Procurement Cleared by EU Commission",
            "they_say": "The consensus views this as a slow, bureaucratic process unlikely to yield immediate capacity.",
            "reality": "European defense contractors are rapidly scaling production facilities. DFEN surged 4.2% on massive volume.",
            "sub": "defense_industrial_base",
            "tickers": ["DFEN", "RHM.DE"]
        },
        {
            "headline": "France Accelerates Next-Gen Nuclear Reactor Timeline",
            "they_say": "Analysts suggest regulatory hurdles will delay deployment by a decade.",
            "reality": "Capital flows indicate strong institutional backing. Energy independence is aggressively priced in.",
            "sub": "energy_independence",
            "tickers": ["ENR.DE", "EXSA.MI"]
        },
        {
            "headline": "BRICS Unveils Pilot for Non-SWIFT Clearing Network",
            "they_say": "Western media frames this as a symbolic move with no technical capability.",
            "reality": "Gold reserves have surged, and FX flows in emerging markets are actively pricing in the new settlement rail.",
            "sub": "brics_payment_rails",
            "tickers": ["GLD", "UUP"]
        },
        {
            "headline": "PBOC Extends Gold Buying Streak to 18th Month",
            "they_say": "It's merely portfolio rebalancing after dollar weakness.",
            "reality": "This is a structural shift. Central banks are front-running a massive geopolitical realignment away from USD reserves.",
            "sub": "central_bank_gold_accumulation",
            "tickers": ["GLD", "FXI"]
        },
        {
            "headline": "Eastern Europe Emerges as Tech Manufacturing Hub",
            "they_say": "Supply chain shifts will take years to impact earnings.",
            "reality": "Capital expenditure reports show massive immediate inflows into Poland and Romania for microchip and EV battery plants.",
            "sub": "supply_chain_nearshoring",
            "tickers": ["EXSA.MI"]
        },
        {
            "headline": "Sovereign AI Act Propels EU Tech Consortium",
            "they_say": "Regulation will stifle European AI innovation.",
            "reality": "Local venture capital is surging into EU-compliant sovereign models, establishing a massive regulatory moat against US hyperscalers.",
            "sub": "tech_sovereignty",
            "tickers": ["EXSA.MI"]
        },
        {
            "headline": "Strategic Rare Earths Export Controls Enacted",
            "they_say": "This will trigger an immediate supply shock and inflation.",
            "reality": "Market action shows accumulation of strategic reserves began 6 months prior. The market was prepared.",
            "sub": "critical_resource_hoarding",
            "tickers": ["KWEB", "FXI"]
        },
        {
            "headline": "New Energy Corridor Signs Multi-Billion Transit Deal",
            "they_say": "The infrastructure is unviable and heavily indebted.",
            "reality": "Asian capital markets are aggressively financing the debt. The corridor is becoming operational faster than anticipated.",
            "sub": "eurasian_infrastructure",
            "tickers": ["FXI", "KWEB"]
        }
    ]

    containers = {}
    story_id_counter = 1000

    for nid, ndata in narratives.items():
        stories = []
        for i in range(12): # Generate 12 stories per narrative
            template = random.choice([t for t in templates if t["sub"] in ndata["subnarratives"]])
            
            headline = template["headline"].replace("{amount}", str(random.randint(10, 100)))
            
            gap = random.randint(5, 45)
            
            story = {
                "story_id": story_id_counter,
                "headline": headline,
                "slug": headline.lower().replace(" ", "-").replace("€", "").replace(".", ""),
                "they_say": template["they_say"],
                "they_say_quote_verified": True,
                "quote_source_url": "https://example.com/source",
                "reality": template["reality"],
                "reality_data_sources": [],
                "narrative_id": nid,
                "narrative_confidence": round(random.uniform(0.7, 1.0), 2),
                "contradiction_score": gap,
                "contradiction_gap": gap,
                "divergence_magnitude": round(random.uniform(0.1, 5.0), 1),
                "capital_significance": round(random.uniform(0.1, 5.0), 1),
                "causal_strength": round(random.uniform(0.1, 5.0), 1),
                "capital_volume_usd": random.randint(100000000, 5000000000),
                "capital_at_stake_usd": random.randint(50000000, 2000000000),
                "capital_base_usd": random.randint(1000000000, 10000000000),
                "impact_factor": round(random.uniform(0.1, 5.0), 1),
                "narrative_implied_flow_usd": random.randint(100000000, 5000000000),
                "actual_flow_usd": random.randint(100000000, 5000000000),
                "data_fidelity": "TIER_1" if random.random() > 0.5 else "TIER_2",
                "materiality_pass": True,
                "confidence_pct": random.randint(70, 99),
                "event_type": template["sub"],
                "event_magnitude": round(random.uniform(1.0, 10.0), 1),
                "causal_chain": "Event -> Reaction -> Flow",
                "geopolitical_dimension": "high",
                "time_horizon": "strategic",
                "affected_tickers": template["tickers"],
                "affected_asset_classes": ["equities", "commodities", "currencies"],
                "brief_review": "",
                "contradiction_note": ""
            }
            stories.append(story)
            story_id_counter += 1

        containers[nid] = {
            "title": ndata["title"],
            "subtitle": ndata["subtitle"],
            "count": len(stories),
            "stories": stories
        }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "generate_synthetic_payload.py",
        "containers": containers
    }

    with open("/Users/alexandersolianin/Projects/gazzetta-di-kyiv/data/stories.json", "w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    generate_payload()
    print("Successfully generated synthetic payload for stories.json")
