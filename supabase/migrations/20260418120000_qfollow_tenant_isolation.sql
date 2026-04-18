-- qFollow — Phase 2: cross-table tenant consistency triggers
-- Ensures followups and engagement_events always match their parent quote's tenant_id.
-- Defence-in-depth: n8n workflows also filter by tenant_id, but the DB catches bugs.

begin;

-- followups.tenant_id must match quotes.tenant_id for the referenced quote_id
create or replace function check_followup_tenant_match()
returns trigger as $$
begin
  if new.quote_id is not null and
     (select tenant_id from quotes where id = new.quote_id) is distinct from new.tenant_id then
    raise exception 'tenant_id mismatch: followup tenant_id (%) does not match quote tenant_id for quote_id (%)',
      new.tenant_id, new.quote_id;
  end if;
  return new;
end
$$ language plpgsql;

drop trigger if exists trg_followup_tenant_check on followups;
create trigger trg_followup_tenant_check
  before insert or update on followups
  for each row execute function check_followup_tenant_match();

-- engagement_events.tenant_id must match quotes.tenant_id for the referenced quote_id
create or replace function check_engagement_tenant_match()
returns trigger as $$
begin
  if new.quote_id is not null and
     (select tenant_id from quotes where id = new.quote_id) is distinct from new.tenant_id then
    raise exception 'tenant_id mismatch: engagement_event tenant_id (%) does not match quote tenant_id for quote_id (%)',
      new.tenant_id, new.quote_id;
  end if;
  return new;
end
$$ language plpgsql;

drop trigger if exists trg_engagement_tenant_check on engagement_events;
create trigger trg_engagement_tenant_check
  before insert or update on engagement_events
  for each row execute function check_engagement_tenant_match();

commit;
