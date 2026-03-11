#!/usr/bin/env python3
"""
Step 10: Fetch YouTube Analytics
Pulls 30-day performance data from YouTube Analytics API.
Run daily by the optimize_strategy.yml workflow.
Saves data to dashboard/data/analytics.json.
"""

import os, json, datetime, urllib.request, urllib.parse
from pathlib import Path

YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

DASH_DATA = Path("dashboard/data")
DASH_DATA.mkdir(parents=True, exist_ok=True)

def get_access_token() -> str:
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
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["access_token"]

def fetch_analytics(access_token: str) -> dict:
    end_date   = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=30)

    params = urllib.parse.urlencode({
        "ids":        "channel==MINE",
        "startDate":  start_date.isoformat(),
        "endDate":    end_date.isoformat(),
        "metrics":    "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes",
        "dimensions": "day",
        "sort":       "day"
    })
    req = urllib.request.Request(
        f"https://youtubeanalytics.googleapis.com/v2/reports?{params}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def main():
    print("📊 Fetching YouTube analytics…")

    if not all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        print("   Missing YouTube credentials — skipping analytics fetch")
        return

    try:
        access_token   = get_access_token()
        analytics_data = fetch_analytics(access_token)

        output = {
            "fetched_at":  datetime.datetime.utcnow().isoformat() + "Z",
            "period_days": 30,
            "data":        analytics_data
        }
        (DASH_DATA / "analytics.json").write_text(json.dumps(output, indent=2))
        print("✅ Analytics saved to dashboard/data/analytics.json")
    except Exception as e:
        print(f"⚠️ Analytics fetch failed: {e}")
        # Write empty file so dashboard doesn't error
        (DASH_DATA / "analytics.json").write_text(
            json.dumps({"fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
                        "error": str(e), "data": {}})
        )

if __name__ == "__main__":
    main()
