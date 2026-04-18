"""Unit tests for WhatsApp webhook payload parsing.

Tests the parsing logic used by the whatsapp-interactions n8n Code node.
The parser extracts sender phone, message text, and action number from
Meta Cloud API webhook payloads. Must handle text messages, status updates,
image messages, and malformed payloads gracefully.
"""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "whatsapp"


def parse_whatsapp_webhook(payload: dict) -> list[dict]:
    """Replicates the Parse WhatsApp Message logic from the n8n Code node.

    This is the reference Python implementation — the n8n node uses equivalent JS.
    Returns a list of parsed messages (empty list = drop the webhook).
    """
    entry = (payload.get("entry") or [None])[0]
    if not entry:
        return []
    changes = (entry.get("changes") or [None])[0]
    if not changes:
        return []
    value = changes.get("value", {})
    messages = value.get("messages")
    if not messages:
        return []

    results = []
    for message in messages:
        if message.get("type") != "text":
            continue
        text = (message.get("text", {}).get("body") or "").strip()
        import re
        action_match = re.match(r"^[1-3]$", text)
        results.append({
            "from": message.get("from", ""),
            "text": text,
            "action": action_match.group(0) if action_match else None,
            "msg_id": message.get("id", ""),
            "timestamp": message.get("timestamp", ""),
        })
    return results


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


class TestParseWhatsAppWebhook:
    def test_valid_action_1(self):
        payload = _load_fixture("incoming_text_1.json")
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] == "1"
        assert results[0]["from"] == "447700900001"
        assert results[0]["text"] == "1"
        assert results[0]["msg_id"].startswith("wamid.")

    def test_valid_action_2(self):
        payload = _load_fixture("incoming_text_2.json")
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] == "2"
        assert results[0]["text"] == "2"

    def test_non_action_text(self):
        payload = _load_fixture("incoming_text_hello.json")
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] is None
        assert results[0]["text"] == "hello there"

    def test_action_with_whitespace(self):
        payload = _load_fixture("incoming_text_1.json")
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = " 1 "
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] == "1"

    def test_status_update_ignored(self):
        payload = _load_fixture("status_update.json")
        results = parse_whatsapp_webhook(payload)
        assert results == []

    def test_image_message_ignored(self):
        payload = _load_fixture("image_message.json")
        results = parse_whatsapp_webhook(payload)
        assert results == []

    def test_empty_payload(self):
        results = parse_whatsapp_webhook({})
        assert results == []

    def test_no_entry(self):
        results = parse_whatsapp_webhook({"object": "whatsapp_business_account"})
        assert results == []

    def test_action_4_not_valid(self):
        payload = _load_fixture("incoming_text_1.json")
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "4"
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] is None

    def test_action_0_not_valid(self):
        payload = _load_fixture("incoming_text_1.json")
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "0"
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] is None

    def test_multiline_text_not_action(self):
        payload = _load_fixture("incoming_text_1.json")
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "1\nsome extra text"
        results = parse_whatsapp_webhook(payload)
        assert len(results) == 1
        assert results[0]["action"] is None
