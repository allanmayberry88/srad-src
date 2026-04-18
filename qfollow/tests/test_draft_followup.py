"""Unit tests for follow-up draft parsing and Gmail draft construction.

Tests the defensive JSON parsing for Haiku draft responses and the
RFC 2822 message building + base64url encoding used by the approve flow.
"""

import base64
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "draft"

STAGE_INSTRUCTIONS = {
    "day3": (
        "This is a day-3 follow-up. Tone: casual, brief. Goal: just confirm "
        "the email arrived and gently remind them."
    ),
    "day7": (
        "This is a day-7 follow-up. Tone: friendly but more substantive. "
        "Goal: re-engage by referencing something specific from the proposal."
    ),
    "day14": (
        "This is a day-14 follow-up. Tone: direct and warm. Goal: create "
        "gentle urgency. Reference the validity period if provided."
    ),
}


def parse_draft(raw_text: str, original_subject: str) -> dict:
    """Replicates the Parse Draft logic from the n8n Code node."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    fallback_subject = original_subject
    if not fallback_subject.startswith("Re: "):
        fallback_subject = f"Re: {fallback_subject}"

    try:
        parsed = json.loads(text)
        subject = parsed.get("draft_subject", fallback_subject)
        body = parsed.get("draft_body", text)
    except (json.JSONDecodeError, ValueError):
        subject = fallback_subject
        body = text

    if not subject.startswith("Re: "):
        subject = f"Re: {subject}"

    return {"draft_subject": subject, "draft_body": body}


def build_rfc2822(to: str, subject: str, body: str, from_addr: str = "") -> str:
    """Build an RFC 2822 message for Gmail drafts.create."""
    lines = []
    if from_addr:
        lines.append(f"From: {from_addr}")
    lines.append(f"To: {to}")
    lines.append(f"Subject: {subject}")
    lines.append('Content-Type: text/plain; charset="UTF-8"')
    lines.append("")
    lines.append(body)
    return "\r\n".join(lines)


def base64url_encode(message: str) -> str:
    """Base64url-encode an RFC 2822 message for the Gmail API."""
    return base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii")


# --- Fixture-based draft parsing tests ---


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_day3_draft():
    fix = load_fixture("day3_response.json")
    raw = fix["api_response"]["content"][0]["text"]
    result = parse_draft(raw, "Proposal - 2-week AI Sprint for Thistle & Finch Accountants")

    assert result["draft_subject"] == fix["expected"]["draft_subject"]
    assert "Rachel" in result["draft_body"]
    assert "Allan" in result["draft_body"]
    assert len(result["draft_body"]) < 500  # day3 should be brief


def test_day7_draft():
    fix = load_fixture("day7_response.json")
    raw = fix["api_response"]["content"][0]["text"]
    result = parse_draft(raw, "Proposal - 2-week AI Sprint for Thistle & Finch Accountants")

    assert result["draft_subject"].startswith("Re: ")
    assert "call" in result["draft_body"].lower() or "questions" in result["draft_body"].lower()


def test_day14_draft():
    fix = load_fixture("day14_response.json")
    raw = fix["api_response"]["content"][0]["text"]
    result = parse_draft(raw, "Proposal - 2-week AI Sprint for Thistle & Finch Accountants")

    assert "valid" in result["draft_body"].lower() or "call" in result["draft_body"].lower()


# --- Edge case parsing tests ---


def test_markdown_fenced_response():
    raw = '```json\n{"draft_subject":"Re: Test","draft_body":"Hi there"}\n```'
    result = parse_draft(raw, "Test")
    assert result["draft_subject"] == "Re: Test"
    assert result["draft_body"] == "Hi there"


def test_invalid_json_fallback():
    raw = "Sorry, I cannot generate that email."
    result = parse_draft(raw, "Original Subject")
    assert result["draft_subject"] == "Re: Original Subject"
    assert result["draft_body"] == raw


def test_missing_re_prefix_added():
    raw = '{"draft_subject":"Proposal Follow-up","draft_body":"Hi there"}'
    result = parse_draft(raw, "Proposal")
    assert result["draft_subject"].startswith("Re: ")


def test_existing_re_prefix_not_doubled():
    raw = '{"draft_subject":"Re: Proposal","draft_body":"Hi there"}'
    result = parse_draft(raw, "Proposal")
    assert result["draft_subject"] == "Re: Proposal"
    assert not result["draft_subject"].startswith("Re: Re: ")


# --- RFC 2822 + base64url tests ---


def test_rfc2822_format():
    msg = build_rfc2822(
        to="jane@acme.co.uk",
        subject="Re: AI Sprint Proposal",
        body="Hi Jane,\n\nJust checking in.\n\nCheers,\nAllan",
    )
    assert "To: jane@acme.co.uk" in msg
    assert "Subject: Re: AI Sprint Proposal" in msg
    assert 'Content-Type: text/plain; charset="UTF-8"' in msg
    assert "Hi Jane," in msg


def test_base64url_roundtrip():
    msg = build_rfc2822(
        to="test@example.com",
        subject="Re: Test",
        body="Hello world",
    )
    encoded = base64url_encode(msg)
    decoded = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
    assert decoded == msg
    # base64url should not contain + or / (only - and _)
    assert "+" not in encoded
    assert "/" not in encoded
