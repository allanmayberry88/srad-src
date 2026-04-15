# qFollow — Prerequisites Checklist

Complete all items before starting Phase 1 code.

## Accounts & Services

- [x] **(Deferred)** ~~Hetzner Cloud VPS~~ — not needed for dev/dogfood. Run n8n locally in Docker.
- [x] **(Done)** Cloudflare Tunnel — `cloudflared` installed (v2025.8.1). Run `cloudflared tunnel --url http://localhost:5678` to expose local n8n.
- [x] **(Done)** Supabase project — `https://frcokifutyygafyzspbt.supabase.co` (free tier)
- [x] **(Done)** Google Cloud project — `srad-493407`. gcloud CLI installed & authenticated.
- [ ] **(In Progress)** Google Cloud APIs & credentials — project exists, need to verify:
  - Gmail API enabled?
  - Cloud Pub/Sub API enabled?
  - OAuth 2.0 credentials created? (redirect URI: `http://localhost:5678/rest/oauth2-credential/callback`)
  - Pub/Sub topic `gmail-notifications` created?
  - `gmail-api-push@system.gserviceaccount.com` granted Pub/Sub Publisher on topic?
- [ ] **(Allan)** Slack app — create at https://api.slack.com/apps
  - Bot scopes needed: `chat:write`, `commands`, `im:write`, `chat:write.public`
  - Enable interactive messages (request URL: Cloudflare Tunnel URL + `/slack/interactions`)
  - Enable slash commands (request URL: tunnel URL + `/slack/commands`)
  - Install to Allan's workspace
  - Note: bot token, signing secret, app ID
- [ ] **(Allan)** Anthropic API key for production Claude Haiku 4.5 calls
  - Separate from the Claude Code key — this is for the running system
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

- [x] **(Done)** Supabase MCP configured in `.mcp.json` — **needs Claude Code restart to activate**
- [x] **(Done)** gcloud MCP configured in `.mcp.json` (project: `srad-493407`) — **needs Claude Code restart to activate**
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
| GOOGLE_CLIENT_ID | **Needed** — verify/create in Google Cloud Console |
| GOOGLE_CLIENT_SECRET | **Needed** — verify/create in Google Cloud Console |
| GOOGLE_PUBSUB_TOPIC | **Needed** — verify/create in Google Cloud Console |
| SLACK_BOT_TOKEN | Waiting on Slack app |
| SLACK_SIGNING_SECRET | Waiting on Slack app |
| ANTHROPIC_API_KEY | Waiting on Allan |
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

1. **Restart Claude Code** → activate Supabase + gcloud MCP servers
2. **Verify Google Cloud setup** via gcloud MCP (APIs enabled, OAuth creds, Pub/Sub topic)
3. **Create Slack app** and get bot token + signing secret
4. **Get Anthropic API key** for production
5. **Voice samples** (can defer to before Phase 2)
