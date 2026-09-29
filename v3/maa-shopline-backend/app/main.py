"""HTTP API for the iOS client.

Tenant identity: an HMAC-signed session issued only at OAuth completion and bound
to shop_id. No endpoint accepts a shop id from the client. Errors are mapped to UI
states (loading/empty/unavailable/degraded/queued/insufficient); raw exceptions
and provider messages are never returned.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import date

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import IsolationError, Settings, assert_isolated
from app.inference.gateway import Gateway, Policy
from app.inference.providers import OpenAICompatAdapter
from app.inference.registry import DataClass
from app.inference.validators import Contract
from app.intelligence.health_check import score
from app.policy.access_policy import CAPABILITIES, CapabilityBlocked
from app.shopline import oauth, webhooks
from app.store import MemoryStore, Store

SESSION_TTL_S = 12 * 3600


def issue_session(secret: str, shop_id: str, now: float | None = None) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"s": shop_id, "e": int((now or time.time()) + SESSION_TTL_S)}).encode()).decode()
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_session(secret: str, token: str) -> str | None:
    try:
        body, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest(), sig):
            return None
        d = json.loads(base64.urlsafe_b64decode(body))
        return d["s"] if d["e"] > time.time() else None
    except Exception:
        return None


def create_app(settings: Settings | None = None, store: Store | None = None,
               gateway: Gateway | None = None, http: httpx.Client | None = None) -> FastAPI:
    s = settings or Settings.from_env()
    assert_isolated(s)                       # refuses to boot in prod if not isolated
    if store is None:
        if s.database_url:
            from app.pgstore import PgStore
            store = PgStore(s.database_url)
        elif s.env == "prod":
            raise IsolationError("DATABASE_URL required in production; in-memory store is test-only")
        else:
            store = MemoryStore()
    st = store
    from app.alerts import Alerter
    alert = Alerter(st, s.alert_webhook_url, s.env)
    client = http or httpx.Client()
    gw = gateway or Gateway(OpenAICompatAdapter({"nvidia": s.nvidia_api_key, "groq": s.groq_api_key,
                                                 "openrouter": s.openrouter_api_key,
                                                 "gemini": s.gemini_api_key}), st)
    session_secret = hashlib.sha256(("session:" + s.token_encryption_key).encode()).hexdigest()
    app = FastAPI(title="MAA × SHOPLINE backend", docs_url=None if s.env == "prod" else "/docs")

    gw.alert = alert

    @app.exception_handler(Exception)
    async def _unhandled(req: Request, exc: Exception):
        # Record class + route only: never the request body, headers or exception text (may carry data).
        alert("unhandled_exception", f"{type(exc).__name__} on {req.method} {req.url.path}", "", source="api")
        return JSONResponse({"state": "error", "reason": "server"}, status_code=500)

    def _bearer_ok(header: str, secret: str) -> bool:
        tok = header.removeprefix("Bearer ").strip()
        return bool(secret) and hmac.compare_digest(tok.encode(), secret.encode())

    def shop(authorization: str = Header(default="")) -> str:
        shop_id = read_session(session_secret, authorization.removeprefix("Bearer ").strip())
        if not shop_id:
            raise HTTPException(401, "unauthenticated")
        inst = st.get_installation_by_shop(shop_id)
        if not inst or inst.get("status") != "active":        # uninstall revokes every issued session
            raise HTTPException(401, "session_revoked")
        return shop_id

    @app.get("/health")
    def health():
        ok = st.ping()
        return JSONResponse({"status": "ok" if ok else "degraded", "db": "ok" if ok else "down"},
                            status_code=200 if ok else 503)

    @app.post("/internal/jobs/drain")
    def drain_jobs(authorization: str = Header(default="")):
        if not s.drain_secret:
            raise HTTPException(404)                             # disabled unless configured
        if not _bearer_ok(authorization, s.drain_secret):
            raise HTTPException(401, "unauthenticated")
        from app.jobs import drain
        return drain(st, gw, alert).__dict__

    @app.get("/admin/summary")
    def admin_summary(authorization: str = Header(default="")):
        if not s.admin_token:
            raise HTTPException(404)
        if not _bearer_ok(authorization, s.admin_token):
            raise HTTPException(401, "unauthenticated")
        return st.admin_summary() if hasattr(st, "admin_summary") else {"store": "memory"}

    @app.post("/admin/jobs/{job_id}/replay")
    def admin_replay(job_id: str, authorization: str = Header(default="")):
        if not s.admin_token:
            raise HTTPException(404)
        if not _bearer_ok(authorization, s.admin_token):
            raise HTTPException(401, "unauthenticated")
        if not hasattr(st, "replay_job") or not st.replay_job(job_id):
            raise HTTPException(409, "not_replayable")
        return {"replayed": job_id}

    @app.get("/auth/shopline/start")
    def start(handle: str, client: str = "web"):
        try:
            return RedirectResponse(oauth.authorize_url(s, st, handle, "ios" if client == "ios" else "web"),
                                    status_code=302)
        except oauth.OAuthError:
            raise HTTPException(400, "invalid_handle")

    @app.get("/auth/shopline/callback")
    def callback(request: Request):
        try:
            shop_id = oauth.handle_callback(s, st, dict(request.query_params), client)
        except oauth.OAuthError:
            raise HTTPException(400, "authorization_failed")
        token = issue_session(session_secret, shop_id)
        if request.query_params.get("customField", "").endswith(oauth.IOS_STATE_SUFFIX):
            # iOS: ASWebAuthenticationSession captures this redirect; token rides in the fragment,
            # which is never sent to any server or written to access logs.
            return RedirectResponse(f"{s.ios_callback_url}#session={token}", status_code=302,
                                    headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        return JSONResponse({"session": token}, headers={"Cache-Control": "no-store"})

    @app.post("/api/session/refresh")
    def refresh(shop_id: str = Depends(shop)):
        return {"session": issue_session(session_secret, shop_id), "expires_in": SESSION_TTL_S}

    @app.post("/api/account/delete")
    def delete_account(shop_id: str = Depends(shop)):
        # App Store guideline 5.1.1(v): in-app deletion. Erases MAA data + the stored SHOPLINE token.
        # The merchant must still uninstall the app inside SHOPLINE to revoke SHOPLINE-side access.
        if not hasattr(st, "erase_shop") or not st.erase_shop(shop_id):
            raise HTTPException(404, "not_found")
        return {"deleted": True, "next": "uninstall_in_shopline_admin"}

    @app.post("/webhooks/shopline")
    async def hook(request: Request):
        raw = await request.body()
        res = webhooks.receive(st, s.shopline_app_secret, dict(request.headers), raw,
                               s.webhook_ts_header, s.webhook_max_age_s)
        return JSONResponse({"ok": res.status == 200}, status_code=res.status)

    @app.get("/api/connection")
    def connection(shop_id: str = Depends(shop)):
        inst = st.get_installation_by_shop(shop_id)
        if not inst:
            return {"state": "disconnected"}
        return {"state": {"active": "connected", "token_expired": "token_expired"}.get(inst["status"], "disconnected"),
                "scopes": inst.get("scopes", []),
                "capabilities": {k: c.status.value for k, c in CAPABILITIES.items()}}

    @app.get("/api/health-check")
    def health_check(shop_id: str = Depends(shop)):
        # Orders read is UNCONFIRMED (TD-01): no SHOPLINE read happens; dimensions are unscored.
        try:
            from app.policy.access_policy import require
            require("orders_read", allow_public_doc=False)
            orders = []  # replaced by snapshot repository once TD-01 confirms the surface
        except CapabilityBlocked:
            orders = None
        return {"state": "degraded" if orders is None else "live",
                "result": score(orders, customers_scope=False, today=date.today())}

    @app.post("/api/advisor")
    def advisor(payload: dict, shop_id: str = Depends(shop)):
        q = str(payload.get("question", ""))[:2000]
        if not q.strip():
            raise HTTPException(422, "empty_question")
        out = gw.generate("advisor_answer", Contract(language="ar" if payload.get("lang") == "ar" else "en"),
                          {"facts": {}, "instruction": f"Merchant question: {q}"},
                          Policy(DataClass.MERCHANT_CONFIDENTIAL, shop_id, safety_required=True))
        return {"state": out.state, "answer": out.value, "generated_at": out.generated_at,
                "job_id": out.job_id, "reason": out.reason}

    @app.post("/admin/shops/{shop_id}/erase")
    def admin_erase(shop_id: str, authorization: str = Header(default="")):
        if not s.admin_token:
            raise HTTPException(404)
        if not _bearer_ok(authorization, s.admin_token):
            raise HTTPException(401, "unauthenticated")
        if not hasattr(st, "erase_shop") or not st.erase_shop(shop_id):
            raise HTTPException(404, "not_found")
        return {"erased": True}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str, shop_id: str = Depends(shop)):
        j = st.get_job(job_id, shop_id) if hasattr(st, "get_job") else None
        if not j:
            raise HTTPException(404, "not_found")                 # also for other shops' jobs: no existence leak
        return {"state": {"done": "ready", "failed": "not_computed", "dead": "not_computed"}.get(j["status"], "preparing")}

    return app
