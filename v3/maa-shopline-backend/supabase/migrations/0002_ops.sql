-- 0002: durable operational state. Replaces every in-memory structure the app
-- used in 0001 (queue, breaker/quota, OAuth state, cache, errors).
-- All tables have RLS on and NO client policy: only the backend (service role /
-- table owner) may touch them. Merchants read their own job status via 0001's jobs policy.

-- ---------- data classes (plan: 4 classes) ----------
alter table inference_attempts drop constraint if exists inference_attempts_data_class_check;
alter table inference_attempts add constraint inference_attempts_data_class_check
  check (data_class in ('public','internal','merchant_confidential','sensitive'));

-- ---------- job queue ----------
alter table jobs alter column shop_id drop not null;               -- platform jobs (nightly sweep) have no shop
alter table jobs drop constraint if exists jobs_status_check;
alter table jobs add constraint jobs_status_check
  check (status in ('queued','running','done','failed','dead'));
update jobs set status = 'dead' where status = 'flagged';
alter table jobs
  add column if not exists max_attempts int not null default 5 check (max_attempts between 1 and 20),
  add column if not exists idempotency_key text,
  add column if not exists locked_at timestamptz,
  add column if not exists locked_by text,
  add column if not exists last_error text,
  add column if not exists started_at timestamptz,
  add column if not exists finished_at timestamptz,
  add column if not exists updated_at timestamptz not null default now();
create unique index if not exists jobs_idempotency_key on jobs (idempotency_key) where idempotency_key is not null;
create index if not exists jobs_claimable on jobs (run_after) where status = 'queued';
create index if not exists jobs_running on jobs (locked_at) where status = 'running';

-- ---------- errors (monitoring; replaces Sentry) ----------
create table if not exists errors (
  id bigint generated always as identity primary key,
  source text not null,                    -- api | job | webhook | provider | scheduler
  kind text not null,                      -- exception class or machine code
  message text not null,                   -- redacted, truncated
  shop_id uuid,                            -- no FK: must survive shop deletion for audit
  context jsonb not null default '{}',
  alerted boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists errors_recent on errors (created_at desc);

-- ---------- provider state: breakers + quota buckets, shared across instances ----------
create table if not exists provider_state (
  key text primary key,                    -- "<provider>:<model>"
  breaker jsonb not null default '{}',
  bucket jsonb not null default '{}',
  bucket_day date not null default current_date,
  updated_at timestamptz not null default now()
);

-- ---------- OAuth state (single use, TTL) ----------
create table if not exists oauth_states (
  state text primary key,
  handle text not null,
  expires_at timestamptz not null
);

-- ---------- webhook replay window ----------
alter table webhook_events add column if not exists sent_at timestamptz;

-- ---------- output cache ----------
create table if not exists output_cache (
  cache_key text primary key,
  shop_id uuid references shops(id) on delete cascade,
  value jsonb not null,
  model text not null,
  generated_at timestamptz not null
);

alter table errors         enable row level security;
alter table provider_state enable row level security;
alter table oauth_states   enable row level security;
alter table output_cache   enable row level security;
-- intentionally no policies: deny-all for anon/authenticated.
