-- qFollow — Phase 1 initial schema
-- Apply in Supabase SQL editor. Idempotent where possible.
-- All tables carry tenant_id; RLS enabled; n8n connects as service_role (bypasses RLS).

begin;

create extension if not exists "pgcrypto";

-- Tenants ---------------------------------------------------------------

create table if not exists tenants (
    id                  uuid primary key default gen_random_uuid(),
    name                text not null,
    email_address       text not null unique,                -- the mailbox we watch
    email_provider      text not null check (email_provider in ('google','microsoft')),
    oauth_token_enc     text,                                -- AES-GCM encrypted refresh token
    gmail_history_id    text,                                -- last-processed historyId
    gmail_watch_expires timestamptz,                         -- watch() renews every <=7 days
    slack_team_id       text,
    slack_channel       text,                                -- where approvals are posted
    slack_bot_token_enc text,                                -- encrypted bot token (V1: shared app, may be null)
    style_guide         jsonb,                               -- populated in Phase 2
    followup_days       integer[] not null default '{3,7,14}',
    timezone            text not null default 'Europe/London',
    active              boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

-- Voice samples (Phase 2 populates; schema now to avoid a later migration) ---

create table if not exists voice_samples (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid not null references tenants(id) on delete cascade,
    email_type  text check (email_type in ('quote','followup','general')),
    subject     text,
    body        text,
    created_at  timestamptz not null default now()
);

-- Quotes ----------------------------------------------------------------

create table if not exists quotes (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants(id) on delete cascade,
    provider_msg_id text not null,                           -- Gmail message id
    thread_id       text,                                    -- Gmail thread id
    recipient_email text not null,
    recipient_name  text,
    subject         text not null,
    sent_at         timestamptz not null,
    body_snippet    text,                                    -- first ~500 chars for later context
    proposed_items  jsonb,                                   -- [{description, qty, unit_price, line_total}]
    total_amount    numeric(10,2),
    currency        text default 'GBP',
    valid_until     date,                                    -- default sent_at + 30 days if not extracted
    summary         text,                                    -- LLM-generated plain-English summary
    status          text not null default 'active' check (status in (
                        'pending_confirmation', 'active', 'replied',
                        'won', 'lost', 'expired', 'stopped'
                    )),
    stopped_reason  text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (tenant_id, provider_msg_id)
);

-- Engagement events (replies in V1; opens/clicks Phase 5+) --------------

create table if not exists engagement_events (
    id          uuid primary key default gen_random_uuid(),
    quote_id    uuid not null references quotes(id) on delete cascade,
    tenant_id   uuid not null references tenants(id) on delete cascade,
    event_type  text not null check (event_type in (
                    'reply_detected', 'open', 'link_click', 'manual_note'
                )),
    occurred_at timestamptz not null default now(),
    metadata    jsonb
);

-- Follow-ups ------------------------------------------------------------

create table if not exists followups (
    id              uuid primary key default gen_random_uuid(),
    quote_id        uuid not null references quotes(id) on delete cascade,
    tenant_id       uuid not null references tenants(id) on delete cascade,
    stage           text not null check (stage in ('day0','day3','day7','day14','custom')),
    scheduled_for   timestamptz not null,
    draft_subject   text,
    draft_body      text,
    status          text not null default 'pending' check (status in (
                        'pending', 'draft_ready', 'sent_to_slack',
                        'approved', 'edited', 'rejected', 'skipped', 'cancelled'
                    )),
    slack_msg_ts    text,
    user_edits      text,
    gmail_draft_id  text,                                    -- populated on approve
    decided_at      timestamptz,
    created_at      timestamptz not null default now()
);

-- Error log (populated Phase 2; table here so n8n workflows can write from day one) ---

create table if not exists error_log (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid references tenants(id) on delete set null,
    workflow    text,
    node        text,
    error_msg   text,
    context     jsonb,
    occurred_at timestamptz not null default now()
);

-- Indexes ---------------------------------------------------------------

create index if not exists idx_quotes_tenant_status   on quotes(tenant_id, status);
create index if not exists idx_quotes_thread          on quotes(thread_id);
create index if not exists idx_followups_due          on followups(scheduled_for, status) where status = 'pending';
create index if not exists idx_followups_quote        on followups(quote_id);
create index if not exists idx_engagement_quote       on engagement_events(quote_id);
create index if not exists idx_tenants_email          on tenants(email_address);

-- Row-Level Security ----------------------------------------------------
-- n8n connects via service_role which bypasses RLS. Policies exist so that
-- if we ever add a customer-facing web layer using the anon key, isolation
-- is enforced at the DB.

alter table tenants            enable row level security;
alter table voice_samples      enable row level security;
alter table quotes             enable row level security;
alter table engagement_events  enable row level security;
alter table followups          enable row level security;
alter table error_log          enable row level security;

-- Deny-all for anon (no customer-facing reads in Phase 1)
do $$
begin
    if not exists (select 1 from pg_policies where policyname = 'tenants_no_anon' and tablename = 'tenants') then
        create policy tenants_no_anon on tenants            for all to anon using (false);
        create policy voice_no_anon on voice_samples        for all to anon using (false);
        create policy quotes_no_anon on quotes              for all to anon using (false);
        create policy events_no_anon on engagement_events   for all to anon using (false);
        create policy followups_no_anon on followups        for all to anon using (false);
        create policy errorlog_no_anon on error_log         for all to anon using (false);
    end if;
end
$$;

-- updated_at triggers ---------------------------------------------------

create or replace function set_updated_at() returns trigger as $$
begin
    new.updated_at = now();
    return new;
end
$$ language plpgsql;

drop trigger if exists trg_tenants_updated on tenants;
create trigger trg_tenants_updated before update on tenants
    for each row execute function set_updated_at();

drop trigger if exists trg_quotes_updated on quotes;
create trigger trg_quotes_updated before update on quotes
    for each row execute function set_updated_at();

commit;
