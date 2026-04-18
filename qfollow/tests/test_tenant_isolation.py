"""Tenant isolation audit for n8n workflows.

Fetches all qfollow workflows from the n8n API and verifies that every
Supabase REST query includes a tenant_id filter. Queries without tenant_id
can leak data across tenants.

Requires: N8N_API_KEY and N8N_BASE_URL env vars (or reads from deploy/.env).
Run with: pytest qfollow/tests/test_tenant_isolation.py -v
"""

import json
import os
import re
from pathlib import Path

import pytest
import requests

DEPLOY_ENV = Path(__file__).parent.parent / "deploy" / ".env"

# Nodes that legitimately query across all tenants (cron-driven batch processors)
CROSS_TENANT_ALLOWLIST = {
    # Cron-driven batch queries that process all tenants — tenant_id propagates via data flow
    "qfollow — reply-checker": {"Query Active Quotes", "Query Expired Quotes"},
    "qfollow — followup-scheduler": {
        "Query Due Followups",
        # These PATCH by primary key (id=eq.) on items from tenant-scoped batch
        "Save Draft",
        "Update Sent Status",
    },
    "qfollow — error-handler": {"Log Error", "Read Health", "PATCH Health", "Mark Alerted"},
    "qfollow — gmail-watch-renewal": {"Query Active Tenants"},
    # Insert Followups: POST body contains tenant_id in row data (dynamic expression)
    "qfollow — slack-commands": {"Insert Followups"},
    "qfollow — slack-interactions": {"Insert Followups"},
    "qfollow — whatsapp-interactions": {"Insert Followups"},
}

# Tables where tenant_id column isn't applicable:
# - workflow_health / error_log: operational tables, no tenant dimension
# - tenants: the id column IS the tenant — filtered by id, email, or slack_team_id
NON_TENANT_TABLES = {"workflow_health", "error_log", "tenants"}


def _load_env():
    """Read N8N_API_KEY from deploy/.env if not in environment."""
    if os.environ.get("N8N_API_KEY"):
        return
    if DEPLOY_ENV.exists():
        for line in DEPLOY_ENV.read_text().splitlines():
            if line.startswith("N8N_API_KEY="):
                os.environ["N8N_API_KEY"] = line.split("=", 1)[1].strip()
            elif line.startswith("WEBHOOK_BASE_URL="):
                os.environ.setdefault(
                    "N8N_BASE_URL",
                    line.split("=", 1)[1].strip().replace("/webhook", ""),
                )


def _get_workflows():
    """Fetch all qfollow workflows from n8n API."""
    _load_env()
    api_key = os.environ.get("N8N_API_KEY")
    base_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678")
    if not api_key:
        pytest.skip("N8N_API_KEY not set — skipping live audit")

    resp = requests.get(
        f"{base_url}/api/v1/workflows",
        headers={"X-N8N-API-KEY": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    workflows = data.get("data", data)
    return [w for w in workflows if w.get("name", "").startswith("qfollow")]


def _is_supabase_query(node: dict) -> bool:
    """Check if an HTTP Request node targets Supabase REST API."""
    if node.get("type") != "n8n-nodes-base.httpRequest":
        return False
    params = node.get("parameters", {})
    url = params.get("url", "")
    if "SUPABASE_URL" in url or "supabase.co/rest" in url:
        return True
    # Check query parameters too
    qp = params.get("queryParameters", {}).get("parameters", [])
    for p in qp:
        if "supabase" in str(p.get("value", "")).lower():
            return True
    return False


def _targets_non_tenant_table(url: str) -> bool:
    """Check if the URL targets a table that doesn't need tenant_id."""
    for table in NON_TENANT_TABLES:
        if f"/rest/v1/{table}" in url:
            return True
    return False


def _has_tenant_id_filter(node: dict) -> bool:
    """Check if the node's URL or query params include tenant_id filtering."""
    params = node.get("parameters", {})
    url = params.get("url", "")
    if "tenant_id=eq." in url or "tenant_id" in url:
        return True
    # Check query parameters
    qp = params.get("queryParameters", {}).get("parameters", [])
    for p in qp:
        name = p.get("name", "")
        value = str(p.get("value", ""))
        if "tenant_id" in name or "tenant_id" in value:
            return True
    # Check body for INSERTs that include tenant_id
    body = params.get("jsonBody", "")
    if params.get("method") == "POST" and "tenant_id" in body:
        return True
    return False


def _is_allowlisted(workflow_name: str, node_name: str) -> bool:
    """Check if this node is in the cross-tenant allowlist."""
    allowed = CROSS_TENANT_ALLOWLIST.get(workflow_name, set())
    return node_name in allowed


def test_all_supabase_queries_have_tenant_id():
    """Every Supabase query must include tenant_id, unless allowlisted."""
    workflows = _get_workflows()
    assert len(workflows) > 0, "No qfollow workflows found"

    violations = []
    for wf in workflows:
        wf_name = wf["name"]
        for node in wf.get("nodes", []):
            if not _is_supabase_query(node):
                continue
            url = node.get("parameters", {}).get("url", "")
            if _targets_non_tenant_table(url):
                continue
            if _is_allowlisted(wf_name, node["name"]):
                continue
            if not _has_tenant_id_filter(node):
                violations.append(
                    f"  {wf_name} → {node['name']} (id={node.get('id')})"
                )

    if violations:
        msg = "Supabase queries missing tenant_id filter:\n" + "\n".join(violations)
        pytest.fail(msg)


def test_no_hardcoded_slack_channels():
    """Slack notifications must use tenant's channel from DB, not hardcoded values."""
    workflows = _get_workflows()

    # error-handler is allowed to use a hardcoded operator channel
    OPERATOR_WORKFLOWS = {"qfollow — error-handler"}
    channel_pattern = re.compile(r"C[A-Z0-9]{10}")

    violations = []
    for wf in workflows:
        if wf["name"] in OPERATOR_WORKFLOWS:
            continue
        for node in wf.get("nodes", []):
            params = node.get("parameters", {})
            url = params.get("url", "")
            body = params.get("jsonBody", "")
            if "slack.com/api" not in url:
                continue
            if channel_pattern.search(body):
                violations.append(
                    f"  {wf['name']} → {node['name']}: hardcoded channel ID in body"
                )

    if violations:
        msg = "Hardcoded Slack channel IDs found:\n" + "\n".join(violations)
        pytest.fail(msg)


def test_no_hardcoded_whatsapp_numbers():
    """WhatsApp messages must use tenant's number from DB, not hardcoded values."""
    workflows = _get_workflows()

    phone_pattern = re.compile(r"\b\d{10,15}\b")

    violations = []
    for wf in workflows:
        for node in wf.get("nodes", []):
            params = node.get("parameters", {})
            url = params.get("url", "")
            body = params.get("jsonBody", "")
            if "graph.facebook.com" not in url:
                continue
            if phone_pattern.search(body):
                violations.append(
                    f"  {wf['name']} → {node['name']}: hardcoded phone number in body"
                )

    if violations:
        msg = "Hardcoded WhatsApp phone numbers found:\n" + "\n".join(violations)
        pytest.fail(msg)


def test_workflow_count():
    """Verify expected number of qfollow workflows are active."""
    workflows = _get_workflows()
    active = [w for w in workflows if w.get("active")]
    assert len(active) >= 8, (
        f"Expected at least 8 active qfollow workflows, found {len(active)}: "
        + ", ".join(w["name"] for w in active)
    )
