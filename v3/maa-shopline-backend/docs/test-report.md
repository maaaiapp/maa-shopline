# Test report — 27 Sep 2026

`python -m pytest -q` → **81 passed** (Python 3.11, Postgres 16 local cluster).

| Layer | File | Count |
|---|---|---|
| OAuth, signing, webhook | tests/test_shopline.py | 17 |
| Inference gateway + failure injection | tests/test_gateway.py | 39 |
| Health check, isolation, session, API | tests/test_health_and_api.py | 9 |
| Database / RLS | tests/test_rls.py | 16 |

Not run: live provider calls (egress 403), SHOPLINE sandbox (none provisioned), browser/iOS E2E (no client build), load/concurrency beyond the dedupe lock, backup-admission golden sets.
