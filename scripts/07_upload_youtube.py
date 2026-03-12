#!/usr/bin/env python3
"""
Step 7: Upload Video to YouTube
Uploads the final video with metadata using the YouTube Data API v3.
Uses OAuth2 refresh token (set up once with auth_youtube.py).
Schedules the video for the optimal posting time from strategy.json.
"""

import os, json, time, datetime
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")

YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

script_path = os.environ.get("SCRIPT_PATH", str(OUTPUT_DIR / "script.json"))
script_data = json.loads(Path(script_path).read_text())

topic_json = os.environ.get("TOPIC_DATA", "")
topic_data = json.loads(topic_json) if topic_json else json.loads((OUTPUT_DIR / "topic.json").read_text())

final_video   = os.environ.get("FINAL_VIDEO",   str(OUTPUT_DIR / "final_video.mp4"))
thumbnail_path = os.environ.get("THUMBNAIL",     str(OUTPUT_DIR / "thumbnail.jpg"))

STRATEGY_FILE = Path("scripts/strategy.json")

# ── OAuth2 token refresh ──────────────────────────────────────────────────────

def get_access_token() -> str:
    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        "client_id":     YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type":    "refresh_token"
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            if "access_token" not in data:
                raise RuntimeError(f"No access_token in response: {data}")
            return data["access_token"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"   ❌ Token refresh failed HTTP {e.code}: {body}")
        print(f"   Check that YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN are correct in GitHub Secrets.")
        raise

# ── Calculate scheduled publish time ─────────────────────────────────────────

def get_publish_time() -> str:
    """
    Return an ISO 8601 UTC time string for when to publish.
    Uses best_posting_hours from strategy.json.
    Staggers by slot number to avoid all 6 publishing at once.
    """
    strategy = {}
    if STRATEGY_FILE.exists():
        try:
            strategy = json.loads(STRATEGY_FILE.read_text())
        except Exception:
            pass

    best_hours = strategy.get("best_posting_hours", [9, 12, 15, 17, 20, 22])

    # Each slot gets a different hour
    slot_int = int(SLOT) - 1  # 0-indexed
    hour = best_hours[slot_int % len(best_hours)]

    # Schedule for tomorrow at this hour
    now = datetime.datetime.utcnow()
    publish_dt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if publish_dt <= now:
        publish_dt += datetime.timedelta(days=1)

    return publish_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

# ── Upload video (resumable) ──────────────────────────────────────────────────

def upload_video(access_token: str, publish_time: str) -> str:
    import urllib.request
    video_path = Path(final_video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {final_video}")

    file_size = video_path.stat().st_size
    title     = script_data.get("title", topic_data["topic"])[:100]
    desc      = script_data.get("description", f"Video about {topic_data['topic']}")[:5000]
    tags      = script_data.get("tags", topic_data.get("seo_keywords", []))[:500]

    metadata = {
        "snippet": {
            "title":       title,
            "description": desc,
            "tags":        tags,
            "categoryId":  "22"  # People & Blogs — works for most content
        },
        "status": {
            "privacyStatus":           "private",
            "publishAt":               publish_time,
            "selfDeclaredMadeForKids": False
        }
    }

    # Step 1: Initiate resumable upload
    meta_bytes = json.dumps(metadata).encode()
    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        data=meta_bytes,
        headers={
            "Authorization":           f"Bearer {access_token}",
            "Content-Type":            "application/json",
            "X-Upload-Content-Type":   "video/mp4",
            "X-Upload-Content-Length": str(file_size)
        }
    )
    with urllib.request.urlopen(init_req, timeout=30) as r:
        upload_url = r.getheader("Location")

    if not upload_url:
        raise RuntimeError("YouTube did not return an upload URL")

    print(f"   Uploading {file_size // (1024*1024)}MB to YouTube…")

    # Step 2: Upload the file in chunks
    chunk_size  = 10 * 1024 * 1024  # 10MB chunks
    uploaded    = 0
    video_id    = None

    with open(final_video, "rb") as f:
        while uploaded < file_size:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            end_byte = uploaded + len(chunk) - 1
            upload_req = urllib.request.Request(
                upload_url,
                data=chunk,
                headers={
                    "Content-Range":  f"bytes {uploaded}-{end_byte}/{file_size}",
                    "Content-Length": str(len(chunk))
                },
                method="PUT"
            )
            try:
                with urllib.request.urlopen(upload_req, timeout=300) as r:
                    if r.status in [200, 201]:
                        resp_data  = json.loads(r.read())
                        video_id   = resp_data.get("id")
            except urllib.error.HTTPError as e:
                if e.code == 308:  # Resume Incomplete — expected during chunked upload
                    pass
                else:
                    raise
            uploaded += len(chunk)
            pct = (uploaded / file_size) * 100
            print(f"   Upload: {pct:.0f}%", end="\r")

    print()
    if not video_id:
        raise RuntimeError("Upload completed but no video ID returned")

    print(f"   ✅ Video uploaded: https://youtu.be/{video_id}")
    return video_id

# ── Upload thumbnail ──────────────────────────────────────────────────────────

def upload_thumbnail(access_token: str, video_id: str):
    import urllib.request
    thumb_path = Path(thumbnail_path)
    if not thumb_path.exists():
        print("   No thumbnail file — skipping")
        return

    with open(thumbnail_path, "rb") as f:
        thumb_bytes = f.read()

    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}&uploadType=media",
        data=thumb_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "image/jpeg"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"   ✅ Thumbnail uploaded (status {r.status})")
    except Exception as e:
        print(f"   ⚠️ Thumbnail upload failed: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"📤 Uploading to YouTube (slot {SLOT})…")

    access_token = get_access_token()
    publish_time = get_publish_time()
    print(f"   Scheduled publish: {publish_time}")

    video_id = upload_video(access_token, publish_time)
    upload_thumbnail(access_token, video_id)

    # Save result
    result = {"video_id": video_id, "publish_time": publish_time, "url": f"https://youtu.be/{video_id}"}
    (OUTPUT_DIR / "upload_result.json").write_text(json.dumps(result, indent=2))

    gho = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(gho, "a") as f:
        f.write(f"youtube_video_id={video_id}\n")
        f.write(f"youtube_url=https://youtu.be/{video_id}\n")

    print(f"✅ YouTube upload complete: https://youtu.be/{video_id}")

if __name__ == "__main__":
    main()
