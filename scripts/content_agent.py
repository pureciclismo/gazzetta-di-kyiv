import json
from google_antigravity import Agent, LocalAgentConfig

def main():
    # 1. Initialize configuration for the Antigravity Agent
    # We use gemini-2.5-pro for complex content generation and reasoning.
    config = LocalAgentConfig(
        model="gemini-2.5-pro",
        system_instruction=(
            "You are an elite geopolitical and macroeconomic intelligence agent for La Gazzetta di Kyiv. "
            "Your task is to continuously synthesize raw news events into structured 'Signals'. "
            "You focus exclusively on two macro narratives: 'European Sovereignty' and 'Global Realignment'. "
            "For every piece of raw data provided by the pipeline, output a JSON object representing a Signal. "
            "The JSON must include: headline, slug, they_say (consensus view), reality (capital flow view), "
            "narrative_id (european_sovereignty or global_realignment), and affected_tickers."
        ),
        # Assuming environment variable GEMINI_API_KEY is set by the user or pipeline runner
    )
    
    # 2. Instantiate the Agent
    try:
        agent = Agent(config)
    except Exception as e:
        print("Failed to initialize Agent. Ensure GEMINI_API_KEY is set in your environment.")
        print(f"Error: {e}")
        return

    print("Agent initialized. Ready to process news pipeline...")

    # Simulated raw news feed input
    raw_news = [
        "The ECB announced today that European banks must increase their sovereign debt holdings of local states.",
        "China and Saudi Arabia have signed a new $50B currency swap agreement bypassing the US Dollar."
    ]

    # 3. Agent Execution Loop
    for news in raw_news:
        print(f"Processing raw news: {news}")
        try:
            # We enforce JSON output using a prompt directive.
            response = agent.run(f"Process this event into a JSON Signal: {news}")
            print("Generated Signal:", response.text)
        except Exception as e:
            print(f"Agent failed to process news: {e}")

if __name__ == "__main__":
    main()
