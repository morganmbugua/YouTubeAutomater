#!/usr/bin/env python3
"""
YouTube OAuth2 One-Time Setup
Run this locally ONCE to get your refresh token.
Then add the output values as GitHub secrets.

Usage:
  pip install google-auth-oauthlib
  python scripts/auth_youtube.py

You will be prompted to log in to Google in your browser.
After approving, copy the three values printed at the end into GitHub secrets.
"""

import json, os, sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: Missing dependency. Run: pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtubepartner",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

def main():
    print("YouTube OAuth2 Setup")
    print("=" * 40)
    print()

    client_id     = input("Paste your YouTube Client ID: ").strip()
    client_secret = input("Paste your YouTube Client Secret: ").strip()

    if not client_id or not client_secret:
        print("ERROR: Client ID and Secret are required.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token"
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    print()
    print("Opening browser for Google authentication…")
    print("(If browser doesn't open, copy the URL printed below and paste it manually)")
    print()

    creds = flow.run_local_server(port=0)

    print()
    print("=" * 60)
    print("SUCCESS! Add these 3 values as GitHub repository secrets:")
    print("=" * 60)
    print(f"YOUTUBE_CLIENT_ID     = {client_id}")
    print(f"YOUTUBE_CLIENT_SECRET = {client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
    print("=" * 60)
    print()
    print("In GitHub: Settings → Secrets and variables → Actions → New repository secret")

if __name__ == "__main__":
    main()
