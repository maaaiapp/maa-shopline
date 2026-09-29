# Security audit — 27 Sep 2026

| Check | Result | Evidence |
|---|---|---|
| Auth on non-public routes | PASS | test_api_auth_required_and_tenant_from_session |
| Tenant from server context only | PASS | session HMAC-bound shop_id; no endpoint reads shop id from client |
| IDOR / RLS | PASS (DB) | tests/test_rls.py |
| Webhook HMAC constant-time, dedupe | PASS | test_webhook_* , hmac.compare_digest |
| Webhook replay | PARTIAL | SHOPLINE sends no timestamp header; dedupe on X-Shopline-Webhook-Id only |
| OAuth state single-use, signed callback, 10-min window | PASS | test_oauth_rejects_bad_state_and_signature, test_state_is_single_use, test_params_replay_window |
| SSRF (store handle → host) | PASS | HANDLE_RE; test_handle_ssrf_guard |
| Open redirect | PASS | redirect target built only from validated handle |
| Injection | PASS (by construction) | parameterised SQL in schema/tests; no string SQL in app |
| XSS / CORS | PASS (API) | JSON only; no CORS middleware → cross-origin denied by default |
| Prompt injection | PARTIAL | store text fenced as untrusted data; no adversarial eval yet |
| Model-output injection | PARTIAL | validators + safety fail-closed; safety model not wired |
| Secrets in repo | PASS | scripts/secret_scan.py passes; .env gitignored |
| **Secrets on disk** | **FAIL — action needed** | `Shopline app.txt` holds live NVIDIA, OpenRouter, Groq keys and the SHOPLINE app secret in plaintext on the Desktop. Move to a secret manager and rotate if the file was ever synced/shared. |
| Tokens encrypted at rest, never selectable by clients | PASS | AES-GCM with AAD=handle; shop_tokens revoked |
| Server-side rate limits | FAIL | not implemented (needed for /api/advisor, re-sync throttle) |
| Isolation | PASS | isolation_check.py + assert_isolated tests |
| Error leakage | PASS | global handler returns `{state:error}`; provider messages never propagated |
