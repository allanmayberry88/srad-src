# qFollow — Prerequisites Checklist

Complete all items before starting Phase 1 code. Items marked with (Allan) require manual action; items marked (Claude Code) can be done in-session.

## Accounts & Services

- [x] **(Deferred)** ~~Hetzner Cloud VPS~~ — not needed for dev/dogfood. Run n8n locally in Docker.
- [x] **(Done)** Cloudflare Tunnel — `cloudflared` installed (v2025.8.1). Run `cloudflared tunnel --url http://localhost:5678` to expose local n8n.
- [x] **(Done)** Supabase project — `https://frcokifutyygafyzspbt.supabase.co` (free tier, upgrade to Pro before customer deployments)
- [ ] **(Allan)** Google Cloud project
  - Enable Gmail API and Pub/Sub API
  - Create OAuth 2.0 credentials (web app type)
  - Set redirect URI to the Cloudflare Tunnel URL (will update once tunnel is running; for now use `http://localhost:5678/auth/google/callback`)
  - Create a Pub/Sub topic for Gmail notifications (e.g., `projects/<project-id>/topics/gmail-notifications`)
  - Grant `gmail-api-push@system.gserviceaccount.com` publish permissions on the topic
  - Note: client ID, client secret, project ID, Pub/Sub topic name
- [ ] **(Allan)** Slack app — create at https://api.slack.com/apps
  - Bot scopes needed: `chat:write`, `commands`, `im:write`, `chat:write.public`
  - Enable interactive messages (request URL: will be your Cloudflare Tunnel URL + `/slack/interactions`)
  - Enable slash commands (request URL: tunnel URL + `/slack/commands`)
  - Install to Allan's workspace
  - Note: bot token, signing secret, app ID
- [ ] **(Allan)** Anthropic API key for production Claude Haiku 4.5 calls
  - Separate from the Claude Code key — this is for the running system
- [x] **(Deferred)** ~~DNS A records~~ — not needed while running locally. Cloudflare Tunnel provides the public URL.

## Local Dev Environment

- [x] **(Done)** Git repo initialised with `.gitignore`
- [x] **(Done)** Python 3.14.3 available
- [x] **(Done)** Docker available (v29.2.1)
- [ ] **(Allan)** n8n — run via Docker (included in docker-compose.yml we'll create). No need to install n8n CLI separately.

## Git Config

- [ ] **(Allan)** Git user name and email not configured. Run:
  ```bash
  git config --global user.name "Your Name"
  git config --global user.email "your@email.com"
  ```

## MCP Servers & Claude Code Setup

- [x] **(Done)** Supabase MCP server configured in `.mcp.json` (will be active on next Claude Code restart)
- [ ] **(Allan)** Restart Claude Code in this project to activate Supabase MCP
- [x] **(Done)** n8n MCP exists — community server at `github.com/czlonkowski/n8n-mcp`. Can create/edit/validate workflows, search nodes, trigger execution. **Add to `.mcp.json` once n8n is running locally.**
- [ ] **(Allan)** Slack MCP — not critical for now; we can test Slack via n8n workflows directly

## Voice Samples

- [ ] **(Allan)** Collect 10-20 sent emails as voice/tone samples:
  - 3-5 formal quotes or proposals
  - 3-5 casual follow-up emails
  - 3-5 general business emails
  - Format: plain text (subject + body), one file per email or one consolidated file
  - Save to `qfollow/voice-samples/` (gitignored — these contain real customer data)

## Credentials Stored

`.env` file at `qfollow/deploy/.env` (gitignored):

| Credential | Status |
|-----------|--------|
| SUPABASE_URL | Done |
| SUPABASE_SERVICE_KEY | Done |
| SUPABASE_ANON_KEY | **Needed** — find in Supabase dashboard → Settings → API |
| GOOGLE_CLIENT_ID | Waiting on Google Cloud project |
| GOOGLE_CLIENT_SECRET | Waiting on Google Cloud project |
| GOOGLE_PUBSUB_TOPIC | Waiting on Google Cloud project |
| SLACK_BOT_TOKEN | Waiting on Slack app |
| SLACK_SIGNING_SECRET | Waiting on Slack app |
| ANTHROPIC_API_KEY | Waiting on Allan |
| TOKEN_ENCRYPTION_KEY | **Can generate now** |
| WEBHOOK_BASE_URL | Set when Cloudflare Tunnel starts |

## Summary — What Allan Needs to Do

1. **Git config** — set your name and email (`git config --global ...`)
2. **Google Cloud project** — create project, enable APIs, create OAuth creds, create Pub/Sub topic
3. **Slack app** — create app, configure scopes, install to workspace
4. **Anthropic API key** — generate a separate key for production LLM calls
5. **Supabase anon key** — grab from dashboard (Settings → API)
6. **Voice samples** — collect 10-20 sample emails into `qfollow/voice-samples/`
7. **Restart Claude Code** — to activate the Supabase MCP server

## Ready Check

Once all the above are done, Phase 1 starts with:
1. Generate encryption key and finalise `.env`
2. Create Supabase schema migration
3. Docker-compose with n8n + Cloudflare Tunnel
4. Wire up Gmail watch → n8n webhook pipeline
