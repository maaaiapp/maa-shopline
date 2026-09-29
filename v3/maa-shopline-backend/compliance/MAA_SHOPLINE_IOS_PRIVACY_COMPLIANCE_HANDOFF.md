# 13 — Executive Handoff

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.


**A. Data processed:** store identity, encrypted tokens, webhook metadata, Advisor questions (until the job finishes), AI outputs, traces, audit and error logs. Order and customer snapshots are designed but not populated.
**B. Where it goes:** Render (compute) and Supabase (storage). AI providers receive merchant data only after approval, and none are approved yet. Slack or Discord receive alert codes only.
**C. Providers:** see 03. Every provider's terms are UNKNOWN.
**D. Personal data:** yes — store handles (possible sole traders), free text, pseudonymised end-customer references (when enabled), end-customer data in webhook payloads (in transit only), and IPs at the hosting edge.
**E. Special-category data:** not intentionally collected; free text could contain it.
**F. Transfers:** all UNKNOWN pending region and DPA review.
**G. Retention and deletion:** tokens are deleted on uninstall; Advisor context is dropped when its job finishes; OAuth states are purged automatically; full erasure is available through the admin endpoint; everything else is RETENTION POLICY NOT CURRENTLY DEFINED.
**H. Apple privacy:** cannot be finalised until the iOS app exists; see the draft in 06.
**I–K. GDPR and legal:** see 07, 08 and HUMAN REVIEW REQUIRED.
**L. Engineering remediation:** build the iOS app, self-service export and deletion, consent capture, rate limiting, and purge jobs once retention periods are set.
**M. Documentation only:** provider terms register, region confirmation.
**N. Before App Store submission:** first successful CI compile and TestFlight run, final App Privacy answers (draft in 06), live privacy policy URL, export-compliance answer. In-app account deletion is implemented.
**O. Can wait:** session-key separation, timestamp header.
**P. Next steps:** (1) read regions and DPAs for Supabase, Render, NVIDIA, Groq and Google; (2) legal review of the list; (3) set retention periods; (4) run the iOS CI pipeline and confirm the compiled app matches 04–06.
