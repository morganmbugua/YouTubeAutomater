#!/usr/bin/env python3
"""
Step 8: Upload Video to TikTok
Integrates with the YouTubeAutomater flow. 
Uses TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, and TIKTOK_REFRESH_TOKEN.
"""

import os
import json
import requests
from pathlib import Path

# ── Environment & Path Alignment ─────────────────────────────────────────────
SLOT       = os.environ.get("VIDEO_SLOT", "1")
OUTPUT_DIR = Path(f"output/slot_{SLOT}")

# Secrets from your GitHub Actions / Environment
CLIENT_KEY    = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["TIKTOK_REFRESH_TOKEN"]

# Alignment with YouTubeAutomater metadata
script_path = os.environ.get("SCRIPT_PATH", str(OUTPUT_DIR / "script.json"))
script_data = json.loads(Path(script_path).read_text())

# Extracting caption from your existing script structure
# Prioritizes 'title' from metadata, falls back to 'hook'
caption = script_data.get("metadata", {}).get("title") or script_data.get("hook", "Check out this video!")
caption += " #automation #shorts #fyp"

final_video = os.environ.get("FINAL_VIDEO", str(OUTPUT_DIR / "final_video.mp4"))

# ── TikTok API Logic ────────────────────────────────────────────────────────

def get_access_token():
    """Exchanges the refresh token for a temporary access token."""
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN
    }
    
    response = requests.post(url, headers=headers, data=data)
    res_json = response.json()
    
    if "access_token" in res_json:
        return res_json["access_token"]
    else:
        print(f"   ❌ Token Refresh Failed: {res_json}")
        return None

def upload_to_tiktok(access_token):
    """Initializes and executes the video upload."""
    file_size = os.path.getsize(final_video)
    
    # 1. Initialize Upload
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    init_data = {
        "post_info": {
            "title": caption[:150], # TikTok limit
            "privacy_level": "SELF_ONLY" # Change to PUBLIC_TO_EVERYONE for live
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1
        }
    }
    
    print(f"   📡 Initializing TikTok upload...")
    init_res = requests.post(init_url, headers=headers, json=init_data).json()
    
    if init_res.get("error", {}).get("code") != "ok":
        print(f"   ❌ Init failed: {init_res}")
        return None
        
    upload_url = init_res["data"]["upload_url"]
    publish_id = init_res["data"]["publish_id"]

    # 2. Upload Binary
    print("   📤 Transferring video file...")
    with open(final_video, "rb") as f:
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size-1}/{file_size}"
        }
        upload_res = requests.put(upload_url, headers=upload_headers, data=f)
    
    if upload_res.status_code in [200, 201]:
        print(f"   ✅ TikTok Upload Success! ID: {publish_id}")
        return publish_id
    else:
        print(f"   ❌ File transfer failed: {upload_res.text}")
        return None

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"📱 Processing TikTok Upload for Slot {SLOT}...")
    
    if not os.path.exists(final_video):
        print(f"   ❌ Video not found: {final_video}")
        return

    access_token = get_access_token()
    if access_token:
        publish_id = upload_to_tiktok(access_token)
        
        # Consistent with your YouTube result logging
        result = {"publish_id": publish_id, "status": "uploaded"}
        (OUTPUT_DIR / "tiktok_result.json").write_text(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
