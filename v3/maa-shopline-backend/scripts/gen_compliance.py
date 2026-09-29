#!/usr/bin/env python3
"""Generates the privacy/compliance package from one source of truth (this file),
so the Markdown, JSON and CSV cannot drift. Every entry cites code evidence.
Status vocabulary: CONFIRMED BY CODE | NOT IMPLEMENTED | UNKNOWN | LEGAL REVIEW REQUIRED | EXTERNAL DEPENDENCY."""
import csv, json, pathlib
OUT = pathlib.Path(__file__).resolve().parents[1] / "compliance"
DATE = "2026-09-27"
UNK = "UNKNOWN — PROVIDER TERMS VERIFICATION REQUIRED"
RET = "RETENTION POLICY NOT CURRENTLY DEFINED"
LR = "LEGAL REVIEW REQUIRED"

SCOPE_NOTE = ("Scope of this audit: the backend repository `maa-shopline-backend` as of " + DATE +
    " (FastAPI app, Supabase migrations 0001–0003, GitHub workflows, render.yaml). "
    "and the SwiftUI app in `ios/` (XcodeGen project, no third-party packages). The iOS source has been statically "
    "reviewed but **not yet compiled**: the first compile runs on the GitHub macOS runner (`.github/workflows/ios.yml`). "
    "Nothing here was verified against live dashboards.")

# ---------------- data inventory ----------------
INV = [
 dict(id="D01", category="Store identity", fields="shops.handle, status, referral_source, installed_at, uninstalled_at",
      source="SHOPLINE OAuth callback", destination="Supabase Postgres (shops)", purpose="Identify the installed store; tenant key",
      required="required", user_provided="no", from_shopline="yes", personal="POSSIBLY — a store handle can identify a sole trader",
      sensitive="no", stored="yes", retention="Kept while installed and after uninstall. " + RET,
      deletion="In-app 'Delete account and data' (POST /api/account/delete) or admin erase; both cascade", security="RLS; client may read own row only",
      evidence="0001_init.sql shops; pgstore.upsert_installation", status="CONFIRMED BY CODE"),
 dict(id="D02", category="SHOPLINE access token", fields="shop_tokens.enc_access_token, expires_at",
      source="SHOPLINE token endpoint", destination="Supabase (ciphertext)", purpose="Call SHOPLINE Admin API for the store",
      required="required", user_provided="no", from_shopline="yes", personal="no (credential)", sensitive="credential",
      stored="yes", retention="Until uninstall", deletion="Deleted on apps/uninstalled webhook and on erase",
      security="AES-GCM app-side key (app/security/crypto.py); no client role can select", evidence="0001 shop_tokens; pgstore.mark_uninstalled", status="CONFIRMED BY CODE"),
 dict(id="D03", category="Granted scopes", fields="shop_scopes.scope", source="SHOPLINE OAuth", destination="Supabase",
      purpose="Know which capabilities may be used", required="required", user_provided="no", from_shopline="yes", personal="no",
      sensitive="no", stored="yes", retention=RET, deletion="Erase cascade", security="RLS read-own", evidence="0001 shop_scopes", status="CONFIRMED BY CODE"),
 dict(id="D04", category="Consent records", fields="consent_ledger.purpose, granted, policy_version, recorded_at",
      source="Merchant choice (future app UI)", destination="Supabase", purpose="Evidence of §7.2 consent",
      required="conditional", user_provided="yes", from_shopline="no", personal="POSSIBLY (linked to store)", sensitive="no",
      stored="schema only — NOT IMPLEMENTED: no endpoint writes it", retention=RET, deletion="Erase cascade",
      security="RLS read-own", evidence="0001 consent_ledger; no writer in app/", status="NOT IMPLEMENTED"),
 dict(id="D05", category="Merchant profile / onboarding answers", fields="merchant_profiles.category, positioning, primary_goal, constraints, language",
      source="Merchant (onboarding screens)", destination="Supabase", purpose="Personalise pilot features",
      required="optional", user_provided="yes", from_shopline="no", personal="POSSIBLY — free text may contain personal data",
      sensitive="not intentionally collected; free text could contain anything", stored="schema only — NOT IMPLEMENTED: no endpoint writes it",
      retention=RET, deletion="Erase cascade", security="RLS read/write own", evidence="0001 merchant_profiles", status="NOT IMPLEMENTED"),
 dict(id="D06", category="Order snapshots (end-customer data)", fields="orders_snapshot.order_ref, customer_ref (salted hash), created_at, total, currency, discount_codes",
      source="SHOPLINE Admin API", destination="Supabase", purpose="Deterministic Health Check scoring",
      required="required for Health Check", user_provided="no", from_shopline="yes",
      personal="YES — customer_ref is pseudonymous personal data of the merchant's customers", sensitive="no",
      stored="schema only — NOT POPULATED: sync is blocked until SHOPLINE confirms orders scope (TD-01)",
      retention=RET, deletion="Erase cascade", security="RLS read-own; hashed customer id", evidence="0001 orders_snapshot; jobs.handle('sync') raises capability_blocked", status="NOT IMPLEMENTED"),
 dict(id="D07", category="Webhook events (metadata only)", fields="webhook_events.webhook_id, shop_id, topic, body_sha256, sent_at, received_at",
      source="SHOPLINE webhooks", destination="Supabase", purpose="Idempotency / replay protection / audit",
      required="required", user_provided="no", from_shopline="yes", personal="no — body is NOT stored, only its SHA-256",
      sensitive="no", stored="yes", retention=RET + " (dedupe needs a window; purge not implemented)", deletion="Erase cascade",
      security="RLS: no client access", evidence="webhooks.receive; pgstore.insert_webhook_event", status="CONFIRMED BY CODE"),
 dict(id="D08", category="Webhook payloads in transit", fields="Full SHOPLINE order/customer/product JSON (may include names, emails, addresses of end customers)",
      source="SHOPLINE", destination="Render (in memory only)", purpose="Extract the object id to enqueue a sync",
      required="required", user_provided="no", from_shopline="yes", personal="YES (end-customer personal data in transit)", sensitive="possible",
      stored="NO — only payload['id'] (≤64 chars) is kept in jobs.payload", retention="Request lifetime", deletion="n/a",
      security="HMAC-verified before parsing; TLS", evidence="webhooks.receive", status="CONFIRMED BY CODE"),
 dict(id="D09", category="Advisor question text", fields="jobs.payload.context.instruction ('Merchant question: …')",
      source="Merchant via iOS AdvisorView → POST /api/advisor", destination="Supabase jobs; model provider ONLY if approved", purpose="Answer the merchant's question",
      required="optional", user_provided="yes", from_shopline="no", personal="POSSIBLY (free text)", sensitive="not intentionally",
      stored="yes while queued; context removed when the job reaches done/failed/dead", retention="Until job is terminal (max ~2h with 5 attempts), then context dropped",
      deletion="Automatic on terminal state; erase cascade", security="RLS: merchant can read own job status, not payload through API",
      evidence="main.advisor; gateway._ladder; pgstore.complete_job/fail_job", status="CONFIRMED BY CODE"),
 dict(id="D10", category="AI outputs / cache", fields="output_cache.value, model, generated_at; intelligence_outputs",
      source="MAA backend (model or deterministic)", destination="Supabase", purpose="Serve last valid result; precompute",
      required="required", user_provided="no", from_shopline="derived", personal="POSSIBLY (derived from merchant data)", sensitive="no",
      stored="yes", retention=RET, deletion="Erase deletes by shop prefix", security="RLS: no client policy on output_cache",
      evidence="gateway._deliver; pgstore.save_output; jobs precompute", status="CONFIRMED BY CODE"),
 dict(id="D11", category="Inference trace (§7.5 destination log)", fields="inference_attempts.shop_id, role, data_class, provider, model, attempt, trigger, latency_ms, tokens, validation",
      source="Gateway", destination="Supabase", purpose="Observability; evidence of where each call went", required="required",
      user_provided="no", from_shopline="no", personal="linked to store id; NO prompt or response content stored", sensitive="no",
      stored="yes", retention=RET, deletion="On erase shop_id set to null (record kept, de-linked)", security="RLS: no client access",
      evidence="gateway._attempt; pgstore.append_trace", status="CONFIRMED BY CODE"),
 dict(id="D12", category="Audit events", fields="audit_events.event, detail (handle, domain, scopes, HTTP status codes)",
      source="Backend", destination="Supabase", purpose="Security audit trail", required="required", user_provided="no",
      from_shopline="partly", personal="POSSIBLY (store handle/domain)", sensitive="no", stored="yes", retention=RET,
      deletion="Erase deletes rows for that shop", security="RLS: no client access", evidence="store.audit calls in oauth.py/webhooks.py", status="CONFIRMED BY CODE"),
 dict(id="D13", category="Errors", fields="errors.source, kind, message (redacted, ≤500 chars), shop_id, context.ref",
      source="Backend", destination="Supabase; Slack/Discord (kind + short text only)", purpose="Monitoring and alerts",
      required="required", user_provided="no", from_shopline="no", personal="linked to store id only", sensitive="no",
      stored="yes", retention=RET, deletion="On erase shop_id set to null", security="Secret patterns redacted; exception text never stored for API errors",
      evidence="alerts.Alerter; pgstore.record_error; main._unhandled", status="CONFIRMED BY CODE"),
 dict(id="D14", category="OAuth state", fields="oauth_states.state, handle, expires_at", source="Backend", destination="Supabase",
      purpose="CSRF protection for install", required="required", user_provided="no", from_shopline="no", personal="no",
      sensitive="no", stored="yes (≤10 min)", retention="Deleted on use; expired rows purged every drain", deletion="Automatic",
      security="Single use (DELETE…RETURNING)", evidence="pgstore.pop_oauth_state/purge_expired", status="CONFIRMED BY CODE"),
 dict(id="D15", category="Session token", fields="signed {shop_id, expiry}", source="Backend", destination="Client (future iOS app)",
      purpose="Authenticate API calls", required="required", user_provided="no", from_shopline="no", personal="store identifier",
      sensitive="credential", stored="Not stored server-side. iOS: Keychain, kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly (no iCloud sync)", retention="12 h sliding expiry; revoked on uninstall or account deletion",
      deletion="Expiry", security="HMAC-SHA256; revocation check per request", evidence="main.issue_session/read_session/shop(); ios/MAAShopline/Core/Keychain.swift", status="CONFIRMED BY CODE"),
 dict(id="D16", category="Provider health / quota", fields="provider_state.breaker, bucket", source="Backend", destination="Supabase",
      purpose="Circuit breakers and quota", required="required", user_provided="no", from_shopline="no", personal="no",
      sensitive="no", stored="yes", retention="Bucket resets daily", deletion="n/a", security="RLS: no client access",
      evidence="pgstore.save_provider_state", status="CONFIRMED BY CODE"),
 dict(id="D17", category="Request metadata / IP addresses", fields="Client IP, user agent, request path",
      source="Client", destination="Render platform", purpose="Hosting", required="technical", user_provided="no", from_shopline="no",
      personal="YES (IP address)", sensitive="no", stored="App access log disabled (--no-access-log); Render platform/edge logs: UNKNOWN",
      retention=UNK, deletion=UNK, security="TLS", evidence="render.yaml startCommand", status="UNKNOWN"),
]

# ---------------- providers ----------------
PROV = [
 dict(provider="SHOPLINE", service="OAuth, Admin API, webhooks", purpose="Source of store data; install lifecycle",
      data="Store identity, tokens, order/customer/product data (payloads in transit)", personal="Yes (end-customer data in webhook payloads)",
      classes="n/a (source)", role=LR, location=UNK, transfer=UNK, dpa=UNK, retention=UNK,
      evidence="app/shopline/*", status="CONFIRMED BY CODE — relationship governed by signed agreement (6 Aug 2026)"),
 dict(provider="Supabase", service="Postgres, RLS, pg_cron, pg_net, Vault", purpose="All persistent state",
      data="D01–D07, D09–D14, D16", personal="Yes", classes="all (storage)", role=LR + " (likely processor to MAA)",
      location="UNKNOWN — read project region from the live dashboard", transfer=UNK, dpa=UNK, retention=UNK,
      evidence="supabase/migrations; app/pgstore.py", status="CONFIRMED BY CODE"),
 dict(provider="Render", service="Web service hosting (FastAPI)", purpose="Runs the API and job drain",
      data="All data in transit through the API; D17", personal="Yes (in transit / memory)", classes="all (compute)",
      role=LR, location="render.yaml proposes frankfurt — INFRA DECISION, not deployed", transfer=UNK, dpa=UNK, retention=UNK,
      evidence="render.yaml", status="CONFIRMED BY CODE (configuration); NOT DEPLOYED"),
 dict(provider="NVIDIA (API Catalog)", service="Model inference", purpose="Primary provider for most roles",
      data="Prompts/context for eligible calls", personal="Only if approved for merchant data — currently NOT approved, so only PUBLIC calls",
      classes="PUBLIC only until approved", role=LR, location=UNK, transfer=UNK, dpa=UNK, retention=UNK,
      evidence="providers.BASE; registry.eligible; APPROVED_FOR_MERCHANT_DATA=set()", status="CONFIRMED BY CODE"),
 dict(provider="Groq", service="Model inference (gpt-oss-20b/120b)", purpose="Backup provider",
      data="Prompts for eligible calls", personal="Same rule as NVIDIA", classes="PUBLIC only until approved",
      role=LR, location=UNK, transfer=UNK, dpa=UNK, retention=UNK, evidence="providers.BASE; registry", status="CONFIRMED BY CODE"),
 dict(provider="OpenRouter", service="Model routing (free models)", purpose="Tertiary",
      data="Prompts for PUBLIC calls only", personal="No — code forbids non-PUBLIC data and non-':free' models",
      classes="PUBLIC only (hard rule)", role=LR, location=UNK, transfer=UNK, dpa=UNK,
      retention="UNKNOWN — free-model providers may log prompts; this is why the code restricts it to PUBLIC",
      evidence="registry.eligible", status="CONFIRMED BY CODE"),
 dict(provider="Google (AI Studio / Gemini API)", service="Model inference via OpenAI-compatible endpoint", purpose="NLP/embeddings per plan",
      data="Prompts for eligible calls", personal="Same rule as NVIDIA", classes="PUBLIC only until approved",
      role=LR, location=UNK, transfer=UNK, dpa=UNK, retention="UNKNOWN — AI Studio terms differ by paid/unpaid tier; verify",
      evidence="providers.BASE['gemini']; no role uses it yet", status="CONFIRMED BY CODE (wired, unused)"),
 dict(provider="GitHub", service="Repository, Actions CI, drain-backup schedule", purpose="Source control and scheduling",
      data="Source code; DRAIN_URL/DRAIN_SECRET as encrypted secrets; no merchant data", personal="No",
      classes="none", role="n/a", location=UNK, transfer="n/a", dpa=UNK, retention=UNK,
      evidence=".github/workflows/*", status="CONFIRMED BY CODE"),
 dict(provider="Slack or Discord", service="Incoming webhook alerts", purpose="Operational alerts",
      data="Alert kind, route, job kind, provider key; secrets redacted; no merchant content", personal="No (store UUID may appear in refs)",
      classes="none", role=LR, location=UNK, transfer=UNK, dpa=UNK, retention=UNK,
      evidence="app/alerts.py", status="CONFIRMED BY CODE (provider not yet chosen)"),
 dict(provider="Apple (App Store, APNs, frameworks)", service="Distribution, push", purpose="iOS app",
      data="App distribution/TestFlight; no Apple SDK receives app data (no APNs, analytics or crash SDK in code)", personal="Apple's own processing as distributor", classes="none", role=LR, location=UNK, transfer=UNK,
      dpa=UNK, retention=UNK, evidence="ios/project.yml (no packages); no UserNotifications/APNs code", status="CONFIRMED BY CODE"),
 dict(provider="Vercel", service="—", purpose="Not used by this repository", data="none", personal="n/a", classes="n/a",
      role="n/a", location="n/a", transfer="n/a", dpa="n/a", retention="n/a", evidence="no reference in code", status="NOT IMPLEMENTED"),
]
NOT_FOUND = "Snowflake, OpenAI API (gpt-oss models are served by NVIDIA/Groq, not OpenAI), Meta, Sentry or any analytics SDK: no reference found in code. Absence in this repo does not prove the future iOS app will not use them."

# ---------------- flows ----------------
FLOWS = [
 ("SHOPLINE", "Render API /auth/shopline/callback", "OAuth code, handle, HMAC params", "Install", "HTTPS", "UNKNOWN", "Token encrypted in Supabase"),
 ("Render API", "SHOPLINE token endpoint", "App key/secret, code", "Obtain access token", "HTTPS (signed)", "UNKNOWN", "No"),
 ("SHOPLINE", "Render API /webhooks/shopline", "Order/customer/product JSON", "Change notifications", "HTTPS + HMAC", "UNKNOWN", "Metadata + object id only"),
 ("Future iOS app", "Render API /api/*", "Session token, Advisor question", "Product features", "HTTPS", "UNKNOWN", "Question kept until job terminal"),
 ("Render API", "Supabase Postgres", "All stored categories", "Persistence", "TLS (pooler)", "UNKNOWN — region not read", "Yes"),
 ("Render API", "NVIDIA / Groq / Gemini", "Prompt + context", "Inference", "HTTPS", "UNKNOWN", "Trace row only (no content)"),
 ("Render API", "OpenRouter", "PUBLIC prompts only", "Inference (tertiary)", "HTTPS", "UNKNOWN", "Trace row only"),
 ("Supabase pg_cron/pg_net", "Render /internal/jobs/drain", "Bearer secret; no data", "Trigger job drain", "HTTPS", "UNKNOWN", "No"),
 ("GitHub Actions", "Render /internal/jobs/drain", "Bearer secret; no data", "Backup trigger", "HTTPS", "UNKNOWN", "No"),
 ("Render API", "Slack/Discord", "Alert code + short text", "Alerts", "HTTPS", "UNKNOWN", "Provider-side"),
]

def md_table(rows, cols):
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in cols) + " |\n" for r in rows)

def w(name, body):
    (OUT / name).write_text(body.strip() + "\n")

def main():
    OUT.mkdir(exist_ok=True)
    hdr = lambda t: f"# {t}\n\n_Generated {DATE} by scripts/gen_compliance.py from the implemented code._\n\n{SCOPE_NOTE}\n\n"
    # 01
    cols = ["id","category","fields","source","destination","purpose","personal","stored","retention","deletion","security","evidence","status"]
    w("MAA_SHOPLINE_IOS_DATA_INVENTORY.md", hdr("01 — App Data Inventory") + md_table(INV, cols) +
      "\n**No special-category data is intentionally collected.** Free-text fields (D05, D09) could contain anything a merchant types.\n")
    (OUT / "data_inventory.json").write_text(json.dumps({"generated": DATE, "scope": SCOPE_NOTE, "items": INV}, indent=2, ensure_ascii=False))
    # 02
    fl = [dict(zip(["source","destination","data","purpose","protocol","leaves_region","persisted"], f)) for f in FLOWS]
    mer = """```mermaid
flowchart LR
  SL[SHOPLINE] -- OAuth + webhooks (HMAC) --> API[Render: FastAPI]
  IOS[iOS app — NOT IMPLEMENTED] -. HTTPS session .-> API
  API -- all persistence --> DB[(Supabase Postgres)]
  API -- PUBLIC calls only until providers approved --> NV[NVIDIA / Groq / Gemini]
  API -- PUBLIC only, :free models --> OR[OpenRouter]
  CRON[pg_cron → pg_net] -- bearer secret --> API
  GH[GitHub Actions cron] -- bearer secret --> API
  API -- alert codes only --> AL[Slack / Discord]
```"""
    w("MAA_SHOPLINE_IOS_DATA_FLOW.md", hdr("02 — Data Flow Map") +
      "Merchant-confidential data can reach a model provider only if that provider is added to `APPROVED_FOR_MERCHANT_DATA` (currently empty), so today every merchant-data AI call queues instead of leaving MAA's infrastructure. Webhook bodies are parsed in memory and not stored.\n\n" +
      mer + "\n\n" + md_table(fl, list(fl[0].keys())) + "\n'Leaves region' is UNKNOWN everywhere because no provider region was read from a live dashboard.\n")
    # 03
    pcols = ["provider","service","purpose","data","personal","classes","role","location","transfer","dpa","retention","evidence","status"]
    w("MAA_SHOPLINE_IOS_PROVIDER_REGISTER.md", hdr("03 — Provider / Subprocessor Register") + md_table(PROV, pcols) +
      f"\n**Not found:** {NOT_FOUND}\n\nLast reviewed: {DATE}. For each UNKNOWN, review the provider's Terms of Service, Privacy Policy, Data Processing Addendum and subprocessor list, and record the exact version/date here.\n")
    with open(OUT / "provider_register.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=pcols); wr.writeheader(); wr.writerows(PROV)
    (OUT / "provider_register.json").write_text(json.dumps(PROV, indent=2, ensure_ascii=False))
    # 04 / 05 / 06
    w("MAA_SHOPLINE_IOS_SDK_INVENTORY.md", hdr("04 — Third-Party SDK Inventory") +
      "**iOS: no third-party SDKs.** `ios/project.yml` declares no Swift packages, CocoaPods or frameworks. The app uses only Apple frameworks: SwiftUI, Foundation, Security (Keychain), AuthenticationServices (ASWebAuthenticationSession), Observation. Network destinations: the configured MAA API host only (API_BASE_URL); the SHOPLINE authorization page opens inside ASWebAuthenticationSession.\n\n"
      "Backend dependencies (server-side, not shipped in the app): fastapi, uvicorn, httpx, cryptography, psycopg, psycopg-pool (requirements.txt). None performs analytics or tracking.\n\n"
      "Nothing to declare for third-party SDKs. Re-check if any package is added later.\n")
    w("MAA_SHOPLINE_IOS_PERMISSIONS_AUDIT.md", hdr("05 — iOS Permissions Audit") +
      "**No runtime permission is requested.** The Info.plist (generated from `ios/project.yml`) contains no NS*UsageDescription keys. Camera, Photos, Location, Contacts, Microphone, Bluetooth, Notifications, ATT, Calendar, Files, Face ID and Sign in with Apple: **not used**.\n\n"
      "Other declarations: custom URL scheme `maashopline` (OAuth callback captured by ASWebAuthenticationSession, ephemeral browser session); `ITSAppUsesNonExemptEncryption=false` (HTTPS only — confirm the export-compliance answer in App Store Connect).\n\n"
      "Not implemented: push notifications for queued jobs (the app polls instead). Adding them later requires notification authorisation and an APNs entry in the provider register.\n")
    w("MAA_SHOPLINE_IOS_APP_STORE_PRIVACY_MATRIX.md", hdr("06 — App Store Connect Privacy Matrix") +
      "Based on the implemented iOS source and `PrivacyInfo.xcprivacy`. Confidence MEDIUM until the compiled build is inspected. Final answers are MAA's responsibility in App Store Connect.\n\n" +
      md_table([
        dict(category="Contact Info", collected="Not by implemented API", linked="-", tracking="No", evidence="no endpoint accepts contact info"),
        dict(category="User Content → Other User Content", collected="YES (Advisor questions) — purpose: App Functionality", linked="Yes (store)", tracking="No", evidence="AdvisorView.swift; APIClient.ask"),
        dict(category="Identifiers → User ID", collected="YES (store id inside the session token) — purpose: App Functionality", linked="Yes", tracking="No", evidence="Keychain.swift; APIClient Bearer header"),
        dict(category="Usage Data", collected="Not implemented", linked="-", tracking="No", evidence="no analytics"),
        dict(category="Diagnostics", collected="No (no crash/analytics SDK; server errors are not collected from the device)", linked="-", tracking="No", evidence="no SDKs in project.yml"),
        dict(category="Financial Info / Purchases", collected="Store order data is SHOPLINE-sourced, not collected from the app user — " + LR, linked="-", tracking="No", evidence="orders_snapshot (not populated)"),
        dict(category="Location, Health, Contacts, Browsing/Search History, Sensitive Info", collected="No", linked="-", tracking="No", evidence="no code"),
      ], ["category","collected","linked","tracking","evidence"]) + "\nTracking: nothing in the implemented system links data with third-party data for advertising, so ATT is not indicated — re-verify against the final app.\n")
    # 07 GDPR
    acts = [
     dict(activity="Store installation & authentication", subjects="Merchant (possibly sole trader)", data="D01–D03, D14, D15", legal_basis="Candidate: contract — " + LR, transfer="UNKNOWN", risk="Low"),
     dict(activity="Webhook ingestion", subjects="Merchant's customers (end customers)", data="D07, D08", legal_basis=LR + " (MAA likely processor for merchant; confirm)", transfer="UNKNOWN", risk="Medium"),
     dict(activity="Order snapshot analytics (Health Check)", subjects="End customers (pseudonymised)", data="D06", legal_basis=LR, transfer="UNKNOWN", risk="Medium — NOT YET ACTIVE"),
     dict(activity="AI Advisor", subjects="Merchant; anyone named in free text", data="D09, D10, D11", legal_basis="Candidate: contract — " + LR, transfer="Blocked until providers approved", risk="Medium"),
     dict(activity="Monitoring & security logging", subjects="Merchant", data="D11–D13, D17", legal_basis="Candidate: legitimate interests — " + LR, transfer="UNKNOWN", risk="Low"),
    ]
    w("MAA_SHOPLINE_IOS_GDPR_PROCESSING_MATRIX.md", hdr("07 — GDPR / Privacy Processing Matrix") + md_table(acts, list(acts[0].keys())) +
      "\nNo lawful basis is asserted. Controller/processor roles for MAA, SHOPLINE and each merchant require legal analysis of the signed agreement and SHOPLINE's platform terms. Automated decision-making with legal effect: none implemented.\n")
    # 08
    xfer = [dict(provider=p["provider"], data=p["data"], location=p["location"], mechanism=p["transfer"], dpa=p["dpa"],
                 status="Assessment not started", next_action="Read region + DPA/SCC terms; record version") for p in PROV if p["status"] != "NOT IMPLEMENTED" and p["provider"] != "GitHub"]
    w("MAA_SHOPLINE_IOS_INTERNATIONAL_TRANSFER_REGISTER.md", hdr("08 — International Transfer Register") +
      "MAA is a New Mexico LLC operating from Dubai; merchants may be anywhere SHOPLINE operates. Which transfer regimes apply (EU/UK GDPR, UAE PDPL, others) is " + LR + ".\n\n" + md_table(xfer, list(xfer[0].keys())) +
      "\nNo SCC or adequacy claim is made for any provider.\n")
    # 09
    w("MAA_SHOPLINE_IOS_PRIVACY_POLICY_SOURCE_PACK.md", hdr("09 — Privacy Policy Source Pack") + f"""
1. **MAA identity:** Marketing As Art AI LLC, New Mexico, USA; contact address to be confirmed by MAA.
2. **App identity:** MAA × SHOPLINE merchant app (iOS NOT IMPLEMENTED; backend described here).
3. **Users:** SHOPLINE merchants who install the app. End customers are data subjects but not users.
4. **Data collected from the merchant:** Advisor questions (D09); onboarding answers and consent (D04–D05, not yet implemented).
5. **Data received from SHOPLINE:** store identity, access token, scopes, webhook payloads (parsed, not stored), order snapshots (not yet populated).
6. **Other integrations:** none implemented (socials, reviews: not implemented).
7. **Publicly sourced data:** none implemented.
8. **Technical data:** IP/request metadata at Render (D17), errors, traces.
9. **Purposes:** see inventory 'purpose' column.
10. **Legal bases:** candidates only in 07 — {LR}.
11. **Recipients:** see 03. Model providers receive merchant data only after approval (none approved today).
12. **International transfers:** see 08 — {LR}.
13. **Retention:** {RET} for most categories; defined exceptions in 10.
14. **Deletion:** uninstall deletes the access token; full erasure via admin endpoint; no merchant self-service deletion yet.
15. **User rights:** no self-service access/export/deletion endpoint implemented.
16. **Consent:** ledger schema exists; capture NOT IMPLEMENTED.
17. **Automated processing/profiling:** AI recommendations to the merchant; no automated decisions with legal effect.
18. **AI processing:** routing rules per data class (registry.eligible); SENSITIVE data never sent; OpenRouter PUBLIC-only.
19. **Security:** RLS, AES-GCM tokens, HMAC webhooks, secret redaction, isolation checks.
20. **Contact:** to be supplied by MAA.
21. **Complaints/DPA:** {LR}.
22. **Source disclosure:** data comes from SHOPLINE on the merchant's authorisation.
23. **Open questions:** roles, bases, transfers, retention periods, provider terms.
""")
    # 10
    rcols = ["id","category","stored","retention","deletion"]
    w("MAA_SHOPLINE_IOS_RETENTION_DELETION.md", hdr("10 — Retention & Deletion Matrix") + md_table(INV, rcols) +
      "\nBackups: Supabase backup retention applies to deleted rows — UNKNOWN until the plan's backup settings are read. Third-party deletion (providers): UNKNOWN per provider.\n")
    # 11 gaps
    gaps = [
     ("HIGH","iOS app not yet compiled or run","ios/","Static review only; runtime behaviour unverified","Run .github/workflows/ios.yml; fix any compile errors","Yes","No","Open"),
     ("HIGH","Retention periods undefined for most tables","10","Unbounded storage of personal data","MAA decides periods; implement purge jobs","No","Yes","Open"),
     ("MEDIUM","No self-service data export (deletion now in-app)","main.py","Access/portability requests are manual","Add an export endpoint","No","Yes","Open"),
     ("FIXED","In-app account deletion","POST /api/account/delete; SettingsView","Apple 5.1.1(v)","Implemented + tested","-","-","Fixed"),
     ("HIGH","Provider data terms unverified; approved list empty","registry.py","AI features queue for merchant data","Record terms, approve providers","No","Yes","Open (by design)"),
     ("MEDIUM","Consent capture not implemented","consent_ledger","§7.2 consent not evidenced","Build consent endpoint + UI","No","Yes","Open"),
     ("MEDIUM","No server-side rate limiting","main.py","Abuse / quota drain","Add per-shop limits","No","Best practice","Open"),
     ("MEDIUM","Webhook timestamp header unconfirmed","webhooks._sent_at","Replay window relies on durable dedupe only","Set SHOPLINE_WEBHOOK_TS_HEADER once confirmed","No","Best practice","Open"),
     ("MEDIUM","Render/Supabase platform log retention unknown","render.yaml","IPs retained by platforms","Read and record platform settings","No","Yes","Open"),
     ("LOW","Session key derived from token-encryption key","main.py","Key rotation logs everyone out","Separate SESSION_SECRET","No","Best practice","Open"),
     ("FIXED","OAuth code in access logs","render.yaml","Credential in logs","--no-access-log","-","-","Fixed"),
     ("FIXED","Advisor question kept indefinitely","pgstore","Unbounded retention","Context dropped at terminal state","-","-","Fixed"),
     ("FIXED","In-memory state (queue, dedupe, breakers)","store.py","Lost on restart; replay possible","PgStore + provider_state","-","-","Fixed"),
    ]
    gcols = ["severity","finding","evidence","risk","remediation","blocks_app_store","privacy_requirement","status"]
    w("MAA_SHOPLINE_IOS_PRIVACY_GAPS.md", hdr("11 — Privacy / Security Gap Register") + md_table([dict(zip(gcols, g)) for g in gaps], gcols))
    # 12 evidence
    ev = [
     ("Merchant data cannot reach unapproved providers","registry.eligible; tests/test_pgstore.py::test_confidential_job_never_reaches_unapproved_provider","High"),
     ("Cross-tenant reads/writes denied by RLS","tests/test_rls.py (16 tests, Postgres 16)","High"),
     ("Ops tables closed to clients","tests/test_pgstore.py::test_ops_tables_closed_to_clients","High"),
     ("Webhook dedupe survives restart","tests/test_pgstore.py::test_webhook_dedupe_survives_restart","High"),
     ("Uninstall destroys token and revokes sessions","test_install_lookup_uninstall_destroys_token; test_uninstall_revokes_sessions","High"),
     ("Shop erasure removes all keyed data","test_erase_shop_removes_everything_keyed_to_it","High"),
     ("Alerts contain no secrets","test_alerts_recorded_deduped_and_redacted","High"),
     ("No credentials in tree or git history","scripts/secret_scan.py (tree + --history)","High"),
     ("Provider regions / DPAs","None — not verified","None"),
    ]
    w("MAA_SHOPLINE_IOS_COMPLIANCE_EVIDENCE_INDEX.md", hdr("12 — Compliance Evidence Index") +
      md_table([dict(conclusion=a, evidence=b, confidence=c, verified=DATE) for a, b, c in ev], ["conclusion","evidence","confidence","verified"]))
    # 13 handoff + human review
    human = [
     "Controller/processor roles of MAA, SHOPLINE and merchants under the signed agreement.",
     "Lawful basis for each processing activity in 07.",
     "Which privacy regimes apply (EU/UK GDPR, UAE PDPL, US state laws) given a NM LLC operating from Dubai.",
     "Transfer mechanism for each provider in 08 once regions/DPAs are read.",
     "Retention period for every category marked RETENTION POLICY NOT CURRENTLY DEFINED.",
     "Which providers to approve for merchant-confidential data after reading their terms.",
     "Whether end-customer order data may be used for Health Check under SHOPLINE's platform terms.",
     "Final Apple App Privacy answers (draft in 06) and the export-compliance (encryption) answer.",
    ]
    w("MAA_SHOPLINE_IOS_HUMAN_REVIEW_REQUIRED.md", "# MAA SHOPLINE iOS — HUMAN REVIEW REQUIRED\n\n" + "".join(f"{i}. {h}\n" for i, h in enumerate(human, 1)))
    w("MAA_SHOPLINE_IOS_PRIVACY_COMPLIANCE_HANDOFF.md", hdr("13 — Executive Handoff") + f"""
**A. Data processed:** store identity, encrypted tokens, webhook metadata, Advisor questions (until the job finishes), AI outputs, traces, audit and error logs. Order and customer snapshots are designed but not populated.
**B. Where it goes:** Render (compute) and Supabase (storage). AI providers receive merchant data only after approval, and none are approved yet. Slack or Discord receive alert codes only.
**C. Providers:** see 03. Every provider's terms are UNKNOWN.
**D. Personal data:** yes — store handles (possible sole traders), free text, pseudonymised end-customer references (when enabled), end-customer data in webhook payloads (in transit only), and IPs at the hosting edge.
**E. Special-category data:** not intentionally collected; free text could contain it.
**F. Transfers:** all UNKNOWN pending region and DPA review.
**G. Retention and deletion:** tokens are deleted on uninstall; Advisor context is dropped when its job finishes; OAuth states are purged automatically; full erasure is available through the admin endpoint; everything else is {RET}.
**H. Apple privacy:** cannot be finalised until the iOS app exists; see the draft in 06.
**I–K. GDPR and legal:** see 07, 08 and HUMAN REVIEW REQUIRED.
**L. Engineering remediation:** build the iOS app, self-service export and deletion, consent capture, rate limiting, and purge jobs once retention periods are set.
**M. Documentation only:** provider terms register, region confirmation.
**N. Before App Store submission:** first successful CI compile and TestFlight run, final App Privacy answers (draft in 06), live privacy policy URL, export-compliance answer. In-app account deletion is implemented.
**O. Can wait:** session-key separation, timestamp header.
**P. Next steps:** (1) read regions and DPAs for Supabase, Render, NVIDIA, Groq and Google; (2) legal review of the list; (3) set retention periods; (4) run the iOS CI pipeline and confirm the compiled app matches 04–06.
""")

if __name__ == "__main__":
    main(); print("compliance package written to", OUT)
