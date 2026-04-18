# qFollow — Learnings Log

Running log of non-obvious issues, gotchas, and "next time do X" notes captured during the build. At the end of each phase, promote cross-module items into the root `CLAUDE.md` Gotchas section.

Format: one entry per learning, newest at the top. Tag with phase + date.

---

## Phase 1 — 2026-04-18 (checkpoint 6)

## Phase 1 — 2026-04-18 (checkpoint 7)

### Boolean IF conditions need `singleValue: true` for unary operators
When creating an IF node via MCP with a boolean check like `$json.hasReply == true`, the operator must use `"operation": "true"` with `"singleValue": true` and no `rightValue`. Without `singleValue`, the node validation fails. This applies to all unary operators: `true`, `false`, `empty`, `notEmpty`.

### Gmail `threads.get` with `format=metadata` is lightweight for reply checking
Use `format=metadata&metadataHeaders=From,To` to get just the headers needed for reply detection without downloading full message bodies. Each message in the thread includes `payload.headers` with the From field, which can be compared against the stored `recipient_email`.

---

### Switch node v3 requires `conditions.options` in every rule
When creating a Switch node via MCP, each rule's `conditions` object must include `"options": {"caseSensitive": true, "typeValidation": "loose"}`. Without this, the node crashes at runtime with `Cannot read properties of undefined (reading 'caseSensitive')`. The auto-sanitizer is supposed to add this but doesn't reliably do so for Switch rules — always include it explicitly.

### n8n partial update: use `source`/`target` for connections, not `from`/`to`
The `n8n_update_partial_workflow` MCP tool uses `source` and `target` parameters for `addConnection` operations. Using `from`/`to` (which are used for `rewireConnection`) causes a "Missing required parameter 'source'" error. For Switch node outputs, use `case=N` (0-indexed); for IF node outputs, use `branch="true"/"false"`.

### Switch node replaces IF for multi-action routing
When a single webhook handles multiple action types (e.g., 6 different Slack button actions), replace the IF node with a Switch node (v3). Each case matches on `$json.action_id`. The Switch node supports named outputs via `renameOutput: true` + `outputKey`.

### Gmail `drafts.create` uses base64url-encoded RFC 2822
The Gmail API's `drafts.create` endpoint expects `{ message: { raw: "<base64url>" } }`. The raw value is a full RFC 2822 message (with To, Subject, Content-Type headers) encoded with `Buffer.from(msg, 'utf-8').toString('base64url')`. Include `threadId` in the message object to place the draft in the correct conversation thread.

---

## Phase 1 — 2026-04-18 (checkpoint 5)

### Tenant record must have `slack_team_id` set for interaction handler
The slack-interactions workflow looks up the tenant by `slack_team_id` (from the Slack interaction payload's `team.id`). The original seed script didn't set this field, causing the lookup to return 0 rows and silently stopping the workflow. Always seed `slack_team_id` when creating a tenant — it's required for any Slack interaction handling.

### Slack interactions use `response_url` for async updates
Slack expects a 200 response within 3 seconds of a button click. Use `responseMode: "responseNode"` on the webhook + a `Respond to Webhook` node to immediately return 200, then continue async processing. POST to the `response_url` (included in every interaction payload) with `replace_original: true` to swap the original message's buttons for a confirmation.

### Slack sends interactions as `application/x-www-form-urlencoded`
The payload is URL-encoded form data with a single `payload` field containing a JSON string — not a JSON body. In n8n, access it via `$json.body.payload` (or `$json.payload` depending on webhook version). Always `JSON.parse()` it in a Code node.

### Supabase POST with `Prefer: return=representation` returns an array
Even for a single-row INSERT, Supabase REST returns `[{row}]`. Due to n8n's expression auto-unwrapping (see earlier learning), downstream expressions can use `$json.id` directly, but Code nodes may receive the raw array — add `Array.isArray` guard when needed.

### Referencing upstream nodes across long chains works fine
`$('NodeName').item.json` can reference any ancestor node in the execution path, even many nodes back. Used extensively in the slack-interactions workflow to pull `response_url` from Parse Payload and extraction data from Parse Extraction at the final Ack node.

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
