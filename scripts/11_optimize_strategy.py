#!/usr/bin/env python3
"""
Step 11: AI Strategy Optimizer
Reads recent performance data and asks Gemini to rewrite strategy.json
to improve content decisions. Runs daily via optimize_strategy.yml.
Uses Google Gemini 1.5 Flash — FREE tier.
"""

import os, json, datetime, urllib.request
from pathlib import Path

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
)

STRATEGY_FILE  = Path("scripts/strategy.json")
LOG_FILE       = Path("dashboard/data/run_log.json")
ANALYTICS_FILE = Path("dashboard/data/analytics.json")

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default

def gemini(prompt: str, max_tokens: int = 800) -> str:
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.5}
    }).encode()
    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()

def main():
    print("🧠 Running AI strategy optimizer…")

    strategy  = load_json(STRATEGY_FILE, {})
    log       = load_json(LOG_FILE, [])
    analytics = load_json(ANALYTICS_FILE, {})

    recent_log  = log[-42:]
    successes   = [e for e in recent_log if e.get("video_id")]
    topic_list  = [e.get("topic", "") for e in successes]

    prompt = f"""You are the strategy optimizer for an autonomous YouTube channel.

Current strategy:
{json.dumps(strategy, indent=2)}

Recent video topics (last 7 days):
{json.dumps(topic_list, indent=2)}

Analytics summary:
{json.dumps(analytics.get("data", {}).get("totals", analytics.get("data", {})), indent=2)}

Success rate: {len(successes)}/{len(recent_log)} videos uploaded successfully

Update the strategy to improve performance. Diversify content types if repetitive,
avoid recently covered topics, and optimize posting hours.

Respond ONLY with the updated strategy as a JSON object. No explanation, no markdown, no code fences:
{{
  "content_mix": ["type1", "type2", "type3", "type4", "type5", "type6"],
  "recent_topics": {json.dumps(topic_list[-20:])},
  "avoid_topics": [],
  "best_posting_hours": [9, 12, 15, 17, 20, 22],
  "target_niches": ["niche1", "niche2", "niche3", "niche4", "niche5"],
  "last_optimized": "{datetime.datetime.utcnow().isoformat()}Z"
}}
"""

    raw = gemini(prompt, max_tokens=800)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    new_strategy = json.loads(raw.strip())

    STRATEGY_FILE.write_text(json.dumps(new_strategy, indent=2))
    print("✅ Strategy updated:")
    print(f"   Content mix: {new_strategy.get('content_mix', [])}")
    print(f"   Posting hours: {new_strategy.get('best_posting_hours', [])}")

if __name__ == "__main__":
    main()
