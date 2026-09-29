"""Operational alerts to a Slack or Discord incoming webhook.

Messages carry machine codes and counts only: never merchant data, prompts,
tokens or provider responses. Every alert is also written to the errors table,
and duplicates are suppressed by (kind, ref).
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.pgstore import redact


class Alerter:
    def __init__(self, store, webhook_url: str = "", env: str = "dev", http: httpx.Client | None = None):
        self.store, self.url, self.env = store, webhook_url, env
        self.http = http or httpx.Client(timeout=3.0)

    def __call__(self, kind: str, text: str, ref: str = "", source: str = "monitor", shop_id=None) -> None:
        record = getattr(self.store, "record_error", None)
        exists = getattr(self.store, "error_exists", None)
        if ref and exists and exists(kind, ref):
            return                                                  # already alerted
        err_id = record(source, kind, text, shop_id, {"ref": ref}) if record else None
        if not self.url:
            return
        msg = f"[MAA×SHOPLINE {self.env}] {kind}: {redact(text, 300)}"
        host = urlparse(self.url).hostname or ""
        body = {"content": msg} if host.endswith("discord.com") else {"text": msg}
        try:
            r = self.http.post(self.url, json=body)
            if r.status_code < 300 and err_id and hasattr(self.store, "mark_alerted"):
                self.store.mark_alerted(err_id)
        except httpx.HTTPError:
            pass                                                    # alerting must never break the request
