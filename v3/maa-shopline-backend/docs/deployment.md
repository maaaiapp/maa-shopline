# Deployment runbook (dashboard steps)

These steps need logged-in dashboard access, which the build environment did not have.
Run them in Claude Cowork + Claude in Chrome, or by hand. Never paste a secret value into a file.

| # | Where | Action | Verify |
|---|---|---|---|
| 1 | Supabase dashboard → Project Settings → General | Copy the **Project ID** (20 chars). This settles `jojyjj…` vs `j0jyjj…`. | Matches the host in `https://<ref>.supabase.co` |
| 2 | GitHub | Create a **private** repo; push this repo; Settings → Variables: `SHOPLINE_SUPABASE_REF`; Secrets: `FORBIDDEN_IDENTIFIERS`, `DRAIN_URL`, `DRAIN_SECRET` | `ci` workflow green, with 0 skipped tests |
| 3 | Supabase → SQL editor | Run `0001_init.sql`, then `0002_ops.sql` | `select relname from pg_class where relnamespace='public'::regnamespace and relkind='r' and not relrowsecurity` returns 0 rows |
| 4 | Supabase → Database → Extensions | Enable `pg_cron`, `pg_net` | — |
| 5 | Supabase → Vault | Add secrets `drain_url` (Render URL + `/internal/jobs/drain`) and `drain_secret` | — |
| 6 | Supabase → SQL editor | Run `0003_scheduler.sql` | `select jobname, schedule from cron.job` shows `maa-drain`, `maa-nightly` |
| 7 | Render → New → Blueprint | Point at the repo (`render.yaml`); fill every `sync: false` value; `DATABASE_URL` = **transaction pooler** URI | `/health` returns `{"status":"ok","db":"ok"}` |
| 8 | Render logs | Confirm no `IsolationError` at boot | Service live |
| 9 | Slack or Discord | Create an incoming webhook → Render `ALERT_WEBHOOK_URL` | Trigger `/internal/jobs/drain` with a wrong token 0×; force one error; message arrives |
| 10 | Local machine with provider hosts allowed | `python scripts/probe_providers.py` | Record entitled models in `app/inference/registry.py` (`verified=True`) |
| 11 | SHOPLINE Developer Center | Set the redirect URI and webhook URL to the Render host | Install on the sandbox store; `webhook_events` gets rows |
| 12 | GitHub Actions → drain-backup → Run workflow | Manual run | HTTP 200 |

Secrets to generate (any CSPRNG, ≥32 bytes): `DRAIN_SECRET`, `ADMIN_TOKEN`, `TOKEN_ENCRYPTION_KEY` (base64 of 32 bytes).
`DRAIN_SECRET` must be identical in Render, GitHub and Supabase Vault; `ADMIN_TOKEN` must differ from it.

## iOS → TestFlight from Windows (GitHub macOS runners; no Mac needed)

| # | Where | Action | Verify |
|---|---|---|---|
| 13 | GitHub → Actions → ios | Push `ios/`; the `test` job generates the project, runs unit tests on a simulator and compiles Release | Job green. **This is the first real compile.** Fix anything it reports. |
| 14 | developer.apple.com → Identifiers | Register the App ID (bundle id of your choice) | Bundle id recorded |
| 15 | App Store Connect → Apps → + | Create the app record with that bundle id | App exists |
| 16 | App Store Connect → Users and Access → Integrations → Keys | Create an API key with **Admin** access (required for cloud-managed signing); download the `.p8` once | Key ID + Issuer ID noted |
| 17 | GitHub → Settings → Secrets | `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8_BASE64` (base64 of the .p8), `APPLE_TEAM_ID`; Variables: `MAA_BUNDLE_ID`, `API_BASE_URL` (Render https URL) | — |
| 18 | GitHub → Settings → Environments | Create `testflight`, add yourself as required reviewer | Approval gate before any Apple credential is used |
| 19 | GitHub → Actions → ios → Run workflow | Approve the `testflight` job | Build appears in App Store Connect → TestFlight after processing (~10–30 min) |
| 20 | App Store Connect → TestFlight | Answer export compliance; add yourself as an internal tester | Invite email |
| 21 | iPhone | Install **TestFlight** from the App Store; accept invite; install | Physical-device QA |

Render must also have `IOS_CALLBACK_URL=maashopline://auth` (the default). In the SHOPLINE Developer Center the redirect URI stays the backend's `/auth/shopline/callback`; the backend forwards to the app.
