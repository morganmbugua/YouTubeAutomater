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


# ── Generate script ───────────────────────────────────────────────────────────

def generate_script(topic_data: dict) -> dict:
    topic        = topic_data["topic"]
    content_type = topic_data.get("content_type", "educational")
    audience     = topic_data.get("target_audience", "general audience")
    keywords     = topic_data.get("seo_keywords", [])

    prompt = f"""Write a complete YouTube video script for: "{topic}"
Content type: {content_type}
Target audience: {audience}
SEO keywords to include naturally: {", ".join(keywords)}

CRITICAL REQUIREMENT: The "narration" field MUST be at least 700 words. Count carefully.
Write a FULL, DETAILED script — 700 to 900 words of spoken narration (about 5-6 minutes of video).
Do NOT write a summary or outline. Write every single word the presenter will say.
Write in a conversational, engaging style. No bullet points — flowing spoken sentences only.
Structure: Hook (20s) → Introduction (60s) → 4 main sections (60-90s each) → Conclusion + CTA (30s).
Each section must be several full paragraphs. Be thorough and detailed.

Respond ONLY with a JSON object. No explanation, no markdown, no code fences — raw JSON only:
{{
  "topic": "{topic}",
  "title": "YouTube video title (60 chars max)",
  "description": "YouTube description (200 words, keyword-rich)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "narration": "Full script text. Just the words to be spoken, no stage directions.",
  "sections": [
    {{"title": "Section name", "duration_seconds": 60, "summary": "what this covers"}}
  ],
  "hook": "First 2 sentences of the script",
  "cta": "Last sentence — call to action"
}}"""

    raw = groq_call(prompt, max_tokens=4096)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    word_count = len(result.get("narration", "").split())
    if word_count < 300:
        raise ValueError(f"Narration too short: {word_count} words. AI did not follow instructions.")
    return result

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
