# qFollow: Quote Follow-Up Automation — Implementation Plan

## Context

Allan is building the first automation module for his productised AI sprint business (Srad). This module ("qFollow") automates contextual follow-up on quotes/proposals sent from email. It's the first of many modules in `D:/Projects/srad-src/`, so the plan includes repo structure for cross-module learning. After 2 weeks of dogfooding, it deploys to paying UK SME customers.

## Decisions (resolved 2026-04-14)

1. **Draft-only** for V1 — approved, nothing auto-sends
2. **Always-confirm** quote detection — approved
3. **One quote per thread** even with multiple recipients — track as single quote
4. **Srad branding** for now — no white-labelling
5. **Domain:** `srad.scot` (also hosts corporate website) — use a subdomain e.g. `app.srad.scot` or `api.srad.scot` for OAuth redirects, webhooks, and approval links
6. **30-day default** validity if no explicit expiry detected in the email
7. **Single user per tenant for V1** — schema should accommodate multi-user later
8. **No CRM integration** — customers with CRMs likely have better tooling already
9. **Reopens 3+ alert** skipped for V1 (requires open tracking, deferred)
10. **OAuth integration model** confirmed — centralised infra, customer grants access
11. **Non-technical customer UX** is critical — OAuth flow and onboarding must be dead simple even though Srad does the initial config

---

## 0. Cross-Project Conventions (to be codified in CLAUDE.md)

These apply to ALL Srad modules, not just qFollow:

### Progress tracking & stop/start resilience
- Use Claude Code tasks to track progress within each build session
- Each phase/sub-task should be checkpointed — assume work will be interrupted and resumed in a new conversation
- CLAUDE.md and memory files are the continuity mechanism between sessions
- Update CLAUDE.md after completing each phase with what was built, what's next, and any gotchas discovered

### Build and deploy as we go
- Every phase must end with something deployable and testable — no "big bang" integration
- Phase 1 deploys to the real VPS and processes real emails, even if rough
- Each subsequent phase deploys incrementally on top

### Automated testing
- **Unit tests:** For all LLM prompt logic (mock the API, test parsing of responses), state transitions, and utility functions
- **Integration tests:** For n8n workflows — test the full flow with mock email data against real Supabase
- **E2E tests:** At least one per phase — send a test email, verify the full pipeline produces a Slack message and email draft
- Test framework: pytest for Python scripts, n8n's built-in test mode for workflows
- Tests run before every deploy; broken tests block deployment

### Fail/retry loop
- All n8n workflows must have error handling with configurable retry (3 retries, exponential backoff)
- Dead-letter logging: failed workflow executions logged to a Supabase `error_log` table with full context
- Alert via Slack if any workflow fails 3 consecutive times
- Never silently swallow errors — every failure must be visible

### Model selection for coding
- **Haiku** for straightforward code generation (prompts, simple scripts, config files, tests)
- **Sonnet** for moderate complexity (n8n workflow logic, integration code, debugging)
- **Opus** only when stuck on a tricky reasoning problem — escalate, don't default to it
- This applies to Claude Code's own model usage during the build, not the production LLM calls

---

## 0.1 Prerequisites & Setup Checklist

Complete these BEFORE starting Phase 1 code:

### Accounts & services to provision
- [ ] **Hetzner Cloud account** — create CX22 VPS (Falkenstein or Helsinki)
- [ ] **Supabase account** — create Pro project, note project URL and API keys
- [ ] **Google Cloud project** — enable Gmail API, Pub/Sub API; create OAuth 2.0 credentials (web app type, redirect URI: `https://app.srad.scot/auth/google/callback`)
- [ ] **Slack app** — create at api.slack.com, configure bot scopes (`chat:write`, `commands`, `im:write`), interactive messages request URL
- [ ] **Anthropic API key** — for Claude Haiku 4.5 production calls
- [ ] **DNS** — create `app.srad.scot` and `api.srad.scot` A records pointing to VPS IP

### Local dev environment
- [ ] **Git repo initialised** in `D:/Projects/srad-src/` with `.gitignore`
- [ ] **Python 3.11+** available (for scripts)
- [ ] **Docker** available locally (for testing docker-compose before deploy)
- [ ] **n8n CLI** installed locally for workflow development/export

### MCP servers & Claude Code setup
- [ ] **Supabase MCP** — connect so Claude Code can query/inspect the database directly during development
- [ ] **GitHub MCP** or git setup — for commits and PR management
- [ ] **Slack MCP** (if available) — for testing Slack message posting during development
- [ ] Review whether an **n8n MCP** exists or if we interact via API/CLI

### CLAUDE.md creation (first task in Phase 1)
Create `D:/Projects/srad-src/CLAUDE.md` with:
- Project overview and module index
- Cross-project conventions from this section
- Testing requirements
- Model selection guidance
- Deployment checklist patterns
- Error handling standards

---

## 1. Architecture Overview

```
                            qFollow — DATA FLOW
                            ======================

 OUTBOUND QUOTE                                                    FOLLOW-UP
 (user sends from                                                  (draft lands in
  Gmail or Outlook)                                                 user's Drafts)
       |                                                                ^
       v                                                                |
 +------------------+     +-------------------+     +------------------+
 | EMAIL PROVIDER   |     |   ORCHESTRATOR    |     |  EMAIL PROVIDER  |
 |                  |     |   (n8n on VPS)    |     |                  |
 | Gmail: watch()   |---->|                   |---->| Gmail: drafts.   |
 |  + Pub/Sub       |     | 1. Receive notif  |     |   create()       |
 |  + history.list  |     | 2. Fetch message  |     | M365: POST       |
 |                  |     | 3. Classify quote  |     |   /messages      |
 | M365: Graph API  |---->| 4. Extract fields |     |   (isDraft=true) |
 |  subscriptions   |     | 5. Store state    |     +------------------+
 |  /messages       |     | 6. Schedule f/ups |
 +------------------+     +---------+---------+
                                    |
                          +---------+---------+
                          |                   |
                    +-----v-----+   +---------v---------+
                    | SUPABASE  |   |  LLM (Claude API) |
                    | (Postgres)|   |  Haiku 4.5        |
                    |           |   |                   |
                    | - quotes  |   | - classify quote  |
                    | - events  |   |   (subject+body)  |
                    | - f/ups   |   | - extract fields  |
                    | - config  |   | - draft follow-up |
                    | - voice   |   |   in user's voice |
                    +-----------+   +-------------------+
                          |
                    +-----v-----------+
                    | SLACK APP       |
                    | (Block Kit msg) |
                    |                 |
                    | - Show draft    |
                    | - Approve/Edit/ |
                    |   Reject        |
                    | - "Call them"   |
                    |   alert         |
                    +-----------------+
```

**Google Workspace path:** Gmail `watch(labelIds:["SENT"])` → Cloud Pub/Sub → n8n webhook. **Important:** `labelIds` filter is buggy (Google Issue #36759803) — must filter client-side via `history.list(historyTypes:["messageAdded"], labelId:"SENT")`.

**Microsoft 365 path:** Graph API `POST /subscriptions` on `me/mailFolders('SentItems')/messages`, changeType `created` → webhook to n8n.

**Cron jobs (n8n scheduled triggers):**
- Every 6h: renew Gmail watch (must renew within 7 days)
- Every 15m: check for due follow-ups
- Every 15m: check for reply-based stop conditions

**Key decisions:**
- n8n is the single orchestration layer; both email paths converge into the same downstream flow
- LLM called via direct API from n8n (HTTP Request node), no wrapper service
- Follow-ups created as **drafts in the user's email client**, never sent directly — strongest possible human-in-the-loop guarantee
- Supabase accessed via REST API from n8n

---

## 2. Stack Recommendation with Alternatives

| Component | Recommended | Rejected Alternative | Why |
|-----------|------------|---------------------|-----|
| **Orchestration** | n8n self-hosted on Hetzner VPS (CX22, ~€4.50/mo) | Make.com | Operation-based billing ~$16-29/mo/customer; n8n is free self-hosted |
| **LLM** | Claude Haiku 4.5 ($1/$5 per M tokens) | Claude Sonnet 4.6 | 3x cost, no quality gain for these tasks (~$0.07/mo/customer) |
| **State storage** | Supabase Pro ($25/mo shared) | Self-hosted Postgres | Loses managed backups, REST API, dashboard; not worth saving $25 |
| **Approval UI** | Slack Bot + Block Kit | Custom web dashboard | Would consume 4-6h of budget; Slack does it better |
| **Email fallback** | Email with signed approve/edit/reject links | None | Needed for non-Slack customers |
| **Tracking (V1)** | Reply detection only | Tracking pixels | Apple Mail Privacy Protection makes open tracking unreliable; PECR consent required |
| **Deployment** | Single Hetzner CX22 VPS with Docker | AWS/GCP | Overkill pricing for this workload |

### Steady-state cost per customer (at 10 customers)

| Item | Monthly | Notes |
|------|---------|-------|
| VPS (shared) | ~£0.40 | €4.50/mo total |
| Supabase (shared) | ~£2.00 | $25/mo total |
| Claude API | ~£0.06 | 4 quotes/week |
| Slack / Email APIs | £0.00 | Included |
| **Total** | **~£2.50/customer** | Well under £20 ceiling |

---

## 3. Quote-Detection Problem

### Approaches analysed

| Approach | Precision | Recall | Friction | Works for M365? |
|----------|-----------|--------|----------|-----------------|
| A. LLM classifier on subject+body | ~85-90% | ~85-90% | Zero | Yes |
| B. User-applied Gmail label | 100% | ~60-70% (forgets) | Medium | No (no equivalent) |
| C. BCC to `track@srad.scot` | 100% | ~60-70% (forgets) | Medium | Yes |
| **D. Hybrid: LLM + Slack confirmation** | **100%** | **~90%+** | **~2 seconds** | **Yes** |

### Recommendation: Approach D (Hybrid)

LLM classifies all sent emails. On probable quote detection, pings Slack: *"I think you just sent a quote to [recipient] for [amount]. Track this? [Yes/No]"*. User confirms in 2 seconds. Also add a `/srad track` Slack command to manually flag anything the LLM missed.

**Why not fully automatic:** One false positive triggering follow-ups to the wrong person (e.g., an internal pricing discussion) would damage credibility. The 2-second confirmation is non-negotiable.

**V1 tuning:** Start with a conservative prompt (high precision, lower recall). Tune over time based on accumulated true/false positive data.

---

## 4. Tracking Problem

### V1: Reply detection only

Check via Gmail `history.list` or Graph API on a 15-minute cron whether the recipient has replied to the tracked thread. This is:
- 100% reliable
- Legally clean (checking your own mailbox, no consent needed)
- Sufficient to trigger stop-condition logic

### Deferred

| Method | Issue | Defer to |
|--------|-------|----------|
| Tracking pixels | Apple Mail pre-fetches (false opens), Gmail caches, ~40-60% unreliable | Phase 5+ |
| Link tracking | Changes visible URLs (suspicious), requires PECR consent | Phase 5+ |
| Hosted PDF pages | Changes quote delivery workflow; best as "Srad proposals" feature | Phase 5+ |

**GDPR/PECR note:** Under UK PECR, tracking pixels and link redirects require prior consent (same regime as cookies). ICO can fine up to £17.5M. Not worth the legal risk in V1 when reply detection covers the core use case.

**Consequence:** The "reopened 3+ times → call alert" feature cannot ship in V1 (requires open tracking). The schema supports it so it can be switched on later without migration.

---

## 5. Voice/Tone Problem

### V1 approach: Few-shot prompting with style extraction

**Step 1 — Onboarding:** Collect 10-20 sample emails (3-5 formal quotes, 3-5 casual follow-ups, 3-5 general business emails). Store in `voice_samples` table.

**Step 2 — Style extraction (one-time):** Run Sonnet 4.6 (harder task than classification) to produce a structured style guide:
- Greeting style, sign-off, sentence length, contractions, typical phrases
- Formality level (1-5), exclamation marks, specificity preference
- Stored as JSON in `tenants.style_guide`

**Step 3 — Generation:** System prompt includes: style guide + 3 most relevant sample emails + quote context. Haiku 4.5 generates the draft.

**Step 4 — Feedback loop:** When user edits a draft before approving, store original + edited. After 10+ edits, re-run style extraction to refine.

### Stage-specific tone

- **Day 3:** Casual, brief — "Just checking this landed in your inbox"
- **Day 7:** More substantive — reference specific item, offer to answer questions
- **Day 14:** More direct — reference validity period, suggest a call

Each stage has a separate prompt template referencing the same style guide.

### Rejected: Fine-tuning

Not feasible with 10-20 emails (need thousands). Maintenance burden (re-fine-tune per customer, per model update) not justified.

---

## 6. State Model

```sql
-- Multi-tenant: all tables have tenant_id, enforced by RLS

CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    email_provider  TEXT NOT NULL CHECK (email_provider IN ('google', 'microsoft')),
    oauth_token_enc TEXT,
    slack_team_id   TEXT,
    slack_channel   TEXT,
    slack_bot_token_enc TEXT,
    style_guide     JSONB,
    followup_days   INTEGER[] DEFAULT '{3,7,14}',
    timezone        TEXT DEFAULT 'Europe/London',
    active          BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE voice_samples (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email_type  TEXT CHECK (email_type IN ('quote','followup','general')),
    subject     TEXT,
    body        TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE quotes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    provider_msg_id TEXT NOT NULL,
    thread_id       TEXT,
    recipient_email TEXT NOT NULL,
    recipient_name  TEXT,
    subject         TEXT NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL,
    proposed_items  JSONB,        -- [{description, qty, unit_price, line_total}]
    total_amount    NUMERIC(10,2),
    currency        TEXT DEFAULT 'GBP',
    valid_until     DATE,                 -- default: sent_at + 30 days if not extracted
    summary         TEXT,         -- LLM-generated plain English summary
    status          TEXT DEFAULT 'active' CHECK (status IN (
                        'pending_confirmation', 'active', 'replied',
                        'won', 'lost', 'expired', 'stopped'
                    )),
    stopped_reason  TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE engagement_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id    UUID REFERENCES quotes(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL CHECK (event_type IN (
                    'reply_detected', 'open', 'link_click', 'manual_note'
                )),
    occurred_at TIMESTAMPTZ DEFAULT now(),
    metadata    JSONB
);

CREATE TABLE followups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id        UUID REFERENCES quotes(id) ON DELETE CASCADE,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL CHECK (stage IN ('day3','day7','day14','custom')),
    scheduled_for   TIMESTAMPTZ NOT NULL,
    draft_subject   TEXT,
    draft_body      TEXT,
    status          TEXT DEFAULT 'pending' CHECK (status IN (
                        'pending', 'draft_ready', 'sent_to_slack',
                        'approved', 'edited', 'rejected', 'skipped', 'cancelled'
                    )),
    slack_msg_ts    TEXT,
    user_edits      TEXT,
    decided_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE call_alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id    UUID REFERENCES quotes(id) ON DELETE CASCADE,
    tenant_id   UUID REFERENCES tenants(id) ON DELETE CASCADE,
    reason      TEXT NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT now(),
    acknowledged BOOLEAN DEFAULT false
);

-- Key indexes
CREATE INDEX idx_quotes_tenant_status ON quotes(tenant_id, status);
CREATE INDEX idx_quotes_thread ON quotes(thread_id);
CREATE INDEX idx_followups_due ON followups(scheduled_for, status) WHERE status = 'pending';
CREATE INDEX idx_followups_quote ON followups(quote_id);
CREATE INDEX idx_engagement_quote ON engagement_events(quote_id);

-- RLS enabled on all tables
```

**Notes:** `followup_days` on tenant allows per-customer cadence. `proposed_items` as JSONB avoids a separate line-items table. OAuth tokens stored encrypted (AES-256 with env var key for V1). **Multi-user note:** V1 stores OAuth token on the tenant (single user). When multi-user support is needed, extract a `tenant_users` table with per-user OAuth tokens and link quotes/followups to the user who sent them.

---

## 7. Approval UX

### Slack message when a draft is ready

```
┌─────────────────────────────────────────────┐
│ 📧 Follow-up Ready for Approval             │
├─────────────────────────────────────────────┤
│ Quote to: Jane Smith (jane@acme.co.uk)      │
│ Amount:   £4,200                            │
│ Sent:     7 days ago (7 Apr)                │
│ Stage:    Day 7 follow-up                   │
├─────────────────────────────────────────────┤
│ Subject: Re: AI Sprint Proposal — Acme Ltd  │
│                                             │
│ Draft:                                      │
│ Hi Jane,                                    │
│                                             │
│ Just wanted to check in on the sprint       │
│ proposal I sent over last week. I know the  │
│ data migration piece can feel like a big     │
│ decision — happy to jump on a quick call if  │
│ it would help to talk through the approach.  │
│                                             │
│ The proposal is valid until 21 April, so no  │
│ rush, but wanted to make sure you had        │
│ everything you needed.                       │
│                                             │
│ Cheers,                                     │
│ Allan                                       │
├─────────────────────────────────────────────┤
│ [✅ Approve & Create Draft] [✏️ Edit]        │
│ [❌ Reject] [🏆 Mark Won] [🚫 Mark Lost]    │
└─────────────────────────────────────────────┘
```

### Action behaviours

| Action | What happens |
|--------|-------------|
| **Approve** | Creates draft in Gmail/Outlook (not sent). Slack msg updates to "Approved — draft created in your inbox". User must open email client and hit Send. |
| **Edit** | Opens Slack modal pre-populated with draft. User edits, submits. Edited version saved, then same draft-creation flow. |
| **Reject** | Follow-up marked rejected. Subsequent follow-ups for this quote remain active. |
| **Mark Won/Lost** | Quote status updated. All pending follow-ups cancelled. |

### "Needs personal call" alert (requires tracking — Phase 3+)

```
┌─────────────────────────────────────────────┐
│ 📞 Hot Lead — Consider a Personal Call      │
├─────────────────────────────────────────────┤
│ Jane Smith (jane@acme.co.uk) has reopened   │
│ your £4,200 proposal 3 times in the last    │
│ 48 hours without replying.                  │
│                                             │
│ This usually means they're interested but   │
│ have a blocker. A quick call might close it.│
├─────────────────────────────────────────────┤
│ [✅ Got it]                                  │
└─────────────────────────────────────────────┘
```

### Email fallback (non-Slack customers)

Email with draft as blockquote + three links (approve/edit/reject) hitting n8n webhooks with HMAC-SHA256 signed tokens (48h expiry). Edit opens a minimal single-textarea web page on the VPS.

---

## 8. Build Phases

### Phase 0: Prerequisites & Foundation (1–2 hours)

**Goal:** All accounts provisioned, CLAUDE.md created, repo initialised, MCP servers connected, ready to build.

- Provision Supabase project (free tier for dev), Google Cloud project, Slack app (0.5h)
- Set up Cloudflare Tunnel or ngrok to expose local Docker to internet (0.25h)
- Init git repo, `.gitignore`, `CLAUDE.md`, directory structure (0.25h)
- Connect MCP servers (Supabase, GitHub) and verify Claude Code can query them (0.25h)
- Collect 10 of Allan's sample emails for voice extraction (0.25h)

**Checkpoint:** `CLAUDE.md` exists, git repo initialised, all external accounts accessible.

**Note:** Dev/dogfood runs locally in Docker. Hetzner VPS + DNS deferred to pre-customer deployment.

### Phase 1: Thinnest End-to-End Slice (5–6 hours)

**Goal:** Allan sends a real quote from Gmail → system detects it → extracts info → waits 3 days → drafts follow-up → posts to Slack → on approval creates draft in Gmail. Running locally in Docker by end of phase.

- Local setup: docker-compose with n8n, Cloudflare Tunnel for webhooks (0.5h)
- Supabase schema migration + RLS policies (0.5h)
- Google Cloud: Gmail API + Pub/Sub OAuth, configure watch on SENT (1h)
- n8n workflow 1: Pub/Sub webhook → fetch message → filter SENT → classify (Haiku) → Slack confirmation → extract fields → store → schedule follow-ups (1.5h)
- n8n workflow 2: cron 15min → query due follow-ups → draft with Haiku (voice samples in prompt) → Slack approval → on approve, create Gmail draft (1.5h)
- n8n workflow 3: cron 15min → check replies on active threads → update status, cancel follow-ups (0.5h)
- **Tests:** Unit tests for LLM response parsing, integration test for quote detection flow, E2E test with real email (included in above timings)
- **Test** end-to-end with a real quote email (running locally via Docker + tunnel)

**Checkpoint:** Working system for Allan on Gmail + Slack, running locally. Update CLAUDE.md with learnings.

### Phase 2: Harden and Polish (3–4 hours)

- Error handling: retries (3x exponential backoff), dead-letter `error_log` table, Slack failure alerts (1h)
- Gmail watch auto-renewal (cron every 6h) (0.25h)
- `/srad track` Slack command for manual tracking (0.5h)
- `/srad status` Slack command for active quotes overview (0.5h)
- Quote expiry detection (auto-mark expired after 30 days default) (0.25h)
- Edge cases: email threads, multiple recipients, re-sent quotes (0.5h)
- **Tests:** Integration tests for error/retry paths, Slack command tests
- **Deploy** incremental update (still local Docker for dogfood)
- *2-week dogfood period begins*

**Checkpoint:** Production-hardened system running locally. Update CLAUDE.md with error handling patterns.

**Note:** Migrate to Hetzner VPS at end of dogfood / before first customer. This is a straightforward docker-compose transplant + DNS setup.

### Phase 3: Microsoft 365 Support (2–3 hours)

- Azure AD app registration, Graph API permissions (0.5h)
- n8n workflow: Graph subscription webhook → same downstream flow (1h)
- Graph API draft creation (0.5h)
- Test with real M365 tenant (0.5h)
- Abstract email provider interface in n8n (0.5h)

### Phase 4: Multi-Customer Readiness (2 hours)

- Tenant onboarding script: create record, OAuth flow, store tokens (0.5h)
- Per-tenant voice sample collection + style extraction (0.5h)
- Email fallback approval flow for non-Slack customers (0.75h)
- Customer-facing setup guide + internal deployment runbook (0.25h)

**Total: 13–17 hours across 5 phases (Phase 0–4).** Phase 0 can partly overlap with Phase 1.

### Phase 5+ (post-launch, not in initial budget)

- Open/click tracking (if legally cleared)
- "Hot lead" call alerts
- Web dashboard for quote pipeline
- Analytics: conversion rates, response times
- Srad-hosted proposal pages

---

## 9. Per-Customer Deployment Checklist

### UX priority: non-technical customers

These are small UK professional services firms — solicitors, accountants, consultants. The people granting OAuth and installing the Slack app may not be technical. Even though Srad does the initial config, every customer-facing step must be:
- A single "click this link" with clear plain-English explanation of what they're granting
- No jargon (not "OAuth", say "sign in with Google to give qFollow permission to read your sent emails")
- A branded, professional-looking consent page at `app.srad.scot` (not a raw Google/Microsoft consent screen if avoidable — though V1 will use the standard consent screen with clear naming)

### What's needed from the customer

1. Email provider confirmed (Google Workspace or M365)
2. OAuth grant — customer clicks a link at `app.srad.scot/connect`, signs in with Google/M365, grants permissions. Plain-English scope descriptions.
3. Slack workspace access (install Srad app via a single "Add to Slack" button, designate notification channel)
4. 10–20 sample emails (mix of quotes, follow-ups, general business)
5. Follow-up cadence preferences (default: day 3/7/14)
6. Timezone (default: Europe/London)
7. Quote identification hints (keywords, subject patterns)

### Deployment steps (~3 hours + 30-60min buffer)

| Step | Time | What |
|------|------|------|
| 1 | 5 min | Create tenant record in Supabase |
| 2 | 15 min | Run OAuth flow with customer |
| 3 | 15 min | Configure email watch/subscription |
| 4 | 30 min | Ingest voice samples, run style extraction |
| 5 | 45 min | Review style guide, generate test follow-ups, tune with customer |
| 6 | 15 min | Configure Slack app, test approval message |
| 7 | 30 min | End-to-end test: send test quote → detect → draft → approve → draft created |
| 8 | 15 min | Activate tenant, set up monitoring |
| 9 | 30 min | Buffer for troubleshooting |

---

## 10. Risks and Failure Modes

### 1. Gmail watch() labelIds filter is buggy

**Detail:** Well-documented bug (Google Issue #36759803) — watch() ignores `labelIds` and fires for ALL mailbox changes.

**Mitigation:** Don't rely on `labelIds`. Accept all notifications, filter client-side via `history.list(startHistoryId, labelId="SENT", historyTypes=["messageAdded"])`. One extra API call per notification, completely reliable.

### 2. OAuth token expiry / revocation

**Detail:** Google refresh tokens can be revoked, expire after 6 months unused, or hit the 100-token limit. M365 tokens have similar characteristics. Silent failure = system stops working.

**Mitigation:** Daily health-check cron (`users.getProfile` / `GET /me`) per tenant. Alert via Slack on failure. "Dead man's switch" — if no quotes detected for 14 days, ping Allan to verify connection vs. customer just not sending quotes.

### 3. LLM hallucinates quote details in follow-up

**Detail:** LLM might invent a price, line item, or feature. If user approves without reading carefully, misleading email goes out.

**Mitigation:** (a) Draft-in-email-client forces one more read before send. (b) Slack message shows original quote summary alongside draft for comparison. (c) System prompt instructs: "Do not invent details. If unsure, use vague language like 'the proposal I sent over'." (d) V1 follow-ups are deliberately brief/vague rather than detailed.

### 4. Email API rate limits

**Detail:** Gmail: 250 quota units/sec, daily sending limit. Graph: 10,000 req/10min/app. Steady-state load is negligible but high-volume emailers could trigger many notifications.

**Mitigation:** Batch `history.list` calls (all changes since last historyId in one call). Exponential backoff. At current scale (even 50 customers), unlikely to hit limits.

### 5. Customer data isolation failure

**Detail:** Bug in RLS or missing `tenant_id` filter could leak one customer's quotes to another's Slack.

**Mitigation:** (a) Supabase RLS enforces isolation at DB level — even buggy app code can't cross tenants. (b) All n8n workflows pass `tenant_id` explicitly. (c) Phase 2: integration test that verifies cross-tenant access fails.

---

## 11. Open Questions — All Resolved

All questions resolved on 2026-04-14. See "Decisions" section at top of plan. No blockers remain for Phase 1.

---

## Proposed Directory Structure

```
D:/Projects/srad-src/
├── CLAUDE.md                    # Cross-module conventions and patterns
├── README.md                    # Repo overview, module index
├── .gitignore
├── shared/
│   ├── prompts/                 # Shared LLM prompt templates
│   │   └── style-extraction.md
│   ├── schemas/                 # Common DB patterns
│   │   └── common-columns.sql
│   └── docs/
│       ├── oauth-patterns.md    # Google + M365 OAuth learnings
│       ├── n8n-conventions.md
│       └── deployment.md
│
└── qfollow/                   # Quote follow-up automation
    ├── README.md
    ├── PLAN.md                  # Frozen copy of this plan
    ├── db/
    │   ├── migrations/
    │   │   └── 001_initial_schema.sql
    │   └── seed/
    │       └── sample_voice_data.sql
    ├── n8n/
    │   ├── workflows/
    │   │   ├── quote-detection.json
    │   │   ├── followup-scheduler.json
    │   │   ├── reply-checker.json
    │   │   ├── gmail-watch-renewal.json
    │   │   └── health-check.json
    │   └── credentials/         # .gitignored
    ├── prompts/
    │   ├── classify-quote.md
    │   ├── extract-fields.md
    │   ├── draft-followup-day3.md
    │   ├── draft-followup-day7.md
    │   └── draft-followup-day14.md
    ├── scripts/
    │   ├── onboard-tenant.py
    │   ├── extract-voice.py
    │   └── health-check.py
    ├── slack/
    │   ├── manifest.yaml
    │   └── block-templates/
    │       ├── approval-message.json
    │       ├── call-alert.json
    │       └── quote-confirmed.json
    └── deploy/
        ├── docker-compose.yml
        ├── .env.example
        └── nginx.conf
```

**Repo root `shared/`** holds anything the next module would reuse: OAuth patterns, n8n conventions, style extraction prompt, common DB column patterns.

**`CLAUDE.md` at root** updated after each module with naming conventions, error handling patterns, prompt structure, testing patterns — institutional memory for faster subsequent modules.

---

## Verification Plan

After Phase 1 implementation:
1. Send a real quote email from Allan's Gmail
2. Verify Slack confirmation ping arrives within 2 minutes
3. Confirm the quote, verify extraction (recipient, amount, summary) in Supabase
4. Wait for (or manually trigger) the day-3 follow-up cron
5. Verify Slack approval message appears with contextual draft
6. Approve the draft, verify it appears in Gmail Drafts folder
7. Send a reply from a test account, verify follow-ups are cancelled
8. Test the `/srad track` manual command with a non-detected email
