# 12 — Compliance Evidence Index

_Generated 2026-09-27 by scripts/gen_compliance.py from the implemented code._

Scope of this audit: the backend repository `maa-shopline-backend` as of 2026-09-27 (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). Nothing here was verified against live dashboards.

| conclusion | evidence | confidence | verified |
|---|---|---|---|
| Merchant data cannot reach unapproved providers | registry.eligible; tests/test_pgstore.py::test_confidential_job_never_reaches_unapproved_provider | High | 2026-09-27 |
| Cross-tenant reads/writes denied by RLS | tests/test_rls.py (16 tests, Postgres 16) | High | 2026-09-27 |
| Ops tables closed to clients | tests/test_pgstore.py::test_ops_tables_closed_to_clients | High | 2026-09-27 |
| Webhook dedupe survives restart | tests/test_pgstore.py::test_webhook_dedupe_survives_restart | High | 2026-09-27 |
| Uninstall destroys token and revokes sessions | test_install_lookup_uninstall_destroys_token; test_uninstall_revokes_sessions | High | 2026-09-27 |
| Shop erasure removes all keyed data | test_erase_shop_removes_everything_keyed_to_it | High | 2026-09-27 |
| Alerts contain no secrets | test_alerts_recorded_deduped_and_redacted | High | 2026-09-27 |
| No credentials in tree or git history | scripts/secret_scan.py (tree + --history) | High | 2026-09-27 |
| Provider regions / DPAs | None — not verified | None | 2026-09-27 |
