# Srad Automation Modules

This repo contains automation modules for Srad, a productised AI sprint business targeting UK SMEs. Each module lives in its own directory; shared patterns and learnings live at the repo root.

## Module Index

| Module | Directory | Status | Description |
|--------|-----------|--------|-------------|
| qFollow | `qfollow/` | Phase 2 complete ✅ — dogfood ready | Quote/proposal follow-up automation |

## Cross-Project Conventions

### Progress Tracking & Stop/Start Resilience

- Use Claude Code tasks to track progress within each build session
- Each phase/sub-task should be checkpointed — assume work will be interrupted and resumed in a new conversation
- This file (`CLAUDE.md`) and Claude Code memory files are the continuity mechanism between sessions
- Update this file after completing each phase with what was built, what's next, and any gotchas discovered

### Build and Deploy As We Go

- Every phase must end with something deployable and testable — no "big bang" integration
- Each subsequent phase deploys incrementally on top of the previous
- Never leave the system in a broken deployed state between sessions

### Automated Testing

- **Unit tests:** For all LLM prompt logic (mock the API, test parsing of responses), state transitions, and utility functions
- **Integration tests:** For n8n workflows — test the full flow with mock email data against real Supabase
- **E2E tests:** At least one per phase — verify the full pipeline end-to-end
- **Test framework:** pytest for Python scripts, n8n's built-in test mode for workflows
- Tests run before every deploy; broken tests block deployment
- Test files live in `<module>/tests/`

### Fail/Retry Loop

- All n8n workflows must have error handling with configurable retry (3 retries, exponential backoff)
- Dead-letter logging: failed workflow executions logged to a Supabase `error_log` table with full context
- Alert via Slack if any workflow fails 3 consecutive times
- Never silently swallow errors — every failure must be visible

### Error Handling Standards

- All external API calls (Gmail, Graph, Slack, Claude) must have try/catch with meaningful error messages
- Log: timestamp, tenant_id, workflow name, error message, full context
- Retry: 3 attempts with exponential backoff (1s, 4s, 16s)
- Alert: Slack notification to operator channel after 3 consecutive failures

### Model Selection (for Claude Code during builds)

- **Haiku:** Straightforward code generation — prompts, simple scripts, config files, tests
- **Sonnet:** Moderate complexity — n8n workflow logic, integration code, debugging
- **Opus:** Only when stuck on a tricky reasoning problem — escalate, don't default to it

### LLM Usage in Production

- **Haiku 4.5** for all runtime LLM calls (classification, extraction, draft generation) — keeps costs under £0.10/customer/month
- **Sonnet 4.6** for one-time style extraction during customer onboarding (harder task)
- Always include structured output instructions in prompts; parse JSON responses defensively

### Naming Conventions

- Module directories: lowercase, short, memorable (e.g., `qfollow/`)
- Database tables: snake_case, prefixed by module if ambiguous
- n8n workflows: kebab-case JSON filenames (e.g., `quote-detection.json`)
- Python scripts: snake_case (e.g., `onboard_tenant.py`)
- Prompt files: kebab-case markdown (e.g., `classify-quote.md`)

### Multi-Tenancy

- Single Supabase project serves all customers
- All tables include `tenant_id` column
- Row-Level Security (RLS) enforced on every table — no exceptions
- Every query must filter by `tenant_id`

### Tenant Isolation (CRITICAL)

- Every Supabase query MUST include `tenant_id` filter — no exceptions
- Slack notifications MUST use the tenant's `slack_channel` from DB lookup — never hardcode or use env vars
- Error handler alerts go to operator channel only — never include customer email content
- DB triggers enforce cross-table tenant_id consistency (followups ↔ quotes, events ↔ quotes)
- New workflows: establish tenant_id in the first 2-3 nodes, propagate to all downstream queries
- Cron-driven batch workflows (reply-checker, followup-scheduler) query all tenants but carry tenant_id per-item through the data flow
- `test_tenant_isolation.py` audits all workflows against these rules — run before every deploy

### Secrets & Config

- Never commit secrets — use `.env` files (gitignored)
- `.env.example` in each module's `deploy/` directory documents required variables
- OAuth tokens stored encrypted (AES-256) in Supabase
- API keys passed as environment variables to n8n

### Deployment

- Target: Hetzner Cloud CX22 VPS (Docker + n8n)
- Domain: `srad.scot` — subdomains `app.srad.scot` and `api.srad.scot` for app endpoints
- All services run via docker-compose
- nginx reverse proxy for webhooks and any web endpoints

## Shared Resources

- `shared/prompts/` — LLM prompt templates reusable across modules
- `shared/schemas/` — Common DB patterns (e.g., tenant table, audit columns)
- `shared/docs/` — Cross-module learnings (OAuth patterns, n8n conventions, deployment)

## Gotchas & Learnings

_Updated after each phase. Add findings here so future modules benefit._

- **n8n env access:** set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` to let expressions read `$env`.
- **n8n HTTP node `jsonBody`:** wrap in `={{ JSON.stringify({...}) }}` — raw `={...}` with template literals fails static JSON validation.
- **n8n Code nodes:** default mode drops all items except the first. Use `mode: "runOnceForEachItem"` whenever upstream fans out.
- **Supabase REST → n8n HTTP node:** single-element arrays are auto-unwrapped in expressions. Reference `$json.field`, not `$json[0].field`.
- **Gmail push cursor:** persist `history.list` response's `historyId`, not the Pub/Sub notification's (which can be stale).
- **n8n HTTP Request `authentication`:** never set `genericCredentialType` via MCP unless you have a linked n8n credential store entry. Use `"none"` and pass keys via header expressions.
- **n8n cron schedule reset:** saving a workflow with Schedule Trigger resets the cron relative to save time.
- **Supabase column names:** always verify via `information_schema.columns` before building workflow nodes — don't assume column names.
- See `qfollow/LEARNINGS.md` for full Phase 1+2 gotcha log.
