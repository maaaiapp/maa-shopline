# Release readiness — NOT READY

| Completion item | Status | Evidence / blocker |
|---|---|---|
| Requirements mapped, contract scope traced | PARTIALLY VERIFIED | requirements-traceability.md; Brand DNA/SWOT onboarding scope undecided |
| Backend implemented | PARTIALLY VERIFIED | foundation only: OAuth, webhooks, gateway, health scoring, 4 API routes |
| Frontend connected | BLOCKED | no iOS project supplied; UI file is an HTML prototype |
| Database isolated | BLOCKED | Supabase ref unconfirmed (o vs 0); no project access |
| RLS tested | VERIFIED (local) | tests/test_rls.py on Postgres 16; re-run on the real project |
| SHOPLINE OAuth/API/webhooks tested | PARTIALLY VERIFIED | against published docs with mocks; no sandbox (Kickoff §7) |
| AI routing tested — NVIDIA/Groq/OpenRouter | BLOCKED | egress 403; OpenRouter 402 per plan; no provider approved for merchant data |
| Quality gates + quota handling | PARTIALLY VERIFIED | deterministic validators + quotas tested; judge uncalibrated; safety not wired |
| Security audit | PARTIALLY VERIFIED | security-audit.md: 2 FAIL (plaintext keys on disk, no rate limiting) |
| E2E passing | BLOCKED | needs sandbox store + client |
| Deployment verified | BLOCKED | do-not-deploy conditions hold: ref unconfirmed, provider entitlement unverified, critical fallback untested live |
| No main-platform dependency | VERIFIED | isolation_check passes; no MAA OS runtime referenced |

## Open blockers (owner → action)
1. Mohamed → confirm Supabase ref in dashboard; set `SHOPLINE_SUPABASE_REF`.
2. Mohamed → move keys from `Shopline app.txt` into a secret manager; rotate.
3. SHOPLINE (Kickoff Sessions A–D) → TD-01 scopes, TD-02 reviews, TD-03 channels, TD-04 attribution, TD-09 mobile install hand-off; sandbox store.
4. Mohamed → record NVIDIA/Groq retention & training terms; approve providers for merchant data.
5. Allow egress to integrate.api.nvidia.com, api.groq.com, openrouter.ai and run `scripts/probe_providers.py`.
6. Fund OpenRouter (402) or choose another paid zero-retention tier.
7. Build golden sets; run backup admission; calibrate judge.
8. Product → decide whether Brand DNA / Audience / SWOT / Ecosystem (UI v3 zone 1) are in MVP.
