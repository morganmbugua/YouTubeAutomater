#!/usr/bin/env python3
"""
Step 11: AI Strategy Optimizer
Uses Groq API (FREE) to review performance and rewrite strategy.json daily.
"""

import os, json, datetime, time, urllib.request, urllib.error
from pathlib import Path

GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"

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

def groq(prompt: str, max_tokens: int = 800) -> str:
    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.5
    }).encode()
    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"   HTTP {e.code}: {body[:300]}")
            if e.code in (429, 503):
                wait = 20 * (attempt + 1)
                print(f"   ⏳ Waiting {wait}s (attempt {attempt+1}/5)…")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < 4:
                time.sleep(10)
            else:
                raise
    raise RuntimeError("Groq API failed after 5 attempts")

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
}}"""

    raw = groq(prompt, max_tokens=800)
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
