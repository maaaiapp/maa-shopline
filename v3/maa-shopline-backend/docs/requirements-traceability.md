# Requirements traceability

| Clause / source | Requirement | Implementation | Test | Status |
|---|---|---|---|---|
| Sched. I §2 API connectivity | OAuth install, token lifecycle | shopline/oauth.py | test_shopline::test_oauth_* , test_token_refresh_failure_marks_expired | PARTIALLY VERIFIED (public doc; no sandbox) |
| Sched. I §2 data synchronization | Webhooks, dedupe, reconcile | shopline/webhooks.py, webhook_events PK | test_webhook_* , test_webhook_dedupe_constraint | PARTIALLY VERIFIED (topic list = TD-06) |
| §3.1(b) security, defect-free | Security audit, tests | docs/security-audit.md, 81 tests | full suite | PARTIALLY VERIFIED |
| §3.1(g) no unrelated operations | Capability allowlist | policy/access_policy.py | test via /api/health-check degraded | VERIFIED |
| §5.3(c) no competing platforms | No Shopify/Woo connectors | NOT_IN_SCOPE in policy | — | VERIFIED |
| §6.3 trademarks | No SHOPLINE logo without written consent | backend serves none | — | NOT IN SCOPE (frontend) |
| §7.2 explicit consent | consent_ledger table | migration | RLS tests | PARTIALLY VERIFIED (no consent endpoint yet) |
| §7.3 minimum data | Snapshot minimum fields, hashed customer_ref | migration | — | PARTIALLY VERIFIED (field list pending TD-01) |
| §7.4 cross-border | Provider approval list | registry.APPROVED_FOR_MERCHANT_DATA = ∅ | test_merchant_data_never_goes_to_unapproved_provider, test_no_approved_provider_queues_not_leaks | VERIFIED (enforced); BLOCKED (no provider approved) |
| §7.5 breach evidence | Destination logged per call | inference_attempts / trace rows | test_trace_rows_complete_and_secret_free | VERIFIED |
| §8.1 confidentiality | Merchant data only to approved processors | same as §7.4 | same | VERIFIED |
| Sched. I §4 Live Customer | Full loop on real store | — | — | BLOCKED (P0-1..P0-4) |
| Sched. II referral fees | Referral source per shop | shops.referral_source | — | PARTIALLY VERIFIED (billing = TD-12) |
| Proposal: Health Check | Deterministic scoring vs own history, unscored on missing scope | intelligence/health_check.py | test_health_and_api | PARTIALLY VERIFIED (formulas provisional; data blocked by TD-01) |
| Proposal: VoC | Review-based themes | — | — | BLOCKED (P0-2) |
| Proposal: Growth Advisor | Streaming explainable answer | /api/advisor via gateway | test_api_degraded_states_not_errors | PARTIALLY VERIFIED (non-streaming; no approved provider) |
| Proposal: Campaign Planner | Plan JSON + execution | gateway structured_json role | test_json_repair_* | BLOCKED for execution (P0-3, P0-4) |
