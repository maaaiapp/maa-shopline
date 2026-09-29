# 04 — Third-Party SDK Inventory

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

**iOS: no third-party SDKs.** `ios/project.yml` declares no Swift packages, CocoaPods or frameworks. The app uses only Apple frameworks: SwiftUI, Foundation, Security (Keychain), AuthenticationServices (ASWebAuthenticationSession), Observation. Network destinations: the configured MAA API host only (API_BASE_URL); the SHOPLINE authorization page opens inside ASWebAuthenticationSession.

Backend dependencies (server-side, not shipped in the app): fastapi, uvicorn, httpx, cryptography, psycopg, psycopg-pool (requirements.txt). None performs analytics or tracking.

Nothing to declare for third-party SDKs. Re-check if any package is added later.
