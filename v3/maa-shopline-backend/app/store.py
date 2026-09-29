"""Persistence port. Production uses app.pgstore.PgStore (Postgres/Supabase);
MemoryStore is for unit tests only and is refused in production by create_app."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


class Store(Protocol):
    def save_oauth_state(self, state: str, handle: str, ttl_s: int = 600) -> None: ...
    def pop_oauth_state(self, state: str) -> str | None: ...
    def upsert_installation(self, handle: str, enc_token: str, expires_at: str, scopes: list[str]) -> str: ...
    def get_installation(self, handle: str) -> dict | None: ...
    def mark_uninstalled(self, handle: str) -> None: ...
    def insert_webhook_event(self, webhook_id: str, row: dict) -> bool: ...
    def append_trace(self, row: dict) -> None: ...
    def audit(self, event: str, detail: dict) -> None: ...
    def save_output(self, key: str, value: dict) -> None: ...
    def last_output(self, key: str) -> dict | None: ...
    def enqueue(self, job: dict) -> str: ...


@dataclass
class MemoryStore:
    states: dict[str, tuple[str, float]] = field(default_factory=dict)
    installs: dict[str, dict] = field(default_factory=dict)
    webhooks: dict[str, dict] = field(default_factory=dict)
    traces: list[dict] = field(default_factory=list)
    audits: list[dict] = field(default_factory=list)
    outputs: dict[str, dict] = field(default_factory=dict)
    jobs: list[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def save_oauth_state(self, state, handle, ttl_s=600):
        self.states[state] = (handle, time.time() + ttl_s)

    def pop_oauth_state(self, state):
        v = self.states.pop(state, None)
        if not v or v[1] < time.time():
            return None
        return v[0]

    def upsert_installation(self, handle, enc_token, expires_at, scopes):
        rec = self.installs.setdefault(handle, {"shop_id": f"shop_{len(self.installs)+1}", "handle": handle})
        rec.update(enc_token=enc_token, expires_at=expires_at, scopes=scopes, status="active")
        return rec["shop_id"]

    def get_installation(self, handle):
        return self.installs.get(handle)

    def mark_uninstalled(self, handle):
        if handle in self.installs:
            self.installs[handle].update(status="uninstalled", enc_token=None)

    def insert_webhook_event(self, webhook_id, row):
        with self._lock:  # emulates UNIQUE(webhook_id)
            if webhook_id in self.webhooks:
                return False
            self.webhooks[webhook_id] = row
            return True

    def append_trace(self, row):
        self.traces.append(row)

    def audit(self, event, detail):
        self.audits.append({"event": event, **detail})

    def save_output(self, key, value):
        self.outputs[key] = value

    def last_output(self, key):
        return self.outputs.get(key)

    def enqueue(self, job: dict[str, Any]) -> str:
        key = job.get("idempotency_key")
        if key:
            for j in self.jobs:
                if j.get("idempotency_key") == key:
                    return j["id"]
        job_id = f"job_{len(self.jobs)+1}"
        self.jobs.append({"id": job_id, **job})
        return job_id

    def get_installation_by_shop(self, shop_id):
        return next((i for i in self.installs.values() if i["shop_id"] == shop_id), None)

    def ping(self) -> bool:
        return True

    def erase_shop(self, shop_id: str) -> bool:
        handle = next((h for h, i in self.installs.items() if i["shop_id"] == shop_id), None)
        if not handle:
            return False
        del self.installs[handle]
        self.jobs = [j for j in self.jobs if j.get("shop_id") != shop_id]
        self.outputs = {k: v for k, v in self.outputs.items() if not k.startswith(shop_id + ":")}
        return True
