#!/usr/bin/env python3
"""
Step 9: Log Results to Dashboard
Appends run data to dashboard/data/run_log.json and updates stats.json.
Called with if: always() so it runs even if earlier steps failed.
"""

import os, json, datetime
from pathlib import Path

SLOT     = os.environ.get("VIDEO_SLOT", "1")
STATUS   = os.environ.get("STATUS", "unknown")
VIDEO_ID = os.environ.get("YOUTUBE_VIDEO_ID", "")

OUTPUT_DIR = Path(f"output/slot_{SLOT}")

DASH_DATA  = Path("docs/data")
DASH_DATA.mkdir(parents=True, exist_ok=True)

LOG_FILE   = DASH_DATA / "run_log.json"
STATS_FILE = DASH_DATA / "stats.json"

# ── Build log entry ───────────────────────────────────────────────────────────

def build_entry() -> dict:
    topic_json = os.environ.get("TOPIC_DATA", "")
    if topic_json:
        try:
            topic_data = json.loads(topic_json)
        except Exception:
            topic_data = {}
    else:
        topic_path = OUTPUT_DIR / "topic.json"
        topic_data = json.loads(topic_path.read_text()) if topic_path.exists() else {}

    script_path = OUTPUT_DIR / "script.json"
    script_data = json.loads(script_path.read_text()) if script_path.exists() else {}

    crosspost_path = OUTPUT_DIR / "crosspost_result.json"
    crosspost = json.loads(crosspost_path.read_text()) if crosspost_path.exists() else {}

    return {
        "slot":         int(SLOT),
        "timestamp":    datetime.datetime.utcnow().isoformat() + "Z",
        "status":       STATUS,
        "topic":        topic_data.get("topic", "Unknown"),
        "content_type": topic_data.get("content_type", ""),
        "title":        script_data.get("title", ""),
        "video_id":     VIDEO_ID,
        "youtube_url":  f"https://youtu.be/{VIDEO_ID}" if VIDEO_ID else "",
        "instagram":    crosspost.get("instagram", False),
        "tiktok":       crosspost.get("tiktok", False),
    }

# ── Update stats ──────────────────────────────────────────────────────────────

def update_stats(entries: list[dict]):
    total    = len(entries)
    success  = sum(1 for e in entries if e["status"] in ["success", "unknown"] and e.get("video_id"))
    ig_posts = sum(1 for e in entries if e.get("instagram"))
    tt_posts = sum(1 for e in entries if e.get("tiktok"))

    # Count by content type
    by_type: dict[str, int] = {}
    for e in entries:
        ct = e.get("content_type", "other")
        by_type[ct] = by_type.get(ct, 0) + 1

    stats = {
        "total_runs":       total,
        "successful_videos": success,
        "success_rate":     round(success / total * 100, 1) if total else 0,
        "instagram_posts":  ig_posts,
        "tiktok_posts":     tt_posts,
        "content_breakdown": by_type,
        "last_updated":     datetime.datetime.utcnow().isoformat() + "Z"
    }
    STATS_FILE.write_text(json.dumps(stats, indent=2))

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"📊 Logging results for slot {SLOT} (status: {STATUS})…")

    entry = build_entry()

    # Load existing log
    if LOG_FILE.exists():
        try:
            log = json.loads(LOG_FILE.read_text())
        except Exception:
            log = []
    else:
        log = []

    log.append(entry)

    # Keep last 200 entries
    log = log[-200:]

    LOG_FILE.write_text(json.dumps(log, indent=2))
    update_stats(log)

    # Copy strategy.json into docs/data/ so GitHub Pages can serve it
    import shutil
    strategy_src = Path("scripts/strategy.json")
    strategy_dst = DASH_DATA / "strategy.json"
    if strategy_src.exists():
        shutil.copy(str(strategy_src), str(strategy_dst))

    print(f"✅ Dashboard data updated ({len(log)} entries total)")

if __name__ == "__main__":
    main()
