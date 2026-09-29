# 11 — Privacy / Security Gap Register

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

| severity | finding | evidence | risk | remediation | blocks_app_store | privacy_requirement | status |
|---|---|---|---|---|---|---|---|
| HIGH | iOS app not yet compiled or run | ios/ | Static review only; runtime behaviour unverified | Run .github/workflows/ios.yml; fix any compile errors | Yes | No | Open |
| HIGH | Retention periods undefined for most tables | 10 | Unbounded storage of personal data | MAA decides periods; implement purge jobs | No | Yes | Open |
| MEDIUM | No self-service data export (deletion now in-app) | main.py | Access/portability requests are manual | Add an export endpoint | No | Yes | Open |
| FIXED | In-app account deletion | POST /api/account/delete; SettingsView | Apple 5.1.1(v) | Implemented + tested | - | - | Fixed |
| HIGH | Provider data terms unverified; approved list empty | registry.py | AI features queue for merchant data | Record terms, approve providers | No | Yes | Open (by design) |
| MEDIUM | Consent capture not implemented | consent_ledger | §7.2 consent not evidenced | Build consent endpoint + UI | No | Yes | Open |
| MEDIUM | No server-side rate limiting | main.py | Abuse / quota drain | Add per-shop limits | No | Best practice | Open |
| MEDIUM | Webhook timestamp header unconfirmed | webhooks._sent_at | Replay window relies on durable dedupe only | Set SHOPLINE_WEBHOOK_TS_HEADER once confirmed | No | Best practice | Open |
| MEDIUM | Render/Supabase platform log retention unknown | render.yaml | IPs retained by platforms | Read and record platform settings | No | Yes | Open |
| LOW | Session key derived from token-encryption key | main.py | Key rotation logs everyone out | Separate SESSION_SECRET | No | Best practice | Open |
| FIXED | OAuth code in access logs | render.yaml | Credential in logs | --no-access-log | - | - | Fixed |
| FIXED | Advisor question kept indefinitely | pgstore | Unbounded retention | Context dropped at terminal state | - | - | Fixed |
| FIXED | In-memory state (queue, dedupe, breakers) | store.py | Lost on restart; replay possible | PgStore + provider_state | - | - | Fixed |
