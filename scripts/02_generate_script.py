#!/usr/bin/env python3
"""
Step 2: Generate Video Script
Uses Groq API (FREE — no billing required).
Writes a full 700-900 word narration script + SEO metadata.
"""

import os, json, time
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Load topic
topic_json = os.environ.get("TOPIC_DATA", "")
if topic_json:
    topic_data = json.loads(topic_json)
else:
    topic_data = json.loads((OUTPUT_DIR / "topic.json").read_text())

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


# ── Generate script ───────────────────────────────────────────────────────────

def generate_script(topic_data: dict) -> dict:
    topic      = topic_data["topic"]
    audience   = topic_data.get("target_audience", "general audience")
    keywords   = topic_data.get("seo_keywords", [])
    hook       = topic_data.get("hook", "")
    niche      = topic_data.get("niche", topic_data.get("content_type", "trending news"))
    why_viral  = topic_data.get("why_viral", "")

    # ── Call 1: Narration only (plain text, no JSON overhead) ─────────────────
    narration_prompt = f"""You are writing for a faceless YouTube channel in the "{niche}" niche.
Topic: "{topic}"
Hook angle: {hook}
Why this works: {why_viral}
Audience: {audience}
Weave in these keywords naturally: {", ".join(keywords)}

WRITING RULES:
- Open with the single most shocking or disturbing fact. No intro. No "welcome back."
- Write like you're telling a story to a friend at 2am — direct, gripping, slightly conspiratorial
- Short punchy sentences for tension. Longer ones for context.
- End every paragraph making the listener need to hear the next one
- Use phrases like: "But here's where it gets dark." / "Nobody talks about this part." / "And this is where everything fell apart."
- Specific real details only — exact dates, real names, actual numbers. No vague generalities.
- Build to a climax. The ending must feel like a payoff.
- No bullet points. No headers. No stage directions. Pure flowing spoken story.

STRUCTURE (follow the flow, don't label sections):
1. Cold open: most shocking moment (30s)
2. Setup: who, what, where, when — keep tight (60s)
3. Three escalating acts — each darker than the last (90s each)
4. Climax: the most dramatic moment (60s)
5. Aftermath: consequences and legacy (45s)
6. Close: one punchy final line + "subscribe for more stories like this" (15s)

Write the full narration now. Plain text only. No JSON. No formatting. Minimum 800 words."""

    narration = groq_call(narration_prompt, max_tokens=4096).strip()

    # Strip any accidental formatting
    import re
    narration = re.sub(r'\*+([^*]+)\*+', r'\1', narration)
    narration = re.sub(r'#{1,6}\s+', '', narration)
    narration = re.sub(r'^\s*[\-\•]\s+', '', narration, flags=re.MULTILINE)

    word_count = len(narration.split())
    print(f"   Narration: {word_count} words")
    if word_count < 600:
        raise ValueError(f"Narration too short: {word_count} words.")

    # ── Call 2: Metadata only (small JSON, no narration inside) ──────────────
    meta_prompt = f"""For a YouTube video about "{topic}" in the "{niche}" niche, give me the metadata.

Respond ONLY with raw JSON, no markdown, no explanation:
{{
  "title": "curiosity-gap title, max 60 chars, e.g. The Experiment That Destroyed Everything",
  "description": "150 word YouTube description — hook first sentence, keyword-rich, ends with subscribe CTA",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "hook": "first 2 sentences of the story",
  "cta": "final sentence of the story"
}}"""

    meta_raw = groq_call(meta_prompt, max_tokens=600)
    if "```" in meta_raw:
        meta_raw = meta_raw.split("```")[1]
        if meta_raw.startswith("json"):
            meta_raw = meta_raw[4:]
    meta_raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', meta_raw.strip())

    try:
        meta = json.loads(meta_raw)
    except json.JSONDecodeError:
        # Metadata failure is non-fatal — build defaults
        meta = {
            "title": topic[:60],
            "description": f"The untold story of {topic}. Subscribe for more.",
            "tags": keywords[:10],
            "hook": narration[:150],
            "cta": "Subscribe for more stories like this."
        }

    return {
        "topic":       topic,
        "title":       meta.get("title", topic)[:100],
        "description": meta.get("description", f"The story of {topic}."),
        "tags":        meta.get("tags", keywords[:10]),
        "narration":   narration,
        "sections":    [],
        "hook":        meta.get("hook", narration[:150]),
        "cta":         meta.get("cta", "Subscribe for more stories like this.")
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"✍️ Generating script for slot {SLOT}: {topic_data['topic']}")
    for attempt in range(3):
        try:
            script_data = generate_script(topic_data)
            break
        except (ValueError, Exception) as e:
            print(f"   ⚠️ Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                raise
            time.sleep(5)

    script_path = OUTPUT_DIR / "script.json"
    script_path.write_text(json.dumps(script_data, indent=2))

    narration_path = OUTPUT_DIR / "narration.txt"
    narration_path.write_text(script_data["narration"])

    print(f"   Title: {script_data['title']}")
    print(f"   Narration: {len(script_data['narration'].split())} words")

    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"script_path={script_path}\n")
        f.write(f"narration_path={narration_path}\n")

    print(f"✅ Script saved: {script_path}")

if __name__ == "__main__":
    main()
