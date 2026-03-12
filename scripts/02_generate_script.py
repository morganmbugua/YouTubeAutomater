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
    topic        = topic_data["topic"]
    content_type = topic_data.get("content_type", "educational")
    audience     = topic_data.get("target_audience", "general audience")
    keywords     = topic_data.get("seo_keywords", [])

    hook        = topic_data.get("hook", "")
    niche       = topic_data.get("niche", content_type)
    why_viral   = topic_data.get("why_viral", "")

    prompt = f"""You are writing a script for a faceless YouTube channel in the "{niche}" niche.
The channel gets millions of views because it tells stories that make people feel something — shock, dread, fascination, disbelief.

Topic: "{topic}"
Hook angle: {hook}
Why this works: {why_viral}
Target audience: {audience}
SEO keywords to weave in naturally: {", ".join(keywords)}

WRITING STYLE — study this and copy it exactly:
- Open with the most shocking or intriguing fact. Drop the viewer straight into it. No "welcome back" intros.
- Write like you're telling a story to a friend at 2am — conversational, direct, slightly conspiratorial
- Use short punchy sentences when building tension. Longer sentences to explain context.
- Every paragraph should end making the listener want to hear the next one
- Use phrases like "But here's where it gets dark.", "Nobody talks about this part.", "What happened next shocked everyone.", "And this is where it gets complicated."
- Include specific real details — dates, numbers, names, places. Specificity = credibility = trust
- Build to a climax. The last third should feel like a payoff for listening
- No bullet points. No headers. No stage directions. Just the words spoken, as one flowing story.

STRUCTURE (do not label these in the text — just follow the flow):
1. COLD OPEN (first 30 seconds): Drop the most shocking fact or moment. Make them need to keep watching.
2. SETUP (60s): Brief context — who, what, where, when. Keep it tight.
3. ESCALATION x3 (90s each): Three acts that build tension. Each one darker or more shocking than the last.
4. CLIMAX (60s): The most dramatic moment. What actually happened.
5. AFTERMATH (45s): Consequences, legacy, what it means today.
6. CLOSE (15s): One punchy final thought + "subscribe if you want more stories like this"

WORD COUNT: 750-900 words minimum. Count carefully — this is non-negotiable.

Respond ONLY with a JSON object. No explanation, no markdown, no code fences — raw JSON only:
{{
  "topic": "{topic}",
  "title": "YouTube title — curiosity-gap style, 60 chars max (e.g. 'The Experiment That Went Terribly Wrong')",
  "description": "YouTube description — 150 words, starts with a hook, keyword-rich, ends with subscribe CTA",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "narration": "Full spoken script, 750+ words, no stage directions, no headers, pure flowing story",
  "sections": [
    {{"title": "Section name", "duration_seconds": 60, "summary": "what this covers"}}
  ],
  "hook": "The first 2 sentences of the script",
  "cta": "The final sentence"
}}"""

    raw = groq_call(prompt, max_tokens=4096)

    # Strip markdown fences
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # Fix invalid control characters (newlines/tabs inside JSON string values)
    # Replace literal newlines inside strings with \n escape
    import re
    # Remove control characters except standard whitespace between tokens
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)

    # Try parsing; if it fails, extract fields individually
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract narration with a more lenient approach
        # Ask the model to just return the narration as plain text
        print("   ⚠️ JSON parse failed — extracting narration directly…")
        narration_prompt = f"""Write ONLY the spoken narration for a YouTube video about: "{topic}"
Niche: dark storytelling — shocking, gripping, hook-first.
No JSON, no formatting, no stage directions, no headers. Just the words spoken out loud.
MINIMUM 800 WORDS. Start with the most shocking fact immediately."""
        narration_text = groq_call(narration_prompt, max_tokens=4096)

        title_prompt = f'Curiosity-gap YouTube title for: "{topic}". Max 60 chars. Reply with ONLY the title, no quotes.'
        title = groq_call(title_prompt, max_tokens=50).strip().strip('"')

        result = {
            "topic": topic,
            "title": title[:100],
            "description": f"The dark, untold story of {topic}. Subscribe for more.",
            "tags": keywords[:10],
            "narration": narration_text,
            "sections": [],
            "hook": narration_text[:200],
            "cta": "Subscribe for more stories like this."
        }

    word_count = len(result.get("narration", "").split())
    if word_count < 600:
        raise ValueError(f"Narration too short: {word_count} words. Retrying…")
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
