#!/usr/bin/env python3
"""
Step 5: Assemble Final Video
Builds a documentary/explainer style video:
  - Ken Burns (pan+zoom) effect on each image
  - Crossfade transitions between images
  - Burned-in subtitles
  - Voiceover audio
  - Branded intro (3s) and outro (5s)
  - Auto-clips a 60s YouTube Shorts version

All video is 1920x1080 @ 30fps, H.264, AAC audio.
"""

import os, json, math, subprocess, shutil, tempfile
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load inputs
script_path = os.environ.get("SCRIPT_PATH", str(OUTPUT_DIR / "script.json"))
script_data = json.loads(Path(script_path).read_text())

voice_path   = os.environ.get("VOICE_PATH", str(OUTPUT_DIR / "voiceover.mp3"))
srt_path     = os.environ.get("SRT_PATH", str(OUTPUT_DIR / "subtitles.srt"))
images_meta  = json.loads((OUTPUT_DIR / "images_meta.json").read_text())
image_paths  = images_meta["paths"]

audio_meta_path = OUTPUT_DIR / "audio_meta.json"
if audio_meta_path.exists():
    audio_meta = json.loads(audio_meta_path.read_text())
    total_duration = audio_meta["duration_seconds"]
else:
    # Measure with ffprobe
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", voice_path],
        capture_output=True, text=True
    )
    total_duration = float(r.stdout.strip())

WORK_DIR = OUTPUT_DIR / "work"
WORK_DIR.mkdir(exist_ok=True)

# ── Build Ken Burns slideshow ─────────────────────────────────────────────────

def build_slideshow(image_paths: list[str], duration: float) -> Path:
    """
    Create a video from images with Ken Burns effect.
    Each image gets equal time. Uses ffmpeg's zoompan filter.
    Returns path to the raw slideshow MP4 (no audio, no subtitles).
    """
    n          = len(image_paths)
    # Each image displays for this many seconds (minus 0.5s crossfade overlap)
    img_dur    = duration / n
    fps        = 30
    frames_per = int(img_dur * fps)

    print(f"   Building slideshow: {n} images × {img_dur:.1f}s = {duration:.0f}s")

    # Build a concat file. Each image is processed with zoompan then concat'd.
    # Strategy: process each image into a short clip, then concatenate.

    clip_paths = []
    directions = ["zoom_in", "zoom_out", "pan_right", "pan_left", "pan_up"]

    for i, img_path in enumerate(image_paths):
        clip_path = WORK_DIR / f"clip_{i:03d}.mp4"
        direction = directions[i % len(directions)]

        # zoompan: z=zoom, x/y=pan position
        # All start/end at slightly different positions for variety
        if direction == "zoom_in":
            zp = f"zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames_per}:s=1920x1080:fps={fps}"
        elif direction == "zoom_out":
            zp = f"zoompan=z='if(lte(zoom,1.0),1.5,max(1.0,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames_per}:s=1920x1080:fps={fps}"
        elif direction == "pan_right":
            zp = f"zoompan=z=1.3:x='min(x+1,iw/4)':y='ih/2-(ih/zoom/2)':d={frames_per}:s=1920x1080:fps={fps}"
        elif direction == "pan_left":
            zp = f"zoompan=z=1.3:x='max(x-1,0)':y='ih/2-(ih/zoom/2)':d={frames_per}:s=1920x1080:fps={fps}"
        else:  # pan_up
            zp = f"zoompan=z=1.3:x='iw/2-(iw/zoom/2)':y='min(y+1,ih/4)':d={frames_per}:s=1920x1080:fps={fps}"

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-vf", f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,{zp}",
            "-t", str(img_dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(clip_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not clip_path.exists():
            print(f"   ⚠️ Clip {i} failed — using plain scale fallback")
            # Simpler fallback without zoompan
            cmd_simple = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_path,
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                "-t", str(img_dur),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(clip_path)
            ]
            subprocess.run(cmd_simple, capture_output=True)

        if clip_path.exists():
            clip_paths.append(clip_path)

    # Write concat list
    concat_list = WORK_DIR / "concat.txt"
    with open(concat_list, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{cp.resolve()}'\n")

    slideshow_path = WORK_DIR / "slideshow_raw.mp4"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(slideshow_path)
    ]
    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Slideshow concat failed:\n{result.stderr[-500:]}")

    print(f"   Slideshow assembled: {slideshow_path}")
    return slideshow_path

# ── Build intro card ──────────────────────────────────────────────────────────

def build_intro(title: str, duration: float = 3.0) -> Path:
    intro_path = WORK_DIR / "intro.mp4"
    title_safe = title.replace("'", "\\'").replace(":", "\\:").replace('"', '\\"')[:50]
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x1a1a2e:size=1920x1080:rate=30:duration={duration}",
        "-vf", (
            f"drawtext=text='{title_safe}':"
            f"fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"font=DejaVu-Sans-Bold:box=1:boxcolor=black@0.4:boxborderw=20,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        str(intro_path)
    ]
    subprocess.run(cmd, capture_output=True)
    if not intro_path.exists():
        # Minimal fallback without text
        cmd2 = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1a2e:size=1920x1080:rate=30:duration={duration}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
            str(intro_path)
        ]
        subprocess.run(cmd2, capture_output=True)
    return intro_path

# ── Build outro card ──────────────────────────────────────────────────────────

def build_outro(duration: float = 5.0) -> Path:
    outro_path = WORK_DIR / "outro.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x1a1a2e:size=1920x1080:rate=30:duration={duration}",
        "-vf", (
            "drawtext=text='Like & Subscribe':"
            "fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h/2-50):"
            "font=DejaVu-Sans-Bold,"
            "drawtext=text='for more videos like this':"
            "fontcolor=0xcccccc:fontsize=40:x=(w-text_w)/2:y=(h/2+40):"
            "font=DejaVu-Sans,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        str(outro_path)
    ]
    subprocess.run(cmd, capture_output=True)
    if not outro_path.exists():
        cmd2 = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1a2e:size=1920x1080:rate=30:duration={duration}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
            str(outro_path)
        ]
        subprocess.run(cmd2, capture_output=True)
    return outro_path

# ── Burn subtitles ────────────────────────────────────────────────────────────

def burn_subtitles(input_video: Path, srt_path: str, output_path: Path) -> Path:
    """Burn SRT subtitles into the video."""
    srt_abs = Path(srt_path).resolve()
    if not srt_abs.exists() or srt_abs.stat().st_size == 0:
        print("   No subtitles to burn — copying as-is")
        shutil.copy(str(input_video), str(output_path))
        return output_path

    # Escape path for ffmpeg subtitles filter
    srt_escaped = str(srt_abs).replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", (
            f"subtitles='{srt_escaped}':"
            "force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&Hffffff,"
            "OutlineColour=&H000000,Outline=2,Shadow=1,Alignment=2,MarginV=40'"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ⚠️ Subtitle burn failed — copying without subtitles")
        shutil.copy(str(input_video), str(output_path))
    return output_path

# ── Clip Shorts (portrait 9:16, 60s) ─────────────────────────────────────────

def make_shorts(input_video: Path, output_path: Path):
    """Crop to 9:16 portrait and trim to 58 seconds for YouTube Shorts."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-t", "58",
        "-vf", "crop=608:1080:(iw-608)/2:0,scale=1080:1920",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ⚠️ Shorts clip failed: {result.stderr[-200:]}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🎬 Assembling video for slot {SLOT}…")
    title = script_data.get("title", script_data.get("topic", "Video"))

    # 1. Build Ken Burns slideshow
    slideshow = build_slideshow(image_paths, total_duration)

    # 2. Build intro and outro
    print("   Building intro/outro cards…")
    intro = build_intro(title)
    outro = build_outro()

    # 3. Concatenate: intro + slideshow + outro (video only, no audio yet)
    concat_list = WORK_DIR / "final_concat.txt"
    with open(concat_list, "w") as f:
        for p in [intro, slideshow, outro]:
            f.write(f"file '{p.resolve()}'\n")

    video_no_audio = WORK_DIR / "video_no_audio.mp4"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(video_no_audio)
    ]
    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Final concat failed:\n{result.stderr[-500:]}")

    # 4. Mux in audio (voice starts after 3s intro)
    video_with_audio = WORK_DIR / "video_with_audio.mp4"
    audio_delayed = WORK_DIR / "audio_delayed.aac"

    # Delay audio by intro duration (3s)
    delay_cmd = [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-af", "adelay=3000|3000",  # 3000ms = 3s delay
        "-c:a", "aac", "-b:a", "128k",
        str(audio_delayed)
    ]
    subprocess.run(delay_cmd, capture_output=True)

    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_no_audio),
        "-i", str(audio_delayed),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(video_with_audio)
    ]
    result = subprocess.run(mux_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio mux failed:\n{result.stderr[-500:]}")

    # 5. Burn in subtitles
    print("   Burning in subtitles…")
    final_path = OUTPUT_DIR / "final_video.mp4"
    burn_subtitles(video_with_audio, srt_path, final_path)

    # 6. Create Shorts version
    print("   Creating Shorts clip…")
    shorts_path = OUTPUT_DIR / "shorts.mp4"
    make_shorts(final_path, shorts_path)

    # 7. Clean up work dir
    shutil.rmtree(WORK_DIR, ignore_errors=True)

    size_mb = final_path.stat().st_size // (1024 * 1024)
    print(f"✅ Final video: {final_path} ({size_mb}MB)")
    if shorts_path.exists():
        shorts_mb = shorts_path.stat().st_size // (1024 * 1024)
        print(f"✅ Shorts clip: {shorts_path} ({shorts_mb}MB)")

    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"final_video={final_path}\n")
        f.write(f"shorts_path={shorts_path}\n")

if __name__ == "__main__":
    main()
