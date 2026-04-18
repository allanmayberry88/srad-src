-- qFollow — Phase 2 CP9: workflow health tracking for error alerting
-- Tracks consecutive failures per workflow; Slack alert after 3 in a row.

begin;

create table if not exists workflow_health (
    workflow_name        text primary key,
    consecutive_failures integer not null default 0,
    last_failure_at      timestamptz,
    last_success_at      timestamptz,
    alerted_at           timestamptz
);

insert into workflow_health (workflow_name) values
  ('qfollow — quote-detection'),
  ('qfollow — slack-interactions'),
  ('qfollow — followup-scheduler'),
  ('qfollow — reply-checker'),
  ('qfollow — gmail-watch-renewal')
on conflict do nothing;

alter table workflow_health enable row level security;
create policy wh_no_anon on workflow_health for all to anon using (false);

commit;
