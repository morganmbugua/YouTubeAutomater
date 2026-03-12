#!/usr/bin/env python3
"""
Step 3: Generate Voiceover (Free)
Uses gTTS (Google Text-to-Speech) — completely free, no API key needed.
Also generates an SRT subtitle file timed to the audio.
"""

import os, json, subprocess, re
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

script_path = os.environ.get("SCRIPT_PATH", str(OUTPUT_DIR / "script.json"))
script_data = json.loads(Path(script_path).read_text())
narration   = script_data["narration"]

# ── Text pre-processing for natural TTS flow ──────────────────────────────────

def clean_for_tts(text: str) -> str:
    """
    Pre-process narration so gTTS reads naturally without odd pauses.
    """
    # Remove stage directions like (pause) or [music] or *emphasis*
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\*+([^*]+)\*+', r'\1', text)

    # Remove markdown formatting
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # Replace dashes used as pauses with commas (gTTS pauses too long on em-dash)
    text = re.sub(r'\s*—\s*', ', ', text)
    text = re.sub(r'\s*--\s*', ', ', text)

    # Remove ellipsis (causes long unnatural pauses)
    text = re.sub(r'\.{2,}', '.', text)

    # Replace semicolons with commas — gTTS over-pauses on semicolons
    text = text.replace(';', ',')

    # Replace colons mid-sentence with commas (keep natural flow)
    # But only when not at end of line (e.g. "Here's what we know: it works")
    text = re.sub(r':(?!\n)', ',', text)

    # Remove bullet points / numbering that slipped through
    text = re.sub(r'^\s*[\-\•\*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+[\.\)]\s+', '', text, flags=re.MULTILINE)

    # Collapse multiple spaces/newlines into single space
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r' {2,}', ' ', text)

    # Remove any leftover special characters that confuse TTS
    text = re.sub(r'[^\w\s\.,!?\'\"()-]', '', text)

    return text.strip()


def split_sentences(text: str) -> list:
    """Split into natural sentence chunks for smoother TTS — no choppy mid-sentence breaks."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    merged, buffer = [], ""
    for s in sentences:
        buffer = (buffer + " " + s).strip() if buffer else s
        if len(buffer.split()) >= 15:
            merged.append(buffer)
            buffer = ""
    if buffer:
        merged.append(buffer)
    return [s for s in merged if s.strip()]


def generate_voice(text: str, output_path: Path) -> bool:
    try:
        from gtts import gTTS
        import shutil

        cleaned   = clean_for_tts(text)
        sentences = split_sentences(cleaned)
        print(f"   Generating TTS in {len(sentences)} sentence chunks…")

        tmp_dir = output_path.parent / "tts_chunks"
        tmp_dir.mkdir(exist_ok=True)

        chunk_files = []
        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            chunk_path = tmp_dir / f"chunk_{i:03d}.mp3"
            gTTS(text=sentence.strip(), lang="en", slow=False).save(str(chunk_path))
            chunk_files.append(chunk_path)

        if not chunk_files:
            raise RuntimeError("No audio chunks generated")

        # Concatenate chunks
        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text("\n".join(f"file '{p.resolve()}'" for p in chunk_files))
        result = subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c:a", "copy", str(output_path)
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print("   ⚠️ Chunk concat failed — falling back to single-pass TTS")
            gTTS(text=cleaned, lang="en", slow=False).save(str(output_path))

        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        print(f"   ✅ gTTS audio saved: {output_path.stat().st_size // 1024}KB")

        # Slight speed-up — removes the robotic slowness without sounding rushed
        sped_path = output_path.with_suffix(".sped.mp3")
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(output_path),
            "-filter:a", "atempo=1.1", "-q:a", "2", str(sped_path)
        ], capture_output=True, text=True)
        if result.returncode == 0 and sped_path.exists():
            sped_path.replace(output_path)
            print(f"   ✅ Speed adjusted (atempo=1.1)")
        return True
    except Exception as e:
        raise RuntimeError(f"gTTS failed: {e}")

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
