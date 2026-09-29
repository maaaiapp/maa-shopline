# 07 — GDPR / Privacy Processing Matrix

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

| activity | subjects | data | legal_basis | transfer | risk |
|---|---|---|---|---|---|
| Store installation & authentication | Merchant (possibly sole trader) | D01–D03, D14, D15 | Candidate: contract — LEGAL REVIEW REQUIRED | UNKNOWN | Low |
| Webhook ingestion | Merchant's customers (end customers) | D07, D08 | LEGAL REVIEW REQUIRED (MAA likely processor for merchant; confirm) | UNKNOWN | Medium |
| Order snapshot analytics (Health Check) | End customers (pseudonymised) | D06 | LEGAL REVIEW REQUIRED | UNKNOWN | Medium — NOT YET ACTIVE |
| AI Advisor | Merchant; anyone named in free text | D09, D10, D11 | Candidate: contract — LEGAL REVIEW REQUIRED | Blocked until providers approved | Medium |
| Monitoring & security logging | Merchant | D11–D13, D17 | Candidate: legitimate interests — LEGAL REVIEW REQUIRED | UNKNOWN | Low |

No lawful basis is asserted. Controller/processor roles for MAA, SHOPLINE and each merchant require legal analysis of the signed agreement and SHOPLINE's platform terms. Automated decision-making with legal effect: none implemented.
