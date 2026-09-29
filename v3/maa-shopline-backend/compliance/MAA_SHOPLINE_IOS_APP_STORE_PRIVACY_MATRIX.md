# 06 — App Store Connect Privacy Matrix

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

Based on the implemented iOS source and `PrivacyInfo.xcprivacy`. Confidence MEDIUM until the compiled build is inspected. Final answers are MAA's responsibility in App Store Connect.

| category | collected | linked | tracking | evidence |
|---|---|---|---|---|
| Contact Info | Not by implemented API | - | No | no endpoint accepts contact info |
| User Content → Other User Content | YES (Advisor questions) — purpose: App Functionality | Yes (store) | No | AdvisorView.swift; APIClient.ask |
| Identifiers → User ID | YES (store id inside the session token) — purpose: App Functionality | Yes | No | Keychain.swift; APIClient Bearer header |
| Usage Data | Not implemented | - | No | no analytics |
| Diagnostics | No (no crash/analytics SDK; server errors are not collected from the device) | - | No | no SDKs in project.yml |
| Financial Info / Purchases | Store order data is SHOPLINE-sourced, not collected from the app user — LEGAL REVIEW REQUIRED | - | No | orders_snapshot (not populated) |
| Location, Health, Contacts, Browsing/Search History, Sensitive Info | No | - | No | no code |

Tracking: nothing in the implemented system links data with third-party data for advertising, so ATT is not indicated — re-verify against the final app.
