-- MAA × SHOPLINE — dedicated project schema. Target: SHOPLINE Supabase project only.
-- Every tenant-owned table: shop_id NOT NULL + RLS keyed to the JWT claim `shop_id`
-- (claim set server-side at session issue; never from client input).
-- Service role bypasses RLS and is used only by the backend.

create extension if not exists pgcrypto;

create or replace function app_current_shop() returns uuid
language sql stable as $$
  select nullif(coalesce(auth.jwt() ->> 'shop_id', ''), '')::uuid
$$;

create table shops (
  id uuid primary key default gen_random_uuid(),
  handle text not null unique check (handle ~ '^[a-z0-9][a-z0-9-]{0,62}$'),
  status text not null default 'active' check (status in ('active','token_expired','uninstalled')),
  referral_source text check (referral_source in ('shopline','developer','mutual')),  -- Sched. II
  installed_at timestamptz not null default now(),
  uninstalled_at timestamptz
);

-- Tokens: ciphertext only (AES-GCM, app-side key). No client role may select.
create table shop_tokens (
  shop_id uuid primary key references shops(id) on delete cascade,
  enc_access_token text not null,
  expires_at timestamptz,
  updated_at timestamptz not null default now()
);

create table shop_scopes (
  shop_id uuid references shops(id) on delete cascade,
  scope text not null,
  granted_at timestamptz not null default now(),
  primary key (shop_id, scope)
);

create table consent_ledger (                                  -- §7.2 explicit consent
  id bigint generated always as identity primary key,
  shop_id uuid not null references shops(id) on delete cascade,
  purpose text not null,
  granted boolean not null,
  policy_version text not null,
  recorded_at timestamptz not null default now()
);

create table merchant_profiles (                               -- screen 05 / 29
  shop_id uuid primary key references shops(id) on delete cascade,
  category text, positioning text, primary_goal text, constraints text,
  language text not null default 'en' check (language in ('en','ar')),
  updated_at timestamptz not null default now()
);

create table shop_data_sync_state (
  shop_id uuid references shops(id) on delete cascade,
  object text not null check (object in ('orders','customers','products','reviews')),
  cursor text, last_success_at timestamptz, status text not null default 'pending',
  primary key (shop_id, object)
);

-- Snapshots: minimum fields (§7.3). customer_ref is a salted hash, not the SHOPLINE id.
create table orders_snapshot (
  shop_id uuid not null references shops(id) on delete cascade,
  order_ref text not null,
  customer_ref text,
  created_at timestamptz not null,
  total numeric(14,2) not null,
  currency char(3) not null,
  discount_codes text[] not null default '{}',
  primary key (shop_id, order_ref)
);

create table intelligence_outputs (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id) on delete cascade,
  task text not null,
  cache_key text not null,
  value jsonb not null,
  model text not null,
  validation text not null check (validation = 'pass'),        -- only validated output is stored
  generated_at timestamptz not null default now()
);
create index on intelligence_outputs (shop_id, cache_key, generated_at desc);

create table jobs (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references shops(id) on delete cascade,
  kind text not null, payload jsonb not null default '{}',
  status text not null default 'queued' check (status in ('queued','running','done','flagged')),
  attempts int not null default 0, run_after timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table inference_attempts (                              -- §7.5 destination log
  id bigint generated always as identity primary key,
  shop_id uuid references shops(id) on delete set null,
  role text not null, data_class text not null check (data_class in ('merchant_confidential','public')),
  provider text not null, model text not null, attempt int not null,
  trigger text, latency_ms int not null, tokens int not null default 0,
  validation text not null, created_at timestamptz not null default now()
);

create table webhook_events (
  webhook_id text primary key,                                 -- X-Shopline-Webhook-Id: dedupe
  shop_id uuid references shops(id) on delete cascade,
  topic text not null, body_sha256 text not null,
  status text not null default 'received',
  received_at timestamptz not null default now()
);

create table audit_events (
  id bigint generated always as identity primary key,
  shop_id uuid, event text not null, detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- ---------- RLS ----------
alter table shops                enable row level security;
alter table shop_tokens          enable row level security;
alter table shop_scopes          enable row level security;
alter table consent_ledger       enable row level security;
alter table merchant_profiles    enable row level security;
alter table shop_data_sync_state enable row level security;
alter table orders_snapshot      enable row level security;
alter table intelligence_outputs enable row level security;
alter table jobs                 enable row level security;
alter table inference_attempts   enable row level security;
alter table webhook_events       enable row level security;
alter table audit_events         enable row level security;

create policy shop_self on shops for select to authenticated using (id = app_current_shop());
create policy tenant_read on shop_scopes          for select to authenticated using (shop_id = app_current_shop());
create policy tenant_read on consent_ledger       for select to authenticated using (shop_id = app_current_shop());
create policy tenant_rw   on merchant_profiles    for all    to authenticated
  using (shop_id = app_current_shop()) with check (shop_id = app_current_shop());
create policy tenant_read on shop_data_sync_state for select to authenticated using (shop_id = app_current_shop());
create policy tenant_read on orders_snapshot      for select to authenticated using (shop_id = app_current_shop());
create policy tenant_read on intelligence_outputs for select to authenticated using (shop_id = app_current_shop());
create policy tenant_read on jobs                 for select to authenticated using (shop_id = app_current_shop());
-- shop_tokens, inference_attempts, webhook_events, audit_events: no client policy => no client access.
revoke all on shop_tokens, inference_attempts, webhook_events, audit_events from anon, authenticated;
