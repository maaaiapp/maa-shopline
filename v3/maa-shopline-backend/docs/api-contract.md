# API contract (current)

All `/api/*` require `Authorization: Bearer <session>`; 401 otherwise. Responses carry a `state` the UI maps directly; no raw error text.

| Endpoint | Screen | Response states |
|---|---|---|
| GET /auth/shopline/start?handle= | 02 | 302 to SHOPLINE authorize; 400 invalid_handle |
| GET /auth/shopline/callback | 02→03 | `{session}`; 400 authorization_failed. Mobile hand-off contract = TD-09 |
| POST /webhooks/shopline | — | 200 / 401 (bad signature) |
| GET /api/connection | 30 | connected · token_expired · disconnected; scopes; capability statuses |
| GET /api/health-check | 09 | live · degraded (dimension-level: scored / unscored + needs / insufficient + requirement) |
| POST /api/advisor `{question, lang}` | 27/28 | live · last_valid (+generated_at) · queued (+job_id) · not_computed · blocked |

Unhandled exceptions → `{"state":"error","reason":"server"}` (500). Not yet built: screens 04–08, 10–26 endpoints, streaming, consent capture, profile.
