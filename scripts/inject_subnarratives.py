import yaml

with open('/Users/alexandersolianin/Projects/gazzetta-di-kyiv/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

subnarratives_data = {
    "usd_debasement_reserve_diversification": {
        "brics_payment_rails": {
            "title": "BRICS Alternative Payment Rails",
            "description": "De-dollarization efforts via bilateral trade settlement and non-SWIFT clearing infrastructure."
        },
        "sovereign_gold_accumulation": {
            "title": "Sovereign Gold Accumulation",
            "description": "Physical gold buying by non-Western central banks as a neutral reserve asset."
        },
        "treasury_market_illiquidity": {
            "title": "Treasury Market Illiquidity",
            "description": "Signs of stress, reduced foreign buying, and structural changes in the US Treasury market."
        }
    },
    "critical_resource_control_infrastructure": {
        "strategic_minerals_hoarding": {
            "title": "Strategic Minerals Hoarding",
            "description": "State-level accumulation of rare earths, copper, and uranium."
        },
        "energy_grid_modernization": {
            "title": "Energy Grid Modernization",
            "description": "Investments in grid resilience and next-generation nuclear to support AI compute."
        },
        "lng_infrastructure_expansion": {
            "title": "LNG Infrastructure Expansion",
            "description": "Securing long-term non-Russian gas supplies and building export/import terminals."
        }
    },
    "supply_chain_resilience_reshoring_defense": {
        "defense_industrial_base": {
            "title": "Defense Industrial Base Revitalization",
            "description": "Capital allocation toward continental munition, aerospace, and defense contractors."
        },
        "manufacturing_nearshoring": {
            "title": "Manufacturing Nearshoring",
            "description": "Relocating critical manufacturing closer to domestic markets to reduce geopolitical risk."
        },
        "tariff_regime_shifts": {
            "title": "Tariff Regime Shifts",
            "description": "New protectionist measures and trade barriers reshaping global logistics."
        }
    },
    "china_geoeconomic_expansion": {
        "belt_and_road_2_0": {
            "title": "Belt and Road 2.0",
            "description": "Targeted infrastructure investments focusing on digital and green energy corridors."
        },
        "rmb_internationalization": {
            "title": "RMB Internationalization",
            "description": "Expanding the use of the Yuan in cross-border trade and commodity pricing."
        },
        "smic_foundry_advancements": {
            "title": "Domestic Foundry Advancements",
            "description": "China's push for semiconductor independence despite Western export controls."
        }
    },
    "space_economy_commercialization": {
        "leo_constellations": {
            "title": "LEO Satcom Constellations",
            "description": "Rapid deployment of low Earth orbit networks for global broadband and military communications."
        },
        "space_logistics_and_launch": {
            "title": "Space Logistics & Launch Capacity",
            "description": "Commercial scaling of reusable rockets and orbital transfer vehicles."
        },
        "lunar_infrastructure": {
            "title": "Lunar Infrastructure Race",
            "description": "State and commercial efforts to establish permanent bases and resource extraction on the Moon."
        }
    },
    "gene_editing_biotech_longevity": {
        "crispr_therapeutics": {
            "title": "CRISPR & In-Vivo Editing",
            "description": "Transition of CRISPR therapies from clinical trials to commercial markets."
        },
        "advanced_biomanufacturing": {
            "title": "Advanced Biomanufacturing",
            "description": "Scaling production of biologics and synthetic biology applications."
        },
        "longevity_interventions": {
            "title": "Commercial Longevity Interventions",
            "description": "Emerging therapeutics aimed at healthspan extension and cellular rejuvenation."
        }
    },
    "tech_convergence_platforms_ai_autonomy": {
        "autonomous_agents": {
            "title": "Autonomous AI Agents",
            "description": "Deployment of AI systems capable of executing complex, multi-step workflows."
        },
        "enterprise_ai_integration": {
            "title": "Enterprise AI Integration",
            "description": "Adoption of generative AI models to restructure corporate productivity and operations."
        },
        "quantum_ai_convergence": {
            "title": "Quantum-AI Convergence",
            "description": "Early breakthroughs in using quantum computing to accelerate machine learning."
        }
    },
    "prestige_asset_acquisition_strategic_investment": {
        "sovereign_sports_investments": {
            "title": "Sovereign Sports Investments",
            "description": "Middle Eastern and Asian sovereign funds acquiring marquee sports franchises."
        },
        "cultural_soft_power": {
            "title": "Cultural Soft Power Assets",
            "description": "Strategic investments in media, entertainment, and gaming publishers."
        },
        "trophy_real_estate": {
            "title": "Trophy Real Estate & Infrastructure",
            "description": "Acquisition of ultra-prime properties and critical logistics hubs by state actors."
        }
    },
    "ai_compute_semiconductor_hegemony": {
        "advanced_node_monopoly": {
            "title": "Advanced Node Monopoly",
            "description": "The concentration of sub-3nm manufacturing capabilities in a few foundries."
        },
        "ai_accelerator_dominance": {
            "title": "AI Accelerator Dominance",
            "description": "The hyperscaler race to secure next-generation GPUs and custom silicon."
        },
        "export_control_evasion": {
            "title": "Export Control Evasion & Adaptation",
            "description": "Market responses to semiconductor sanctions and the rise of gray market compute."
        }
    },
    "digital_assets_reserves_onchain_finance": {
        "stablecoin_settlement": {
            "title": "Stablecoin Settlement Networks",
            "description": "Integration of stablecoins into traditional payment rails and cross-border trade."
        },
        "tokenized_real_world_assets": {
            "title": "Tokenized Real-World Assets",
            "description": "Bringing treasuries, credit, and private equity on-chain for institutional liquidity."
        },
        "sovereign_btc_adoption": {
            "title": "Sovereign Bitcoin Adoption",
            "description": "Nation-states incorporating Bitcoin into their strategic reserves or legal frameworks."
        }
    },
    "monetary_policy_regime_shift_rate_cycle": {
        "higher_for_longer_regime": {
            "title": "Higher-for-Longer Regime",
            "description": "Structural inflation forcing central banks to maintain restrictive real rates."
        },
        "yield_curve_dynamics": {
            "title": "Yield Curve Dynamics",
            "description": "Shifts in term premia and the implications of curve un-inversion."
        },
        "central_bank_divergence": {
            "title": "Central Bank Policy Divergence",
            "description": "Decoupling of monetary policy paths between the Fed, ECB, and BOJ."
        }
    },
    "commodity_supercycle_supply_rebalancing": {
        "energy_transition_metals": {
            "title": "Energy Transition Metals",
            "description": "Structural supply deficits in copper, lithium, and nickel driven by electrification."
        },
        "agricultural_supply_shocks": {
            "title": "Agricultural Supply Shocks",
            "description": "Disruptions to global food supplies due to weather anomalies and trade barriers."
        },
        "upstream_underinvestment": {
            "title": "Upstream Underinvestment",
            "description": "Capital starvation in legacy fossil fuel extraction leading to supply inelasticity."
        }
    }
}

for narrative_id, sub_data in subnarratives_data.items():
    if narrative_id in config['narratives']:
        config['narratives'][narrative_id]['subnarratives'] = sub_data

class Dumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)

with open('/Users/alexandersolianin/Projects/gazzetta-di-kyiv/config.yaml', 'w') as f:
    yaml.dump(config, f, Dumper=Dumper, sort_keys=False, default_flow_style=False)

print("Updated config.yaml with subnarratives.")
