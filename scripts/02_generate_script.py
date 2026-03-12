#!/usr/bin/env python3
"""
Step 2: Generate Video Script
Uses Groq API (FREE — no billing required).
Writes a full 700-900 word narration script + SEO metadata.
"""

import os, json, time, urllib.request, urllib.error
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

def groq(prompt: str, max_tokens: int = 2048) -> str:
    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.8
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

    raw = groq(prompt, max_tokens=2048)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"✍️ Generating script for slot {SLOT}: {topic_data['topic']}")
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
