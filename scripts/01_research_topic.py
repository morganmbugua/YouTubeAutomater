#!/usr/bin/env python3
"""
Step 1: Research Trending Topics
Uses Groq API (FREE — no billing required, 14,400 requests/day).
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

# Local cache — written every run, survives even when git commit fails
# This is the key to preventing repeats across runs
LOCAL_CACHE = Path("output/topics_cache.json")

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
                temperature=0.85
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
    strategy = {}
    if STRATEGY_FILE.exists():
        try:
            strategy = json.loads(STRATEGY_FILE.read_text())
        except Exception:
            pass

    # Merge local cache — it's more up-to-date than git-committed strategy.json
    if LOCAL_CACHE.exists():
        try:
            cache = json.loads(LOCAL_CACHE.read_text())
            cached_recent = cache.get("recent_topics", [])
            strat_recent  = strategy.get("recent_topics", [])
            # Use whichever list is longer (more topics tracked = fewer repeats)
            if len(cached_recent) > len(strat_recent):
                strategy["recent_topics"] = cached_recent
                print(f"   Using local cache: {len(cached_recent)} topics tracked")
        except Exception:
            pass

    # Ensure correct defaults — never fall back to old generic niches
    strategy.setdefault("content_mix", ["dark history", "true crime & conspiracies", "dark psychology",
                                         "shocking science & nature", "rise and fall stories", "survival & disaster"])
    strategy.setdefault("recent_topics", [])
    strategy.setdefault("avoid_topics", [])
    strategy.setdefault("best_posting_hours", [6, 9, 12, 15, 18, 21])
    strategy.setdefault("target_niches", ["dark history", "true crime", "dark psychology", "mystery", "survival"])
    return strategy

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

# ── Niche definitions ─────────────────────────────────────────────────────────

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

# ── Pick topic ────────────────────────────────────────────────────────────────

def pick_topic(strategy: dict, trending: list) -> dict:
    import datetime

    slot_int = int(SLOT)
    avoid    = strategy.get("avoid_topics", [])
    recent   = strategy.get("recent_topics", [])[-50:]

    # Rotate niche by slot number
    niche = NICHES[(slot_int - 1) % len(NICHES)]

    if FORCE_TOPIC:
        topic_instruction = f"The specific topic is: {FORCE_TOPIC}"
        niche_context = ""
    else:
        topic_instruction = f"Choose ONE specific, compelling topic in the '{niche['name']}' niche."
        date_seed = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        niche_context = f"""
Niche: {niche['description']}
Content angles to use: {', '.join(niche['content_types'])}
Uniqueness seed (use to pick a fresh angle): {date_seed}-slot{slot_int}

=== ALREADY COVERED — NEVER REPEAT ANY OF THESE ===
{chr(10).join(f'- {t}' for t in recent) if recent else '(none yet — pick anything good)'}

Also avoid entirely: {avoid if avoid else 'nothing specific'}
Trending YouTube titles (pulse check only, do not copy): {trending[:8]}

HARD REQUIREMENTS:
- Must be 100% different from every topic in the already-covered list
- Specific named event or person — not a category (e.g. "The 1986 Chernobyl Disaster" not "nuclear accidents")
- Real documented event preferred over hypotheticals  
- Strong story arc with a shocking or tragic resolution
- Broad global appeal"""

    prompt = f"""{topic_instruction}
{niche_context}

Pick the most compelling specific story for a viral dark-niche YouTube channel.

Respond ONLY with raw JSON, no markdown:
{{
  "topic": "specific topic name",
  "hook": "most shocking single fact about this topic",
  "search_query": "3-4 word image search",
  "image_queries": ["{niche['image_style']}", "{niche['image_style']} dark", "relevant image 1", "relevant image 2", "relevant image 3"],
  "content_type": "{niche['name']}",
  "niche": "{niche['name']}",
  "target_audience": "who watches this",
  "why_viral": "why this gets clicks",
  "seo_keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"]
}}"""

    extra_avoid = ""
    for attempt in range(4):
        full_prompt = prompt + extra_avoid
        raw = groq_call(full_prompt, max_tokens=700)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw.strip())

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            if attempt < 3:
                continue
            raise

        chosen       = result.get("topic", "")
        chosen_clean = chosen.lower().strip()

        # Check if this topic is too similar to a recent one
        is_repeat = any(
            chosen_clean in r.lower() or r.lower() in chosen_clean
            for r in recent
        )

        if not is_repeat:
            return result

        print(f"   ⚠️ Attempt {attempt+1}: '{chosen}' is a repeat — retrying…")
        extra_avoid += f"\nDO NOT pick '{chosen}' — already covered. Choose a completely different topic."

    print(f"   ⚠️ Could not avoid repeats after 4 attempts — proceeding")
    return result

# ── Save + update cache ───────────────────────────────────────────────────────

def update_strategy(strategy: dict, topic_data: dict):
    import datetime
    recent = strategy.get("recent_topics", [])
    topic  = topic_data["topic"]

    if topic not in recent:
        recent.append(topic)
    strategy["recent_topics"] = recent[-50:]
    STRATEGY_FILE.write_text(json.dumps(strategy, indent=2))

    # Write local cache — this survives even when git commit fails
    LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CACHE.write_text(json.dumps({
        "recent_topics": strategy["recent_topics"],
        "last_updated":  datetime.datetime.utcnow().isoformat() + "Z"
    }, indent=2))
    print(f"   Topics cache updated: {len(strategy['recent_topics'])} topics tracked")

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
