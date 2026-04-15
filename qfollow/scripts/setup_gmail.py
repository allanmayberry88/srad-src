"""One-time Gmail OAuth + watch() setup for a tenant.

Flow:
  1. Runs InstalledAppFlow in a browser (port 8765).
  2. Captures refresh_token; encrypts with TOKEN_ENCRYPTION_KEY; stores in
     tenants.oauth_token_enc.
  3. Calls gmail.users.watch with labelIds=["SENT"] + topicName=$GOOGLE_PUBSUB_TOPIC.
  4. Stores resulting historyId + expiration in tenants.gmail_history_id /
     gmail_watch_expires.

Prerequisite: add http://localhost:8765/ as an Authorized redirect URI on the
OAuth Web client in Google Cloud Console (project srad-493407).

Usage:
    python -m scripts.setup_gmail --email allan@srad.scot
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from scripts import token_crypto

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]
REDIRECT_PORT = 8765


def _supabase_patch(email: str, patch: dict) -> None:
    base = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/tenants"
    key = os.environ["SUPABASE_SERVICE_KEY"]
    qs = urllib.parse.urlencode({"email_address": f"eq.{email}"})
    req = urllib.request.Request(
        f"{base}?{qs}",
        data=json.dumps(patch).encode("utf-8"),
        method="PATCH",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    urllib.request.urlopen(req).read()


def run_oauth() -> "google.oauth2.credentials.Credentials":
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"http://localhost:{REDIRECT_PORT}/"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=REDIRECT_PORT, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        raise RuntimeError(
            "No refresh_token returned. Re-run with a fresh consent (revoke prior grant at "
            "https://myaccount.google.com/permissions)."
        )
    return creds


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True, help="tenants.email_address to update")
    args = p.parse_args()

    print("[1/3] Opening browser for Google OAuth …")
    creds = run_oauth()
    print("      got refresh_token")

    enc = token_crypto.encrypt(creds.refresh_token)
    _supabase_patch(args.email, {"oauth_token_enc": enc})
    print("[2/3] refresh_token encrypted + stored in tenants.oauth_token_enc")

    print("[3/3] Calling gmail.users.watch …")
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    watch_resp = gmail.users().watch(
        userId="me",
        body={
            "labelIds": ["SENT"],
            "topicName": os.environ["GOOGLE_PUBSUB_TOPIC"],
        },
    ).execute()
    history_id = watch_resp["historyId"]
    # expiration is ms since epoch
    expires = dt.datetime.fromtimestamp(int(watch_resp["expiration"]) / 1000, tz=dt.timezone.utc)
    _supabase_patch(
        args.email,
        {
            "gmail_history_id": str(history_id),
            "gmail_watch_expires": expires.isoformat(),
        },
    )
    print(f"      historyId={history_id}  expires={expires.isoformat()}")
    print("\nDone. Pub/Sub should fire on the next sent email.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
