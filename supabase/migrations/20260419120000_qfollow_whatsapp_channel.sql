-- WhatsApp as alternative approval channel (per-tenant config)
begin;

-- Tenant-level channel preference + WhatsApp contact number
alter table tenants
  add column if not exists approval_channel text not null default 'slack'
    check (approval_channel in ('slack', 'whatsapp')),
  add column if not exists whatsapp_phone_number text;

-- WhatsApp message ID for correlating approval replies (parallels slack_msg_ts)
alter table followups
  add column if not exists approval_msg_id text;

-- Extend followup status to include 'sent_to_whatsapp'
-- The inline CHECK from the initial migration has an auto-generated name;
-- drop all check constraints on status and recreate.
do $$
declare
  r record;
begin
  for r in
    select con.conname
    from pg_constraint con
    join pg_attribute att on att.attnum = any(con.conkey)
                         and att.attrelid = con.conrelid
    where con.conrelid = 'followups'::regclass
      and con.contype = 'c'
      and att.attname = 'status'
  loop
    execute format('alter table followups drop constraint %I', r.conname);
  end loop;
end $$;

alter table followups add constraint followups_status_check check (
  status in (
    'pending', 'draft_ready', 'sent_to_slack', 'sent_to_whatsapp',
    'approved', 'edited', 'rejected', 'skipped', 'cancelled'
  )
);

-- Register new workflow in health tracking
insert into workflow_health (workflow_name) values
  ('qfollow — whatsapp-interactions')
on conflict do nothing;

commit;
