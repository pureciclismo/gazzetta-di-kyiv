#!/usr/bin/env python3
"""
newsletter_prompts.py — DeepSeek prompt templates for newsletter intelligence extraction.

Separated from fetch_newsletters.py for easy tuning without touching fetch logic.
"""

# The system-level instruction for DeepSeek
SYSTEM_PROMPT = """You are an intelligence extraction engine for La Gazzetta di Kyiv,
a geopolitical and macroeconomic analysis publication. Your role is to extract
structured intelligence from newsletter emails.

You are rigorous, precise, and focused on information that has geopolitical,
macroeconomic, or financial significance. You do NOT summarize marketing fluff,
product promotions, or editorial opinions unless they signal a broader trend.

Always respond with valid JSON only — no markdown fences, no commentary."""


def build_extraction_prompt(subject: str, sender_name: str, body_text: str, narratives: list[str]) -> str:
    """Build the extraction prompt for a single newsletter."""

    narrative_list = "\n".join(f"  - {n}" for n in narratives)

    return f"""Extract structured intelligence from this newsletter email.

SENDER: {sender_name}
SUBJECT: {subject}

BODY:
{body_text[:8000]}

ACTIVE NARRATIVES TO MATCH AGAINST:
{narrative_list}

Return a JSON object with exactly these fields:

{{
  "summary": "2-3 sentence summary of the main intelligence value",
  "bullets": ["key point 1", "key point 2", "key point 3"],
  "topics": ["topic1", "topic2"],
  "narrative_matches": ["narrative_id_if_matched"],
  "links": [
    {{"url": "https://...", "context": "why this link matters"}}
  ],
  "data_points": [
    {{"stat": "exact quoted statistic or number", "source": "attribution if given"}}
  ],
  "value_score": 7,
  "value_score_reason": "one sentence explaining the score",
  "is_newsletter": true,
  "language": "en"
}}

SCORING GUIDE for value_score (1-10):
  9-10: Contains hard data, breaking developments, or signals on active narratives
  7-8:  Useful context, trend confirmation, or relevant analysis
  5-6:  General background, soft signals, or mixed relevance
  3-4:  Mostly opinion, anecdote, or light coverage
  1-2:  Marketing, promotions, or zero intelligence value

NARRATIVE MATCHING: Only include a narrative in narrative_matches if the content
directly addresses it. Use the exact narrative ID strings provided above."""


def build_batch_prompt(items: list[dict]) -> list[dict]:
    """
    Build a list of messages for batch processing.
    Each item: {subject, sender_name, body_text}
    Returns list of {role, content} dicts.
    """
    messages = []
    for i, item in enumerate(items):
        messages.append({
            "role": "user",
            "content": f"[Newsletter {i+1}] FROM: {item['sender_name']} | SUBJECT: {item['subject']}\n\n{item['body_text'][:4000]}"
        })
    return messages


NEWSLETTER_DETECTION_PROMPT = """Is this email a newsletter or bulk mailing?
Reply with JSON: {{"is_newsletter": true/false, "confidence": 0.0-1.0, "reason": "..."}}

Subject: {subject}
From: {sender}
Has List-Unsubscribe header: {has_unsubscribe}
Body preview: {body_preview}"""
