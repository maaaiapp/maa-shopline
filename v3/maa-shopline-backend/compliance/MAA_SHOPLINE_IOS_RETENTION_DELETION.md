# 10 — Retention & Deletion Matrix

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

| id | category | stored | retention | deletion |
|---|---|---|---|---|
| D01 | Store identity | yes | Kept while installed and after uninstall. RETENTION POLICY NOT CURRENTLY DEFINED | In-app 'Delete account and data' (POST /api/account/delete) or admin erase; both cascade |
| D02 | SHOPLINE access token | yes | Until uninstall | Deleted on apps/uninstalled webhook and on erase |
| D03 | Granted scopes | yes | RETENTION POLICY NOT CURRENTLY DEFINED | Erase cascade |
| D04 | Consent records | schema only — NOT IMPLEMENTED: no endpoint writes it | RETENTION POLICY NOT CURRENTLY DEFINED | Erase cascade |
| D05 | Merchant profile / onboarding answers | schema only — NOT IMPLEMENTED: no endpoint writes it | RETENTION POLICY NOT CURRENTLY DEFINED | Erase cascade |
| D06 | Order snapshots (end-customer data) | schema only — NOT POPULATED: sync is blocked until SHOPLINE confirms orders scope (TD-01) | RETENTION POLICY NOT CURRENTLY DEFINED | Erase cascade |
| D07 | Webhook events (metadata only) | yes | RETENTION POLICY NOT CURRENTLY DEFINED (dedupe needs a window; purge not implemented) | Erase cascade |
| D08 | Webhook payloads in transit | NO — only payload['id'] (≤64 chars) is kept in jobs.payload | Request lifetime | n/a |
| D09 | Advisor question text | yes while queued; context removed when the job reaches done/failed/dead | Until job is terminal (max ~2h with 5 attempts), then context dropped | Automatic on terminal state; erase cascade |
| D10 | AI outputs / cache | yes | RETENTION POLICY NOT CURRENTLY DEFINED | Erase deletes by shop prefix |
| D11 | Inference trace (§7.5 destination log) | yes | RETENTION POLICY NOT CURRENTLY DEFINED | On erase shop_id set to null (record kept, de-linked) |
| D12 | Audit events | yes | RETENTION POLICY NOT CURRENTLY DEFINED | Erase deletes rows for that shop |
| D13 | Errors | yes | RETENTION POLICY NOT CURRENTLY DEFINED | On erase shop_id set to null |
| D14 | OAuth state | yes (≤10 min) | Deleted on use; expired rows purged every drain | Automatic |
| D15 | Session token | Not stored server-side. iOS: Keychain, kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly (no iCloud sync) | 12 h sliding expiry; revoked on uninstall or account deletion | Expiry |
| D16 | Provider health / quota | yes | Bucket resets daily | n/a |
| D17 | Request metadata / IP addresses | App access log disabled (--no-access-log); Render platform/edge logs: UNKNOWN | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED |

Backups: Supabase backup retention applies to deleted rows — UNKNOWN until the plan's backup settings are read. Third-party deletion (providers): UNKNOWN per provider.
