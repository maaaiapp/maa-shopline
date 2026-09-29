# 08 — International Transfer Register

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

MAA is a New Mexico LLC operating from Dubai; merchants may be anywhere SHOPLINE operates. Which transfer regimes apply (EU/UK GDPR, UAE PDPL, others) is LEGAL REVIEW REQUIRED.

| provider | data | location | mechanism | dpa | status | next_action |
|---|---|---|---|---|---|---|
| SHOPLINE | Store identity, tokens, order/customer/product data (payloads in transit) | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| Supabase | D01–D07, D09–D14, D16 | UNKNOWN — read project region from the live dashboard | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| Render | All data in transit through the API; D17 | render.yaml proposes frankfurt — INFRA DECISION, not deployed | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| NVIDIA (API Catalog) | Prompts/context for eligible calls | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| Groq | Prompts for eligible calls | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| OpenRouter | Prompts for PUBLIC calls only | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| Google (AI Studio / Gemini API) | Prompts for eligible calls | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| Slack or Discord | Alert kind, route, job kind, provider key; secrets redacted; no merchant content | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |
| Apple (App Store, APNs, frameworks) | App distribution/TestFlight; no Apple SDK receives app data (no APNs, analytics or crash SDK in code) | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED | Assessment not started | Read region + DPA/SCC terms; record version |

No SCC or adequacy claim is made for any provider.
