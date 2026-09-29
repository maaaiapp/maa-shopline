"""SHOPLINE signatures, per developer.shopline.com 'Generate and verify signatures'.

- GET / callback: sort params alphabetically (excluding `sign`), join k=v with '&',
  HMAC-SHA256 with app secret, lowercase hex.
- POST: HMAC-SHA256(body + timestamp_ms), hex, sent in `sign` header.
- Webhook: HMAC-SHA256(raw body), hex, header X-Shopline-Hmac-Sha256.
All comparisons are constant time.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping


def _hmac_hex(secret: str, msg: bytes) -> str:
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def sign_params(params: Mapping[str, str], secret: str) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "sign")
    source = "&".join(f"{k}={v}" for k, v in items)
    return _hmac_hex(secret, source.encode())


def verify_params(params: Mapping[str, str], secret: str, *, max_age_s: int = 600, now_ms: int | None = None) -> bool:
    sign = params.get("sign", "")
    ts = params.get("timestamp", "")
    if not sign or not ts.isdigit():
        return False
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if abs(now_ms - int(ts)) > max_age_s * 1000:
        return False  # replay window
    return hmac.compare_digest(sign_params(params, secret), sign.lower())


def sign_post(body: str, timestamp_ms: str, secret: str) -> str:
    return _hmac_hex(secret, (body + timestamp_ms).encode())


def verify_webhook(raw_body: bytes, header_sig: str | None, secret: str) -> bool:
    if not header_sig or not secret:
        return False
    return hmac.compare_digest(_hmac_hex(secret, raw_body), header_sig.strip().lower())
