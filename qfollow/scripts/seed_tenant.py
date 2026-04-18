"""Seed or update a tenant row in Supabase.

Idempotent: upserts on email_address. Reads SUPABASE_URL + SUPABASE_SERVICE_KEY from env.

Usage:
    python -m scripts.seed_tenant \\
        --name "Allan Mayberry" \\
        --email allan@srad.scot \\
        --slack-channel C0AU0A02W48 \\
        --slack-team-id T0ATDPXCRJ5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def upsert_tenant(
    name: str,
    email: str,
    slack_channel: str,
    slack_team_id: str | None = None,
    approval_channel: str = "slack",
    whatsapp_phone_number: str | None = None,
) -> dict:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/tenants"
    key = os.environ["SUPABASE_SERVICE_KEY"]
    payload = {
        "name": name,
        "email_address": email,
        "email_provider": "google",
        "slack_channel": slack_channel,
        "active": True,
        "approval_channel": approval_channel,
    }
    if slack_team_id:
        payload["slack_team_id"] = slack_team_id
    if whatsapp_phone_number:
        payload["whatsapp_phone_number"] = whatsapp_phone_number
    req = urllib.request.Request(
        url + "?on_conflict=email_address",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())[0]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--slack-channel", required=True)
    p.add_argument("--slack-team-id", default=None)
    p.add_argument("--approval-channel", default="slack", choices=["slack", "whatsapp"])
    p.add_argument("--whatsapp-phone-number", default=None)
    args = p.parse_args()
    row = upsert_tenant(
        args.name,
        args.email,
        args.slack_channel,
        args.slack_team_id,
        args.approval_channel,
        args.whatsapp_phone_number,
    )
    print(f"Tenant upserted: id={row['id']} email={row['email_address']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
