#!/usr/bin/env python3
"""
Step 3: Generate Voiceover (Free)
Uses gTTS (Google Text-to-Speech) — completely free, no API key needed.
Also generates an SRT subtitle file timed to the audio.
"""

import os, json, subprocess
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

script_path = os.environ.get("SCRIPT_PATH", str(OUTPUT_DIR / "script.json"))
script_data = json.loads(Path(script_path).read_text())
narration   = script_data["narration"]

# ── gTTS ──────────────────────────────────────────────────────────────────────

def generate_voice(text: str, output_path: Path) -> bool:
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(str(output_path))
        print(f"   ✅ gTTS audio saved: {output_path.stat().st_size // 1024}KB")
        return True
    except Exception as e:
        raise RuntimeError(f"gTTS failed: {e}. Is gTTS installed? (pip install gTTS)")

# ── Audio duration via ffprobe ────────────────────────────────────────────────

def get_audio_duration(audio_path: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        # Estimate from word count: ~140 words/minute
        return (len(narration.split()) / 140) * 60

# ── Generate SRT subtitles ────────────────────────────────────────────────────

def generate_srt(narration: str, duration_seconds: float, srt_path: Path):
    words      = narration.split()
    chunk_size = 8
    chunks     = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    if not chunks:
        srt_path.write_text("")
        return

    time_per_chunk = duration_seconds / len(chunks)

    def fmt(s: float) -> str:
        h = int(s // 3600); m = int((s % 3600) // 60)
        sec = int(s % 60);  ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    lines = []
    for i, chunk in enumerate(chunks):
        start = i * time_per_chunk
        end   = start + time_per_chunk - 0.1
        lines += [str(i+1), f"{fmt(start)} --> {fmt(end)}", chunk, ""]

    srt_path.write_text("\n".join(lines))
    print(f"   SRT: {len(chunks)} subtitle entries")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🎙️ Generating voiceover for slot {SLOT}…")
    print(f"   Narration: {len(narration.split())} words")

    voice_path = OUTPUT_DIR / "voiceover.mp3"
    generate_voice(narration, voice_path)

    duration = get_audio_duration(voice_path)
    print(f"   Duration: {duration:.1f}s")

    srt_path = OUTPUT_DIR / "subtitles.srt"
    generate_srt(narration, duration, srt_path)

    (OUTPUT_DIR / "audio_meta.json").write_text(
        json.dumps({"duration_seconds": duration, "word_count": len(narration.split())})
    )

    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"voice_path={voice_path}\n")
        f.write(f"srt_path={srt_path}\n")

    print("✅ Voice + subtitles ready")

if __name__ == "__main__":
    main()
