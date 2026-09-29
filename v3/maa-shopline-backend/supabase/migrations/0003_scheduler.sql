-- 0003: pg_cron -> pg_net -> Render /internal/jobs/drain  (Supabase only).
-- pg_cron runs SQL, not Python; it only *triggers* the drain endpoint.
-- Before applying, store two Vault secrets in the Supabase dashboard:
--   drain_url    = https://<render-service>/internal/jobs/drain
--   drain_secret = same value as Render env DRAIN_SECRET
-- No URL or secret is hard-coded here.
create extension if not exists pg_cron;
create extension if not exists pg_net;

create or replace function app_trigger_drain() returns bigint
language sql security definer set search_path = public as $$
  select net.http_post(
    url     := (select decrypted_secret from vault.decrypted_secrets where name = 'drain_url'),
    headers := jsonb_build_object(
                 'Content-Type','application/json',
                 'Authorization','Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'drain_secret')),
    body    := '{"source":"pg_cron"}'::jsonb,
    timeout_milliseconds := 60000              -- tolerates Render cold start
  );
$$;
revoke all on function app_trigger_drain() from public, anon, authenticated;

select cron.unschedule(jobid) from cron.job where jobname in ('maa-drain','maa-nightly');
select cron.schedule('maa-drain',   '* * * * *',  $$select app_trigger_drain()$$);
-- Nightly precompute: enqueue is idempotent per shop per day.
select cron.schedule('maa-nightly', '0 22 * * *', $$
  insert into jobs (shop_id, kind, payload, idempotency_key)
  select id, 'precompute', '{"screens":["health_check","voc"]}'::jsonb,
         'precompute:' || id || ':' || current_date
  from shops where status = 'active'
  on conflict (idempotency_key) where idempotency_key is not null do nothing
$$);
