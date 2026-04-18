"""Unit tests for quote field extraction parsing.

Tests the defensive JSON parsing logic used by the slack-interactions workflow
to extract structured fields from Haiku's response. The parser must handle:
- Valid responses with all fields
- Missing optional fields (default to null / GBP)
- Markdown-fenced responses (strip fences before parse)
- Completely invalid responses (return safe defaults)
"""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "extract"


def parse_extraction(raw_text: str, sent_at_iso: str, to_header: str) -> dict:
    """Replicates the Parse Extraction logic from the n8n Code node.

    This is the reference implementation — the n8n node uses equivalent JS.
    """
    text = raw_text.strip()
    # Strip markdown fences defensively
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    defaults = {
        "recipient_name": None,
        "recipient_email": to_header.split("<")[-1].rstrip(">").strip() if to_header else "",
        "total_amount": None,
        "currency": "GBP",
        "proposed_items": None,
        "valid_until": None,
        "summary": "",
    }

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return defaults

    result = {**defaults, **{k: v for k, v in parsed.items() if k in defaults}}

    # Ensure currency defaults to GBP if missing/empty
    if not result.get("currency"):
        result["currency"] = "GBP"

    # Compute valid_until default: sent_at + 30 days
    if result["valid_until"] is None and sent_at_iso:
        from datetime import datetime, timedelta

        try:
            sent_dt = datetime.fromisoformat(sent_at_iso.replace("Z", "+00:00"))
            result["valid_until"] = (sent_dt + timedelta(days=30)).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    return result


# --- Fixture-based tests ---


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_full_line_items():
    fix = load_fixture("full_line_items.json")
    raw_text = fix["api_response"]["content"][0]["text"]
    result = parse_extraction(raw_text, "2026-04-15T10:00:00Z", "Jane Smith <jane@acme.co.uk>")

    assert result["recipient_name"] == "Jane Smith"
    assert result["recipient_email"] == "jane@acme.co.uk"
    assert result["total_amount"] == 4200.00
    assert result["currency"] == "GBP"
    assert len(result["proposed_items"]) == 2
    assert "data migration" in result["proposed_items"][0]["description"]
    assert result["valid_until"] == "2026-05-15"
    assert "Acme" in result["summary"]


def test_simple_price():
    fix = load_fixture("simple_price.json")
    raw_text = fix["api_response"]["content"][0]["text"]
    result = parse_extraction(raw_text, "2026-04-10T09:00:00Z", "bob@taylorplumbing.co.uk")

    assert result["recipient_name"] == "Bob Taylor"
    assert result["total_amount"] == 850.00
    assert result["proposed_items"] is None
    # valid_until should default to sent_at + 30 days since LLM returned null
    assert result["valid_until"] == "2026-05-10"


def test_no_amount():
    fix = load_fixture("no_amount.json")
    raw_text = fix["api_response"]["content"][0]["text"]
    result = parse_extraction(raw_text, "2026-04-12T14:30:00Z", "sarah@northlegal.co.uk")

    assert result["total_amount"] is None
    assert result["recipient_email"] == "sarah@northlegal.co.uk"
    assert result["valid_until"] == "2026-05-12"


# --- Edge case tests ---


def test_markdown_fenced_response():
    raw = '```json\n{"recipient_name":"Test","recipient_email":"a@b.com","total_amount":100,"currency":"GBP","proposed_items":null,"valid_until":null,"summary":"Test quote"}\n```'
    result = parse_extraction(raw, "2026-04-15T10:00:00Z", "a@b.com")

    assert result["recipient_name"] == "Test"
    assert result["total_amount"] == 100


def test_completely_invalid_response():
    result = parse_extraction("I cannot process this request.", "2026-04-15T10:00:00Z", "Jane <jane@x.com>")

    assert result["recipient_name"] is None
    assert result["recipient_email"] == "jane@x.com"
    assert result["total_amount"] is None
    assert result["currency"] == "GBP"


def test_missing_currency_defaults_to_gbp():
    raw = '{"recipient_name":"Test","recipient_email":"a@b.com","total_amount":500,"currency":"","proposed_items":null,"valid_until":null,"summary":"Test"}'
    result = parse_extraction(raw, "2026-04-15T10:00:00Z", "a@b.com")

    assert result["currency"] == "GBP"


def test_extra_fields_ignored():
    raw = '{"recipient_name":"Test","recipient_email":"a@b.com","total_amount":500,"currency":"GBP","proposed_items":null,"valid_until":null,"summary":"Test","extra_field":"should be dropped"}'
    result = parse_extraction(raw, "2026-04-15T10:00:00Z", "a@b.com")

    assert "extra_field" not in result


def test_valid_until_preserved_when_extracted():
    """If LLM provides valid_until, don't override with sent_at + 30."""
    raw = '{"recipient_name":"Test","recipient_email":"a@b.com","total_amount":500,"currency":"GBP","proposed_items":null,"valid_until":"2026-06-01","summary":"Test"}'
    result = parse_extraction(raw, "2026-04-15T10:00:00Z", "a@b.com")

    assert result["valid_until"] == "2026-06-01"
