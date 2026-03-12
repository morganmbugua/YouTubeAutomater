#!/usr/bin/env python3
"""
Step 2: Generate Video Script
Uses Google Gemini 1.5 Flash (FREE) to write a full video script with SEO metadata.
Outputs: script.json with narration text, title, description, tags.
"""

import os, json, time, urllib.request, urllib.error
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-lite:generateContent?key=" + GEMINI_API_KEY
)

# Load topic
topic_json = os.environ.get("TOPIC_DATA", "")
if topic_json:
    topic_data = json.loads(topic_json)
else:
    topic_data = json.loads((OUTPUT_DIR / "topic.json").read_text())

# ── Gemini helper ─────────────────────────────────────────────────────────────

def gemini(prompt: str, max_tokens: int = 3000) -> str:
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8}
    }).encode()
    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()

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

The script should be 700-900 words of spoken narration — about 5-6 minutes of video.
Write in a conversational, engaging style. No bullet points — flowing spoken sentences only.
Structure: Hook (20s) → Introduction → 4-5 main sections → Conclusion + CTA.

Also write the YouTube metadata.

Respond ONLY with a JSON object. No explanation, no markdown, no code fences — raw JSON only:
{{
  "topic": "{topic}",
  "title": "YouTube video title (60 chars max, include main keyword)",
  "description": "YouTube description (250 words, keyword-rich, include timestamps placeholder)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "narration": "Full script text here. Just the words to be spoken, no stage directions.",
  "sections": [
    {{"title": "Section name", "duration_seconds": 60, "summary": "what this section covers"}}
  ],
  "hook": "First 2 sentences of the script — the attention grabber",
  "cta": "Last sentence — call to action for likes and subscribe"
}}
"""
    raw = gemini(prompt, max_tokens=3000)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"✍️ Generating script for slot {SLOT}: {topic_data['topic']}")
    stagger = (int(SLOT) - 1) * 15
    if stagger > 0:
        print(f"   Staggering {stagger}s to avoid rate limits…")
        time.sleep(stagger)
    script_data = generate_script(topic_data)

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
