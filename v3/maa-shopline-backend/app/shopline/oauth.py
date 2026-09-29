"""SHOPLINE OAuth install flow (developer.shopline.com/docs/apps/api-instructions-for-use/app-authorization).

Status: PUBLIC_DOC — built to the published contract, not yet run against a
sandbox store (Kickoff Pack TD-09 open).
"""
from __future__ import annotations

import json
import re
import secrets
import time
from urllib.parse import quote

import httpx

from app.config import Settings
from app.policy.access_policy import require
from app.security.crypto import TokenCipher
from app.shopline.signing import sign_post, verify_params
from app.store import Store

HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")  # SSRF guard: only <handle>.myshopline.com


class OAuthError(Exception):
    pass


def valid_handle(handle: str) -> bool:
    return bool(HANDLE_RE.fullmatch(handle or ""))


IOS_STATE_SUFFIX = "~ios"   # token_urlsafe never emits '~'; state is server-issued and single-use, so unforgeable


def authorize_url(s: Settings, store: Store, handle: str, client: str = "web") -> str:
    require("oauth_install")
    if not valid_handle(handle):
        raise OAuthError("invalid store handle")
    state = secrets.token_urlsafe(24) + (IOS_STATE_SUFFIX if client == "ios" else "")
    store.save_oauth_state(state, handle)
    return (f"https://{handle}.myshopline.com/admin/oauth-web/#/oauth/authorize"
            f"?appKey={quote(s.shopline_app_key)}&responseType=code&scope={quote(s.shopline_scopes)}"
            f"&redirectUri={quote(s.shopline_redirect_uri, safe='')}&customField={quote(state)}")


def handle_callback(s: Settings, store: Store, params: dict[str, str], http: httpx.Client) -> str:
    """Verify signature + state, exchange code, store encrypted token. Returns shop_id."""
    if not verify_params(params, s.shopline_app_secret):
        store.audit("oauth_bad_signature", {"handle": params.get("handle", "")[:64]})
        raise OAuthError("signature")
    handle = params.get("handle", "")
    state_handle = store.pop_oauth_state(params.get("customField", ""))
    if not valid_handle(handle) or state_handle != handle:
        store.audit("oauth_bad_state", {"handle": handle[:64]})
        raise OAuthError("state")
    body = json.dumps({"code": params.get("code", "")}, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    r = http.post(f"https://{handle}.myshopline.com/admin/oauth/token/create", content=body,
                  headers={"Content-Type": "application/json", "appkey": s.shopline_app_key,
                           "timestamp": ts, "sign": sign_post(body, ts, s.shopline_app_secret)},
                  timeout=15)
    data = r.json().get("data") if r.status_code == 200 else None
    if not data or not data.get("accessToken"):
        store.audit("oauth_token_failed", {"handle": handle, "status": r.status_code})
        raise OAuthError("token exchange")
    enc = TokenCipher(s.token_encryption_key).encrypt(data["accessToken"], aad=handle)
    scopes = [x for x in (data.get("scope") or "").split(",") if x]
    shop_id = store.upsert_installation(handle, enc, data.get("expireTime", ""), scopes)
    store.audit("installed", {"shop_id": shop_id, "scopes": scopes})
    return shop_id


def refresh_token(s: Settings, store: Store, handle: str, http: httpx.Client) -> bool:
    """Tokens last ~10h. On failure the shop goes to 'Token expired' state (screen 30)."""
    inst = store.get_installation(handle)
    if not inst or inst.get("status") != "active":
        return False
    body, ts = "{}", str(int(time.time() * 1000))
    r = http.post(f"https://{handle}.myshopline.com/admin/oauth/token/refresh", content=body,
                  headers={"Content-Type": "application/json", "appkey": s.shopline_app_key,
                           "timestamp": ts, "sign": sign_post(body, ts, s.shopline_app_secret)},
                  timeout=15)
    data = r.json().get("data") if r.status_code == 200 else None
    if not data or not data.get("accessToken"):
        store.audit("token_refresh_failed", {"handle": handle, "status": r.status_code})
        inst["status"] = "token_expired"
        return False
    inst["enc_token"] = TokenCipher(s.token_encryption_key).encrypt(data["accessToken"], aad=handle)
    inst["expires_at"] = data.get("expireTime", "")
    return True
