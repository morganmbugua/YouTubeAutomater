#!/usr/bin/env python3
"""
Step 8: Cross-post to Instagram Reels + TikTok
Posts the Shorts clip to Instagram and TikTok.

Instagram: Requires Meta App Review before working on real accounts.
TikTok: Requires TikTok developer approval.

Both platforms are skipped gracefully if credentials are missing or approval
is not yet granted. The pipeline never fails due to cross-posting issues.
"""

import os, json, time, urllib.request, urllib.parse
from pathlib import Path

SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")

INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID   = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
TIKTOK_ACCESS_TOKEN    = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
GITHUB_TOKEN           = os.environ.get("GITHUB_TOKEN", "")

shorts_path    = os.environ.get("SHORTS_VIDEO",     str(OUTPUT_DIR / "shorts.mp4"))
topic_json     = os.environ.get("TOPIC_DATA", "")
topic_data     = json.loads(topic_json) if topic_json else json.loads((OUTPUT_DIR / "topic.json").read_text())
youtube_video_id = os.environ.get("YOUTUBE_VIDEO_ID", "")

# ── Get a public URL for the Shorts video ────────────────────────────────────

def get_public_video_url() -> str | None:
    """
    Upload the Shorts video to GitHub Releases and return its public URL.
    Falls back to using the YouTube Shorts URL if upload fails.
    """
    if youtube_video_id:
        youtube_shorts_url = f"https://www.youtube.com/shorts/{youtube_video_id}"
        # Instagram and TikTok can accept video file URLs, not YouTube URLs.
        # We need the actual video file hosted somewhere public.

    if not GITHUB_TOKEN:
        print("   No GITHUB_TOKEN — cannot host video publicly")
        return None

    shorts_file = Path(shorts_path)
    if not shorts_file.exists():
        print("   Shorts file not found")
        return None

    try:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not repo:
            return None

        # Create a release if none exists today
        today = __import__("datetime").date.today().isoformat()
        tag   = f"videos-{today}"

        # Try to create the release (idempotent — fails silently if exists)
        create_data = json.dumps({
            "tag_name": tag,
            "name": f"Videos {today}",
            "draft": False,
            "prerelease": False
        }).encode()
        create_req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases",
            data=create_data,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type":  "application/json",
                "Accept":        "application/vnd.github+json"
            }
        )
        try:
            with urllib.request.urlopen(create_req, timeout=15) as r:
                release_data = json.loads(r.read())
        except urllib.error.HTTPError:
            # Release already exists — fetch it
            list_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json"
                }
            )
            with urllib.request.urlopen(list_req, timeout=15) as r:
                release_data = json.loads(r.read())

        upload_url = release_data.get("upload_url", "").replace("{?name,label}", "")
        asset_name = f"slot_{SLOT}_shorts.mp4"

        with open(shorts_path, "rb") as f:
            video_bytes = f.read()

        upload_req = urllib.request.Request(
            f"{upload_url}?name={asset_name}",
            data=video_bytes,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type":  "video/mp4"
            }
        )
        with urllib.request.urlopen(upload_req, timeout=120) as r:
            asset_data = json.loads(r.read())

        url = asset_data.get("browser_download_url")
        print(f"   Video hosted at: {url}")
        return url

    except Exception as e:
        print(f"   ⚠️ GitHub video hosting failed: {e}")
        return None

# ── Instagram ─────────────────────────────────────────────────────────────────

def post_instagram(video_url: str) -> bool:
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        print("   Instagram: no credentials — skipping")
        return False
    if not video_url:
        print("   Instagram: no video URL — skipping")
        return False
    try:
        topic   = topic_data.get("topic", "")
        caption = f"{topic} 🎥\n\n#shorts #viral #trending #{topic.replace(' ', '').lower()[:20]}"
        if youtube_video_id:
            caption += f"\n\nFull video: https://youtu.be/{youtube_video_id}"

        # Step 1: Create media container
        create_params = urllib.parse.urlencode({
            "media_type":    "REELS",
            "video_url":     video_url,
            "caption":       caption,
            "access_token":  INSTAGRAM_ACCESS_TOKEN
        })
        req = urllib.request.Request(
            f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media",
            data=create_params.encode(),
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            container_id = json.loads(r.read()).get("id")

        if not container_id:
            print("   Instagram: container creation failed")
            return False

        print(f"   Instagram container: {container_id} — waiting for processing…")
        time.sleep(30)

        # Step 2: Publish
        pub_params = urllib.parse.urlencode({
            "creation_id": container_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN
        })
        pub_req = urllib.request.Request(
            f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish",
            data=pub_params.encode(),
            method="POST"
        )
        with urllib.request.urlopen(pub_req, timeout=30) as r:
            result = json.loads(r.read())
            media_id = result.get("id")

        print(f"   ✅ Instagram posted: {media_id}")
        return True

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"   ⚠️ Instagram HTTP {e.code}: {body[:200]}")
        # Check if it's an approval issue
        if "permission" in body.lower() or "review" in body.lower():
            print("   ℹ️ Instagram: App Review required. See setup guide.")
        return False
    except Exception as e:
        print(f"   ⚠️ Instagram error: {e}")
        return False

# ── TikTok ────────────────────────────────────────────────────────────────────

def post_tiktok(video_url: str) -> bool:
    if not TIKTOK_ACCESS_TOKEN:
        print("   TikTok: no credentials — skipping")
        return False
    if not video_url:
        print("   TikTok: no video URL — skipping")
        return False
    try:
        topic   = topic_data.get("topic", "")
        caption = f"{topic} #shorts #viral #trending"[:150]

        payload = json.dumps({
            "post_info": {
                "title":         caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet":  False,
                "disable_stitch": False
            },
            "source_info": {
                "source":    "PULL_FROM_URL",
                "video_url": video_url
            }
        }).encode()

        req = urllib.request.Request(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            data=payload,
            headers={
                "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
                "Content-Type":  "application/json; charset=UTF-8"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())

        if result.get("error", {}).get("code") == "ok":
            publish_id = result.get("data", {}).get("publish_id")
            print(f"   ✅ TikTok posted: {publish_id}")
            return True
        else:
            err = result.get("error", {})
            print(f"   ⚠️ TikTok error: {err}")
            if "permission" in str(err).lower():
                print("   ℹ️ TikTok: Developer approval required. See setup guide.")
            return False

    except Exception as e:
        print(f"   ⚠️ TikTok exception: {e}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"📱 Cross-posting for slot {SLOT}…")

    video_url = get_public_video_url()

    ig_ok  = post_instagram(video_url)
    tt_ok  = post_tiktok(video_url)

    result = {
        "instagram": ig_ok,
        "tiktok":    tt_ok,
        "video_url": video_url
    }
    (OUTPUT_DIR / "crosspost_result.json").write_text(json.dumps(result, indent=2))

    status = []
    if ig_ok:  status.append("Instagram ✅")
    if tt_ok:  status.append("TikTok ✅")
    if not ig_ok and not tt_ok:
        status.append("Cross-posting skipped (credentials missing or not approved)")

    print(f"✅ Cross-post: {', '.join(status)}")

if __name__ == "__main__":
    main()
