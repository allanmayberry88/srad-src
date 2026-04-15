# qFollow — Quote Follow-Up Automation

Automates contextual follow-up on quotes/proposals sent from email. First module of the Srad automation suite. V1 targets Allan's own Gmail (dogfood) before rolling to paying UK SME customers.

**Status:** Phase 1 in progress. See [`PLAN.md`](PLAN.md) for full roadmap, [`PREREQUISITES.md`](PREREQUISITES.md) for Phase 0 state, [`LEARNINGS.md`](LEARNINGS.md) for running gotchas.

## What it does

```
You send a quote from Gmail
        │
        ▼
Gmail watch() → Pub/Sub → n8n webhook
        │
        ▼
Haiku 4.5 classifies: is this a quote?
        │
        ▼
Slack: "I think you sent a quote to X — track it? [Yes/No]"
        │ (you click Yes)
        ▼
Quote stored in Supabase; day-3 / day-7 / day-14 follow-ups scheduled
        │
        ▼ (on each due date)
Haiku 4.5 generates a draft follow-up
        │
        ▼
Slack: "Day 3 follow-up ready — [Approve / Edit / Reject]"
        │ (you click Approve)
        ▼
Draft created in your Gmail Drafts folder (never auto-sent)
```

Reply detection runs on a separate 15-minute cron: if the recipient replies, remaining follow-ups for that thread are cancelled.

## Component map

| Component | Where | Purpose |
|-----------|-------|---------|
| **n8n** (Docker) | `deploy/docker-compose.yml` | Orchestration — all workflows live here |
| **Cloudflare Tunnel** (`cloudflared`) | external, quick tunnel | Exposes local n8n for Gmail Pub/Sub push + Slack webhooks |
| **Supabase** (Postgres) | `db/migrations/` | State — tenants, quotes, followups, engagement_events |
| **Google Cloud** — Gmail API + Pub/Sub | project `srad-493407` | Sent-mail notifications |
| **Slack app** | Allan's workspace | Approval UX via Block Kit |
| **Anthropic Claude Haiku 4.5** | API | Classification + draft generation |
| **Python utilities** | `scripts/` | OAuth token encryption, onboarding, tests |

## Directory layout

```
qfollow/
├── PLAN.md                 # Full roadmap (frozen)
├── PREREQUISITES.md        # Phase 0 checklist
├── README.md               # This file — kept in sync with reality
├── LEARNINGS.md            # Running log of gotchas + fixes
├── db/migrations/          # SQL migrations, applied in order
├── n8n/workflows/          # Exported workflow JSONs (source of truth)
├── prompts/                # Haiku/Sonnet prompt templates
├── scripts/                # Python utilities (token crypto, onboarding)
├── slack/                  # Slack app manifest + Block Kit templates
├── tests/                  # pytest unit tests
├── deploy/                 # docker-compose, .env.example
└── voice-samples/          # (gitignored) — Allan's sample emails for Phase 2
```

## Local dev quickstart

**Prerequisites:** everything in `PREREQUISITES.md` (all marked done as of 2026-04-15).

### 1. Start n8n

```bash
cd qfollow/deploy
docker compose up -d
```

n8n is now at `http://localhost:5678`. First run: create owner account.

### 2. Start the tunnel

```bash
cloudflared tunnel --url http://localhost:5678
```

Copy the `https://…trycloudflare.com` URL. **This URL changes on every restart.** When it changes you must:

1. Update `WEBHOOK_BASE_URL` in `qfollow/deploy/.env`
2. `docker compose up -d --force-recreate` so n8n rebakes it
3. Update Slack Interactivity + Slash Commands URLs at https://api.slack.com/apps
4. Update the Gmail Pub/Sub push subscription endpoint

### 3. Apply the Supabase schema

Migrations live at repo root: `supabase/migrations/`. Two ways to apply:

- **Local:** `supabase db push` (requires `SUPABASE_ACCESS_TOKEN` env var; project already linked)
- **CI:** push to `main` — `.github/workflows/supabase-migrate.yml` runs `db push` automatically. Requires repo secrets `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD`.

New migration: `supabase migration new <name>` → edits an auto-timestamped file. Commit + push and CI applies it.

### 4. Seed Allan as the first tenant

See `scripts/seed_allan_tenant.py` (created in checkpoint 3).

### 5. n8n workflows

Built live via the n8n MCP, not imported from JSON. Current state:

| Workflow | ID | Status | Trigger |
|---|---|---|---|
| `qfollow — quote-detection` | `Tmc7atNtMiVL6atO` | ✅ active | Pub/Sub push on `/webhook/pubsub/gmail` |
| `slack-interactions` | — | not built yet (checkpoint 5) | Slack Interactivity webhook |
| `followup-scheduler` | — | not built yet | cron 15m |
| `reply-checker` | — | not built yet | cron 15m |
| `gmail-watch-renewal` | — | not built yet | cron 6h |

Credentials required on the quote-detection workflow (attached in the n8n UI):
- **Gmail OAuth2 API** — on `Gmail history.list` and `Gmail messages.get`. Create once, reuse.

App-level env vars are consumed directly via `$env` expressions (`SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`), not n8n credentials. This requires `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` in `docker-compose.yml`.

## Env vars

See `deploy/.env.example` for the full list. Key ones:
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — service role; RLS bypassed for n8n
- `GOOGLE_CLIENT_ID` / `_SECRET` — OAuth web client
- `GOOGLE_PUBSUB_TOPIC` — `projects/srad-493407/topics/gmail-notifications`
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`
- `ANTHROPIC_API_KEY` — funded with £10 prepaid (no auto-renew)
- `TOKEN_ENCRYPTION_KEY` — 32-byte hex, used by `scripts/token_crypto.py` to encrypt OAuth refresh tokens at rest in `tenants.oauth_token_enc`
- `N8N_ENCRYPTION_KEY` — n8n's own credential encryption, unrelated to above
- `WEBHOOK_BASE_URL` — current tunnel URL

## Testing

```bash
cd qfollow
pytest tests/
```

- Unit tests mock Anthropic API and assert defensive parsing of classifier/extractor responses
- n8n workflows tested manually via n8n's "Execute Node" mode with mock payloads in `tests/fixtures/`
- E2E smoke test: send a real quote email → verify full flow through to Gmail draft (runbook in `tests/e2e.md`)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Slack interaction button does nothing | Tunnel URL changed; Slack still points at old URL | Update at api.slack.com/apps → Interactivity + Slash Commands |
| No Pub/Sub notification when sending email | Gmail watch() expired (max 7 days) | Re-run watch; Phase 2 adds auto-renewal cron |
| `history.list` returns unrelated events | Gmail `labelIds` watch filter is buggy (Google Issue #36759803) | Filter client-side in n8n: only act on `messageAdded` with `labelId: "SENT"` |
| n8n webhook returns 404 on tunnel URL | `WEBHOOK_URL` env not re-baked after tunnel change | `docker compose up -d --force-recreate` |

More in `LEARNINGS.md`.
