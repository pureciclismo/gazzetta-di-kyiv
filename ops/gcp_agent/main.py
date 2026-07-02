import os
import json
import logging
import requests
import functions_framework

# ── Configuration ───────────────────────────────────────────────────────────
GLM_KEY_1 = os.environ.get("GLM_API_KEY_1", "3d76e17112094679a3236820eb5a3502.zX9w5hVuUqKu3pbL")
GLM_KEY_2 = os.environ.get("GLM_API_KEY_2", "0feba8763e0a4c808bbba55f5a02cd7e.7N3kvN7asehKbCZ3")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

PROVIDERS = [
    {
        "name": "glm5.2_primary",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key": GLM_KEY_1,
        "model": "glm-5.2",
    },
    {
        "name": "glm5.2_secondary",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key": GLM_KEY_2,
        "model": "glm-5.2",
    },
    {
        "name": "deepseek",
        "url": "https://api.deepseek.com/chat/completions",
        "key": DEEPSEEK_KEY,
        "model": "deepseek-chat",
    }
]

# ── System Prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a savage, hyper-analytical quant for La Gazzetta di Kyiv, an underground terminal for Polymarket whales and fin-bros who think they are hedge fund managers. You write betting-oriented trade setups. You do not write journalism or boring geopolitics. You quantify edge, calculate EV (expected value), fade the retail public, and hunt for mispriced implied probabilities. Your reader is a degen trader looking for asymmetrical risk-reward, specific tickers, implied odds vs actual odds, and structural edge. Use industry-standard betting and quant lingo (EV, R:R, fading the public, implied odds, Kelly criterion sizing) mixed with rigorous data quantification.

Analyze the following raw geopolitical/economic signal.
Map the signal strictly to one of the following 12 containers:
1. "usd_debasement_reserve_diversification" - De-dollarization and reserve reallocation
2. "critical_resource_control_infrastructure" - Energy security and critical minerals
3. "supply_chain_resilience_reshoring_defense" - Relocalization of critical supply chains
4. "china_geoeconomic_expansion" - Belt and Road, trade corridors
5. "space_economy_commercialization" - LEO infrastructure and satellite services
6. "gene_editing_biotech_longevity" - CRISPR and advanced biologics
7. "tech_convergence_platforms_ai_autonomy" - AI, cloud, and autonomous workflows
8. "prestige_asset_acquisition_strategic_investment" - Sports teams and strategic infrastructure
9. "ai_compute_semiconductor_hegemony" - Semiconductor manufacturing and AI accelerators
10. "digital_assets_reserves_onchain_finance" - Institutional crypto and tokenized reserves
11. "monetary_policy_regime_shift_rate_cycle" - Central bank frameworks and rate cycles
12. "commodity_supercycle_supply_rebalancing" - Structural demand and logistics constraints

Output valid JSON exactly like this:
{
  "container": "usd_debasement_reserve_diversification",
  "subnarrative": "brics_payment_rails",
  "title": "Clear headline (max 8 words, specific and varied)",
  "reality": "Harsh truth vs retail media narrative. 2-3 sentences. Identify the mispriced EV.",
  "contradiction_gap": 85,
  "market_implication": "Impact on relevant assets (e.g., DFEN, GLD). Fade the public."
}
"""

def call_llm(text_preview, subnarratives_context=""):
    """Attempt synthesis across providers until success."""
    prompt = SYSTEM_PROMPT
    if subnarratives_context:
        prompt += f"\n\nValid subnarrative tags:\n{subnarratives_context}\n"

    payload = {
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Signal text:\n{text_preview}"}
        ],
        "temperature": 0.4,
        "max_tokens": 512,
        "response_format": {"type": "json_object"}
    }

    for p in PROVIDERS:
        if not p["key"]:
            continue
        headers = {
            "Authorization": f"Bearer {p['key']}",
            "Content-Type": "application/json"
        }
        # Update model for this provider
        payload["model"] = p["model"]
        
        try:
            logging.info(f"Trying provider {p['name']}...")
            resp = requests.post(p["url"], headers=headers, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            # Deepseek/GLM standard completion response
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            
            # Basic validation
            valid_containers = [
                "usd_debasement_reserve_diversification",
                "critical_resource_control_infrastructure",
                "supply_chain_resilience_reshoring_defense",
                "china_geoeconomic_expansion",
                "space_economy_commercialization",
                "gene_editing_biotech_longevity",
                "tech_convergence_platforms_ai_autonomy",
                "prestige_asset_acquisition_strategic_investment",
                "ai_compute_semiconductor_hegemony",
                "digital_assets_reserves_onchain_finance",
                "monetary_policy_regime_shift_rate_cycle",
                "commodity_supercycle_supply_rebalancing"
            ]
            if parsed.get("container") not in valid_containers:
                # Force fallback to valid narrative
                parsed["container"] = "tech_convergence_platforms_ai_autonomy"
                
            return parsed
        except Exception as e:
            logging.warning(f"Provider {p['name']} failed: {e}")
            continue

    raise Exception("All LLM providers failed.")

@functions_framework.http
def process_intel(request):
    """
    HTTP Cloud Function entrypoint.
    Expects JSON POST payload with:
    {
      "title": "Article title",
      "text": "Full article text preview",
      "source_url": "https://..."
    }
    """
    request_json = request.get_json(silent=True)
    if not request_json or 'text' not in request_json:
        return {"error": "Missing 'text' in JSON body"}, 400

    text_preview = request_json['text']
    subnarratives_context = request_json.get('subnarratives_context', "")
    try:
        result = call_llm(text_preview, subnarratives_context)
        
        # Attach source metadata
        result["source_url"] = request_json.get("source_url", "")
        result["original_title"] = request_json.get("title", "")
        
        return result, 200
    except Exception as e:
        logging.error(str(e))
        return {"error": "Synthesis failed", "details": str(e)}, 500
