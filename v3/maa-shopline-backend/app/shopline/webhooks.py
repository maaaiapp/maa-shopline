"""Webhook pipeline: verify HMAC → authenticate shop → authorize topic →
deduplicate → acknowledge → process → persist → reconcile.

SHOPLINE requires 200 within 5 s and may deliver duplicates; X-Shopline-Webhook-Id
is stable across retries and is the idempotency key.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.shopline.oauth import valid_handle
from app.shopline.signing import verify_webhook
from app.store import Store

# Topics we subscribe to. Only the lifecycle topic is actionable until TD-06
# confirms the order/customer/product topic list.
ALLOWED_TOPICS = {"app/uninstalled", "apps/uninstalled", "orders/create", "orders/update",
                  "customers/create", "customers/update", "products/update",
                  "customers/redact", "merchants/redact"}


@dataclass
class WebhookResult:
    status: int
    outcome: str  # rejected_signature | rejected_stale | rejected_shop | ignored_topic | duplicate | accepted


def _sent_at(h: dict[str, str], ts_header: str):
    """Parse the sender timestamp if SHOPLINE's header name has been configured.
    The header name is NOT hard-coded: it must come from SHOPLINE's docs/partner team."""
    if not ts_header or ts_header.lower() not in h:
        return None
    from datetime import datetime, timezone
    raw = h[ts_header.lower()].strip()
    try:
        v = float(raw)
        return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None


def receive(store: Store, secret: str, headers: dict[str, str], raw: bytes,
            ts_header: str = "", max_age_s: int = 300, default_topic: str = "") -> WebhookResult:
    h = {k.lower(): v for k, v in headers.items()}
    body_hash = hashlib.sha256(raw).hexdigest()
    if not verify_webhook(raw, h.get("x-shopline-hmac-sha256"), secret):
        store.audit("webhook_bad_signature", {"body_sha256": body_hash})
        return WebhookResult(401, "rejected_signature")
    domain = h.get("x-shopline-shop-domain", "")
    handle = domain.split(".")[0] if domain.endswith(".myshopline.com") else ""
    inst = store.get_installation(handle) if valid_handle(handle) else None
    if not inst:
        store.audit("webhook_unknown_shop", {"domain": domain[:128]})
        return WebhookResult(200, "rejected_shop")  # ack so SHOPLINE stops retrying; nothing persisted
    topic = h.get("x-shopline-topic", "") or default_topic
    if topic not in ALLOWED_TOPICS:
        return WebhookResult(200, "ignored_topic")
    sent_at = _sent_at(h, ts_header)
    if sent_at is not None:
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - sent_at).total_seconds()
        if age > max_age_s or age < -60:
            store.audit("webhook_stale", {"age_s": int(age)})
            return WebhookResult(401, "rejected_stale")
    wid = h.get("x-shopline-webhook-id") or body_hash
    fresh = store.insert_webhook_event(wid, {"shop_id": inst["shop_id"], "topic": topic,
                                             "body_sha256": body_hash, "status": "received",
                                             "sent_at": sent_at.isoformat() if sent_at else None})
    if not fresh:
        return WebhookResult(200, "duplicate")
    # Processing is enqueued, never done inline (5 s deadline). Payload is untrusted data.
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        store.audit("webhook_bad_json", {"webhook_id": wid})
        return WebhookResult(200, "accepted")
    if topic in ("app/uninstalled", "apps/uninstalled"):
        store.mark_uninstalled(handle)
        store.audit("uninstalled", {"shop_id": inst["shop_id"]})
    elif topic == "merchants/redact":
        # Compliance: erase everything MAA holds for this shop (erase_shop writes its own audit row).
        erased = hasattr(store, "erase_shop") and store.erase_shop(inst["shop_id"])
        if not erased:
            store.audit("merchant_redact_noop", {"shop_id": inst["shop_id"]})
    elif topic == "customers/redact":
        # Compliance: MAA keeps no per-customer records, so record the request (ids only, no PII).
        cust = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
        store.audit("customer_redact_requested", {"shop_id": inst["shop_id"],
                                                  "customer_id": str(cust.get("id", ""))[:64]})
    else:
        store.enqueue({"kind": "sync", "shop_id": inst["shop_id"], "topic": topic,
                       "object_id": str(payload.get("id", ""))[:64], "idempotency_key": f"wh:{wid}"})
    return WebhookResult(200, "accepted")
