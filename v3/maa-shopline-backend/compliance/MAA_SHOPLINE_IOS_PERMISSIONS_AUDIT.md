# 05 — iOS Permissions Audit

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

**No runtime permission is requested.** The Info.plist (generated from `ios/project.yml`) contains no NS*UsageDescription keys. Camera, Photos, Location, Contacts, Microphone, Bluetooth, Notifications, ATT, Calendar, Files, Face ID and Sign in with Apple: **not used**.

Other declarations: custom URL scheme `maashopline` (OAuth callback captured by ASWebAuthenticationSession, ephemeral browser session); `ITSAppUsesNonExemptEncryption=false` (HTTPS only — confirm the export-compliance answer in App Store Connect).

Not implemented: push notifications for queued jobs (the app polls instead). Adding them later requires notification authorisation and an APNs entry in the provider register.
