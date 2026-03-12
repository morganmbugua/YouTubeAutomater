#!/usr/bin/env python3
"""
Step 1: Research Trending Topics
Uses Groq API (FREE — no billing required, 14,400 requests/day).
Sign up at console.groq.com → API Keys → Create API Key.
"""

import os, json, time, re, urllib.request, urllib.parse, urllib.error
from pathlib import Path

SLOT            = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR      = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY    = os.environ["GROQ_API_KEY"]
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
FORCE_TOPIC     = os.environ.get("FORCE_TOPIC", "").strip()
STRATEGY_FILE   = Path("scripts/strategy.json")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── Groq helper ───────────────────────────────────────────────────────────────

def groq_call(prompt: str, max_tokens: int = 1024) -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower():
                wait = 20 * (attempt + 1)
                print(f"   ⏳ Rate limited — waiting {wait}s (attempt {attempt+1}/5)…")
                import time; time.sleep(wait)
            else:
                raise
    raise RuntimeError("Groq API failed after 5 attempts")


# ── Load strategy ─────────────────────────────────────────────────────────────

def load_strategy() -> dict:
    if STRATEGY_FILE.exists():
        try:
            return json.loads(STRATEGY_FILE.read_text())
        except Exception:
            pass
    return {
        "content_mix": ["educational", "how-to", "news analysis", "top 10", "explainer", "documentary"],
        "recent_topics": [],
        "avoid_topics": [],
        "best_posting_hours": [9, 12, 15, 17, 20, 22],
        "target_niches": ["technology", "science", "history", "business", "health & wellness"]
    }

# ── Fetch YouTube trending ────────────────────────────────────────────────────

def fetch_youtube_trending() -> list:
    if not YOUTUBE_API_KEY:
        return []
    try:
        params = urllib.parse.urlencode({
            "part": "snippet", "chart": "mostPopular",
            "regionCode": "US", "maxResults": "20", "key": YOUTUBE_API_KEY
        })
        with urllib.request.urlopen(
            f"https://www.googleapis.com/youtube/v3/videos?{params}", timeout=15
        ) as r:
            data = json.loads(r.read())
        titles = [item["snippet"]["title"] for item in data.get("items", [])]
        print(f"   Fetched {len(titles)} trending titles")
        return titles
    except Exception as e:
        print(f"   ⚠️ Trending fetch failed: {e}")
        return []

# ── Pick topic ────────────────────────────────────────────────────────────────

def pick_topic(strategy: dict, trending: list) -> dict:
    slot_int      = int(SLOT)
    content_types = strategy.get("content_mix", ["educational", "how-to", "top 10"])
    content_type  = content_types[(slot_int - 1) % len(content_types)]
    avoid         = strategy.get("avoid_topics", [])
    recent        = strategy.get("recent_topics", [])[-10:]

    if FORCE_TOPIC:
        topic_instruction = f"The topic is: {FORCE_TOPIC}"
    else:
        topic_instruction = (
            f"Choose the single best topic for a '{content_type}' YouTube video. "
            f"Recent topics to avoid repeating: {recent}. "
            f"Topics to avoid entirely: {avoid}. "
            f"YouTube trending titles for context: {trending[:10]}."
        )

    prompt = f"""{topic_instruction}

Respond ONLY with a JSON object. No explanation, no markdown, no code fences — raw JSON only:
{{
  "topic": "exact video topic title",
  "search_query": "3-5 word search query for finding images",
  "image_queries": ["query1", "query2", "query3", "query4", "query5"],
  "content_type": "{content_type}",
  "target_audience": "who would watch this",
  "why_trending": "one sentence on why this topic works now",
  "seo_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""

    raw = groq_call(prompt, max_tokens=600)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
    return json.loads(raw)

# ── Update strategy ───────────────────────────────────────────────────────────

def update_strategy(strategy: dict, topic_data: dict):
    recent = strategy.get("recent_topics", [])
    recent.append(topic_data["topic"])
    strategy["recent_topics"] = recent[-30:]
    STRATEGY_FILE.write_text(json.dumps(strategy, indent=2))

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🔍 Researching topic for slot {SLOT}…")
    strategy   = load_strategy()
    trending   = fetch_youtube_trending()
    topic_data = pick_topic(strategy, trending)

    print(f"   Topic: {topic_data['topic']}")
    print(f"   Type:  {topic_data['content_type']}")

    topic_path = OUTPUT_DIR / "topic.json"
    topic_path.write_text(json.dumps(topic_data, indent=2))
    update_strategy(strategy, topic_data)

    topic_json = json.dumps(topic_data)
    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"topic_data={topic_json}\n")
        f.write(f"topic_path={topic_path}\n")

    print(f"✅ Topic saved: {topic_path}")

if __name__ == "__main__":
    main()
