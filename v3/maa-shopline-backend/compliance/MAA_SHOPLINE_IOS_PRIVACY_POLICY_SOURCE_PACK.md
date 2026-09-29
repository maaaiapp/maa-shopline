# 09 — Privacy Policy Source Pack

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.


1. **MAA identity:** Marketing As Art AI LLC, New Mexico, USA; contact address to be confirmed by MAA.
2. **App identity:** MAA × SHOPLINE merchant app (iOS NOT IMPLEMENTED; backend described here).
3. **Users:** SHOPLINE merchants who install the app. End customers are data subjects but not users.
4. **Data collected from the merchant:** Advisor questions (D09); onboarding answers and consent (D04–D05, not yet implemented).
5. **Data received from SHOPLINE:** store identity, access token, scopes, webhook payloads (parsed, not stored), order snapshots (not yet populated).
6. **Other integrations:** none implemented (socials, reviews: not implemented).
7. **Publicly sourced data:** none implemented.
8. **Technical data:** IP/request metadata at Render (D17), errors, traces.
9. **Purposes:** see inventory 'purpose' column.
10. **Legal bases:** candidates only in 07 — LEGAL REVIEW REQUIRED.
11. **Recipients:** see 03. Model providers receive merchant data only after approval (none approved today).
12. **International transfers:** see 08 — LEGAL REVIEW REQUIRED.
13. **Retention:** RETENTION POLICY NOT CURRENTLY DEFINED for most categories; defined exceptions in 10.
14. **Deletion:** uninstall deletes the access token; full erasure via admin endpoint; no merchant self-service deletion yet.
15. **User rights:** no self-service access/export/deletion endpoint implemented.
16. **Consent:** ledger schema exists; capture NOT IMPLEMENTED.
17. **Automated processing/profiling:** AI recommendations to the merchant; no automated decisions with legal effect.
18. **AI processing:** routing rules per data class (registry.eligible); SENSITIVE data never sent; OpenRouter PUBLIC-only.
19. **Security:** RLS, AES-GCM tokens, HMAC webhooks, secret redaction, isolation checks.
20. **Contact:** to be supplied by MAA.
21. **Complaints/DPA:** LEGAL REVIEW REQUIRED.
22. **Source disclosure:** data comes from SHOPLINE on the merchant's authorisation.
23. **Open questions:** roles, bases, transfers, retention periods, provider terms.
