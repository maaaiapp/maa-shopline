# Database

Migration: `supabase/migrations/0001_init.sql`. Target: SHOPLINE Supabase project only (ref unconfirmed — see source-register).

| Table | Tenant | Client access (authenticated) | Retention (proposed — confirm with Legal, §7.2/§8.4) |
|---|---|---|---|
| shops | self | select own | life of install; delete on request after uninstall |
| shop_tokens | yes | **none** (revoked) — AES-GCM ciphertext | until uninstall/refresh |
| shop_scopes, consent_ledger, shop_data_sync_state | yes | select own | life of install |
| merchant_profiles | yes | read/write own | life of install |
| orders_snapshot | yes | select own; customer_ref hashed | 13 months |
| intelligence_outputs | yes | select own; `validation='pass'` enforced by CHECK | 13 months |
| jobs | yes | select own | 30 days |
| inference_attempts, webhook_events, audit_events | server | **none** | 12 months (breach evidence) |

RLS verified on a real Postgres 16 cluster (`tests/test_rls.py`, 16 tests): RLS on for every table; cross-tenant read denied on 7 tenant tables; cross-tenant update/insert denied; no claim → no rows; server-only tables denied; webhook id unique; unvalidated output rejected.
Not yet built: customers/products/reviews snapshots, campaigns, recommendations (blocked on TD-01/02/03).
