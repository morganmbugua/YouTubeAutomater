#!/usr/bin/env python3
"""
Sequential slot runner.
Runs each video slot one at a time so Gemini API is never hit concurrently.
Waits 20s between slots to stay well within free tier RPM limits.
"""

import os, sys, json, time, subprocess
from pathlib import Path

NUM_VIDEOS = int(os.environ.get("NUM_VIDEOS", "1") or "1")
NUM_VIDEOS = max(1, min(6, NUM_VIDEOS))

SCRIPTS = [
    "01_research_topic.py",
    "02_generate_script.py",
    "03_generate_voice.py",
    "04_fetch_images.py",
    "05_assemble_video.py",
    "06_generate_thumbnail.py",
    "07_upload_youtube.py",
    "08_crosspost.py",
    "09_log_results.py",
]

def run_slot(slot: int) -> bool:
    print(f"\n{'='*60}")
    print(f"🎬 SLOT {slot} / {NUM_VIDEOS}")
    print(f"{'='*60}")

    env = os.environ.copy()
    env["VIDEO_SLOT"] = str(slot)

    # Track outputs across steps (simulate GITHUB_OUTPUT)
    step_outputs = {}
    output_file = Path(f"output/slot_{slot}/.step_outputs")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("")

    for script in SCRIPTS:
        print(f"\n▶ Running {script}…")
        env["GITHUB_OUTPUT"] = str(output_file)

        # Inject previous step outputs into env
        for k, v in step_outputs.items():
            env[k.upper()] = v

        result = subprocess.run(
            [sys.executable, f"scripts/{script}"],
            env=env,
            text=True
        )

        # Parse new outputs
        if output_file.exists():
            for line in output_file.read_text().splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    step_outputs[k.strip().upper()] = v.strip()

        if result.returncode != 0:
            print(f"   ❌ {script} failed (exit {result.returncode}) — skipping rest of slot {slot}")
            # Still run log_results so failure is recorded
            if script != "09_log_results.py":
                env["SLOT_STATUS"] = "failure"
                subprocess.run([sys.executable, "scripts/09_log_results.py"], env=env)
            return False

    print(f"\n✅ Slot {slot} complete")
    return True

def main():
    print(f"🚀 Starting {NUM_VIDEOS} video slot(s) — sequential mode")
    print(f"   (Sequential = no parallel Gemini calls = no rate limits)\n")

    results = []
    for slot in range(1, NUM_VIDEOS + 1):
        success = run_slot(slot)
        results.append((slot, success))

        # Wait between slots to give Gemini breathing room
        if slot < NUM_VIDEOS:
            print(f"\n⏳ Waiting 20s before next slot…")
            time.sleep(20)

    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS")
    print(f"{'='*60}")
    for slot, ok in results:
        status = "✅ Success" if ok else "❌ Failed"
        print(f"  Slot {slot}: {status}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} slots completed successfully")

if __name__ == "__main__":
    main()
