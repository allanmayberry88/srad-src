# qFollow — Prerequisites Checklist

Complete all items before starting Phase 1 code.

## Accounts & Services

- [x] **(Deferred)** ~~Hetzner Cloud VPS~~ — not needed for dev/dogfood. Run n8n locally in Docker.
- [x] **(Done)** Cloudflare Tunnel — `cloudflared` installed (v2025.8.1). Run `cloudflared tunnel --url http://localhost:5678` to expose local n8n.
- [x] **(Done)** Supabase project — `https://frcokifutyygafyzspbt.supabase.co` (free tier)
- [x] **(Done)** Google Cloud project — `srad-493407`. gcloud CLI installed & authenticated.
- [x] **(Done)** Google Cloud APIs & credentials:
  - Gmail API enabled
  - Cloud Pub/Sub API enabled
  - OAuth 2.0 Web client created (redirect `http://localhost:5678/rest/oauth2-credential/callback`); ID + Secret in `.env`
  - Pub/Sub topic `projects/srad-493407/topics/gmail-notifications` created
  - `gmail-api-push@system.gserviceaccount.com` granted `roles/pubsub.publisher` on the topic
  - Note: org policy `iam.allowedPolicyMemberDomains` was overridden at project level to `allowAll` to permit the external Gmail service account
- [x] **(Done)** Slack app created, installed, bot token + signing secret in `.env`. Bot scopes: `chat:write`, `chat:write.public`, `commands`, `im:write`.
  - **Deferred to Phase 1:** Interactivity request URL (`/slack/interactions`) and Slash Commands URL (`/slack/commands`) — both need the Cloudflare Tunnel URL.
- [x] **(Done)** Anthropic API key in `.env`. Funded with £10 prepaid credit, no auto-renewal — revisit spend limits / auto-top-up once there are paying customers.
- [x] **(Deferred)** ~~DNS A records~~ — not needed while running locally.

## Local Dev Environment

- [x] **(Done)** Git repo initialised with `.gitignore`
- [x] **(Done)** Python 3.14.3 available
- [x] **(Done)** Docker available (v29.2.1)
- [ ] n8n — will run via Docker (docker-compose.yml created in Phase 1)

## Git

- [x] **(Done)** Git configured: `Allan <allan@srad.scot>`
- [x] **(Done)** Remote: `https://github.com/allanmayberry88/srad-src.git` — initial commit pushed to `main`

## MCP Servers

- [x] **(Done)** Supabase MCP configured in `.mcp.json` using `@supabase/mcp-server-supabase` (`--project-ref frcokifutyygafyzspbt --read-only`). **Requires** `SUPABASE_ACCESS_TOKEN` env var set to a Supabase Personal Access Token (create at https://supabase.com/dashboard/account/tokens — this is NOT the service-role key). Restart Claude Code after setting.
- [x] **(Done)** gcloud MCP configured in `.mcp.json` using `@google-cloud/gcloud-mcp` (inherits active gcloud project `srad-493407`). Restart Claude Code to activate.
- [ ] n8n MCP (`github.com/czlonkowski/n8n-mcp`) — add once n8n is running locally
- [ ] Slack MCP — not critical; test via n8n workflows

## Credentials in `.env`

File: `qfollow/deploy/.env` (gitignored)

| Credential | Status |
|-----------|--------|
| SUPABASE_URL | Done |
| SUPABASE_ANON_KEY | Done |
| SUPABASE_SERVICE_KEY | Done |
| GOOGLE_PROJECT_ID | Done (`srad-493407`) |
| GOOGLE_CLIENT_ID | Done |
| GOOGLE_CLIENT_SECRET | Done |
| GOOGLE_PUBSUB_TOPIC | Done |
| SLACK_BOT_TOKEN | Done |
| SLACK_SIGNING_SECRET | Done |
| ANTHROPIC_API_KEY | Done |
| TOKEN_ENCRYPTION_KEY | Done |
| WEBHOOK_BASE_URL | Set when Cloudflare Tunnel starts |

## Voice Samples

- [ ] **(Allan)** Collect 10-20 sent emails as voice/tone samples:
  - 3-5 formal quotes or proposals
  - 3-5 casual follow-up emails
  - 3-5 general business emails
  - Format: plain text (subject + body), one file per email or one consolidated file
  - Save to `qfollow/voice-samples/` (gitignored)

## What Remains Before Phase 1

1. **Voice samples** (can defer to before Phase 2)
2. **Phase 1 follow-ups:** paste tunnel URL into Slack Interactivity + Slash Commands
