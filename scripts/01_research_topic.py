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
                model="llama-3.3-70b-versatile",
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

# ── Niche definition ──────────────────────────────────────────────────────────
# These are the highest-performing faceless YouTube niches.
# Focused niche = algorithm recommends to the right audience = faster growth.

NICHES = [
    {
        "name": "dark history",
        "description": "Shocking, disturbing or little-known historical events. Wars, atrocities, conspiracies, fallen empires.",
        "content_types": ["untold story", "the dark truth about", "what they don't teach you", "the real story of"],
        "image_style": "historical war battle ruins soldiers"
    },
    {
        "name": "true crime & conspiracies",
        "description": "Famous crimes, unsolved mysteries, government cover-ups, conspiracy theories with evidence.",
        "content_types": ["the mystery of", "what really happened to", "the cover-up of", "conspiracy exposed"],
        "image_style": "crime investigation mystery dark"
    },
    {
        "name": "dark psychology",
        "description": "Manipulation tactics, cult psychology, how propaganda works, psychological warfare, narcissism.",
        "content_types": ["how manipulators think", "psychological tricks", "the psychology of", "how cults work"],
        "image_style": "psychology mind brain manipulation"
    },
    {
        "name": "shocking science & nature",
        "description": "Extreme natural phenomena, bizarre animal behavior, space horrors, extinction events.",
        "content_types": ["the most extreme", "scientists discovered", "what lives in", "this shouldn't exist"],
        "image_style": "nature science space extreme"
    },
    {
        "name": "rise and fall stories",
        "description": "How empires, companies, celebrities or movements rose to power then collapsed spectacularly.",
        "content_types": ["the rise and fall of", "how they destroyed", "the collapse of", "why they failed"],
        "image_style": "empire collapse ruins powerful"
    },
    {
        "name": "survival & disaster",
        "description": "Real survival stories, natural disasters, plane crashes, war survival, extreme human endurance.",
        "content_types": ["how they survived", "the disaster that", "stuck for", "against all odds"],
        "image_style": "disaster survival extreme conditions"
    },
]


def pick_topic(strategy: dict, trending: list) -> dict:
    import random
    slot_int = int(SLOT)
    avoid    = strategy.get("avoid_topics", [])
    recent   = strategy.get("recent_topics", [])[-15:]

    # Rotate through niches by slot so we don't repeat the same niche daily
    niche = NICHES[(slot_int - 1) % len(NICHES)]

    if FORCE_TOPIC:
        topic_instruction = f"The specific topic is: {FORCE_TOPIC}"
        niche_context = ""
    else:
        topic_instruction = f"Choose ONE specific, compelling topic in the '{niche['name']}' niche."
        niche_context = f"""
Niche description: {niche['description']}
Good content angles for this niche: {', '.join(niche['content_types'])}
Topics to avoid (already covered): {recent}
Topics to avoid entirely: {avoid}
Trending YouTube titles for inspiration (don't copy, use as pulse check): {trending[:8]}

REQUIREMENTS for a good topic:
- Specific, not vague. "The Jonestown Massacre" not "a cult story"
- Creates curiosity or shock. The viewer must NEED to know what happens.
- Has a clear narrative arc — beginning, escalation, shocking conclusion
- Real events preferred over hypotheticals
- Avoid overly political or divisive current events"""

    prompt = f"""{topic_instruction}
{niche_context}

You are picking topics for a faceless YouTube channel that gets millions of views.
Think: what would make someone stop scrolling and click?

Respond ONLY with a JSON object. No explanation, no markdown, no code fences:
{{
  "topic": "specific compelling topic title",
  "hook": "one sentence that would make someone STOP scrolling — the most shocking or intriguing fact about this topic",
  "search_query": "3-4 word image search query",
  "image_queries": ["{niche['image_style']} 1", "{niche['image_style']} 2", "topic specific image 1", "topic specific image 2", "topic specific image 3"],
  "content_type": "{niche['name']}",
  "niche": "{niche['name']}",
  "target_audience": "who watches this type of content",
  "why_viral": "one sentence on why this topic will get clicks",
  "seo_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""

    raw = groq_call(prompt, max_tokens=700)
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
