# qFollow — Learnings Log

Running log of non-obvious issues, gotchas, and "next time do X" notes captured during the build. At the end of each phase, promote cross-module items into the root `CLAUDE.md` Gotchas section.

Format: one entry per learning, newest at the top. Tag with phase + date.

---

## Phase 1 — 2026-04-15

### `$env` access is blocked in n8n by default
n8n 1.x throws "access to env vars denied" when expressions reference `$env.FOO`, even though the variable is passed into the container. Add `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` to the n8n container env (and recreate with `docker compose up -d --force-recreate n8n`). This is set in our `deploy/docker-compose.yml`.

### HTTP Request `jsonBody` is parsed as static JSON before expressions evaluate
Setting `jsonBody` to `={ "key": $json.value }` fails with "not valid JSON" because n8n validates the raw field as JSON *before* evaluating. Workarounds:
1. Wrap the whole body in a single expression that returns a string: `={{ JSON.stringify({ key: $json.value }) }}` — this is what `Update Cursor` and `Slack Confirm` use.
2. Or build the object in an upstream Code node and `JSON.stringify` it in the HTTP node — this is what `Classify (Haiku)` does (`Extract Email` emits `anthropicBody`).

Don't use JS template literals (backticks) in the raw `={...}` form — they aren't valid JSON syntax.

### Supabase REST returns an array; n8n HTTP node passes it through as a single item with array JSON
When `GET /rest/v1/tenants?email=eq.X` returns `[{...}]`, the HTTP node emits one item whose `json` is the array. **But** in n8n expressions, `$json` inside that downstream node is the *object* — the array is unwrapped by the expression engine for single-element arrays. Referencing `$json[0].field` silently returns undefined. Use `$json.field` directly. This bit us in `Tenant Found?`, `Gmail history.list`, `Update Cursor`, and `Slack Confirm`.

### Code nodes default to "Run Once for All Items"
In that mode, `$input.first().json` returns only the first input item — any fan-in from an upstream "split" is silently dropped. Set `parameters.mode: "runOnceForEachItem"` and use `$json` for per-item processing. We hit this on `Extract Email` and `Parse Classification`, which caused 6 of 7 exploded Gmail messages to be silently skipped.

### Gmail OAuth redirect URI must match the current webhook base URL
n8n computes its OAuth callback as `{WEBHOOK_URL}/rest/oauth2-credential/callback`. Every time the Cloudflare quick-tunnel URL changes, the OAuth Web Client's Authorized Redirect URIs list must include the new URL or Google returns "invalid request". Keep both `http://localhost:5678/...` and the current tunnel URL registered. Another reason to move to a named tunnel on `dev.srad.scot`.

### Pub/Sub push to `*.trycloudflare.com` works without domain verification
Google historically requires push-endpoint domains to be verified in Search Console. Creating `gmail-n8n-push` with a `trycloudflare.com` endpoint succeeded without the verification step (tested 2026-04-15). May not hold forever — if it fails later, verify `srad.scot` and use the named tunnel.

### Pub/Sub push subscription needs the workflow active before it can deliver
Obvious in hindsight: while the workflow is inactive, the production webhook URL returns 404. Push messages are retried for `message-retention-duration` (we set 10m) then dropped. Always activate the workflow *before* pointing Pub/Sub at it, or expect a silent backlog.

### Use Gmail's `history.list` response historyId as the cursor, not the notification's
The Pub/Sub push carries a `historyId` representing "a change happened at or after this point", but the notification can be stale relative to what's already in the mailbox. After a successful `history.list` call, write back `response.historyId` — that's the maximum point we've processed. Our `Update Cursor` node uses this with a fallback to the notification's id.

### The classifier is smart enough to flag self-sends
When Allan sent a test quote from `allan@srad.scot` to `allanmayberry@hotmail.com` (same person), Haiku correctly returned `is_quote: false` with the reason "recipient is the sender's own personal email address — self-directed communication". To exercise the positive Slack path during testing, send to a genuinely external recipient.

### Supabase migrations live at repo root, not per-module
The Supabase CLI expects a single `supabase/migrations/` folder per project. One Supabase project serves all Srad modules, so migrations are cross-module. Prefix filenames with the module name (e.g. `20260415120000_qfollow_initial.sql`) for clarity.

**`supabase migration repair --status applied <timestamp>`** is the escape hatch when a migration was applied out-of-band (e.g. via SQL editor). It records it in `supabase_migrations.schema_migrations` without re-running. We used it once to reconcile the initial schema with the newly-linked CLI.

### Cloudflare quick tunnels give a new URL every restart
`cloudflared tunnel --url http://localhost:5678` (without a named tunnel) generates a throwaway `*.trycloudflare.com` subdomain. Every time the tunnel process restarts the URL changes, which breaks: Pub/Sub push subscription, Slack Interactivity/Commands URLs, and the `WEBHOOK_URL` baked into n8n at boot.

**Next time:** for dev this is acceptable (documented in README). For any longer-running dogfood we should register a named tunnel tied to a stable `dev.srad.scot` subdomain so restarts don't thrash external configs. Do before Phase 2 if it bites more than twice.

### n8n needs the webhook URL at process start, not just per-request
n8n bakes `WEBHOOK_URL` / `N8N_EDITOR_BASE_URL` into webhook registration when the process boots. Updating `.env` and restarting (`docker compose up -d --force-recreate`) is required — a plain `docker compose up -d` doesn't re-read env.

### Two separate "encryption keys" in play — don't confuse them
- `N8N_ENCRYPTION_KEY` — n8n's internal credential store encryption. Must be stable across n8n restarts or stored credentials become unreadable.
- `TOKEN_ENCRYPTION_KEY` — app-level, used by `scripts/token_crypto.py` to encrypt OAuth refresh tokens we store in `tenants.oauth_token_enc`.

Both live in `.env`, both are 32-byte hex. Losing either = re-auth everything.

---

<!-- Add new entries above this line, newest first. -->
