"""Job worker invoked by POST /internal/jobs/drain.

Triggered every minute by Supabase pg_cron -> pg_net and, as a backup, by a
GitHub Actions schedule. Duplicate or overlapping triggers are safe: jobs are
claimed with FOR UPDATE SKIP LOCKED, completion is checked against the lease
owner, and every enqueue path uses an idempotency key.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import date

from app.inference import registry as reg
from app.inference.gateway import Gateway, Policy
from app.inference.validators import Contract
from app.intelligence.health_check import score
from app.policy.access_policy import CapabilityBlocked, require


class Retry(Exception):
    """Transient: back off and try again."""


class Terminal(Exception):
    """Will not succeed by retrying (e.g. capability not granted, needs human review)."""


@dataclass
class DrainResult:
    claimed: int = 0
    done: int = 0
    retried: int = 0
    failed: int = 0
    dead: int = 0
    recovered: int = 0
    stuck_alerts: int = 0


def handle(job: dict, store, gw: Gateway) -> None:
    kind, p = job["kind"], job["payload"] or {}
    if kind == "sync":
        try:
            require("orders_read", allow_public_doc=False)      # TD-01: surface not yet confirmed
        except CapabilityBlocked:
            raise Terminal("capability_blocked:orders_read")
        raise Terminal("sync_handler_pending_TD01")               # never reached until TD-01 unblocks
    if kind in ("generate", "regenerate"):
        out = gw.generate(p["task"], Contract(language=p.get("language", "en")), p.get("context", {}),
                          Policy(reg.DataClass(p.get("data_class", "merchant_confidential")), job["shop_id"] or "",
                                 safety_required=bool(p.get("safety_required")), allow_hedge=False, from_job=True))
        if out.state in ("live",):
            return
        if out.state == "not_computed":
            raise Terminal(f"not_computed:{out.reason}")
        raise Retry(out.reason or "capacity")
    if kind == "review":
        raise Terminal("needs_human_review:safety")
    if kind == "precompute":
        # Health Check is deterministic; with orders_read unconfirmed it is computed as unscored, never estimated.
        result = score(None, customers_scope=False, today=date.today())
        store.save_output(f"{job['shop_id']}:health_check:nightly:none",
                          {"value": result, "model": "deterministic", "generated_at": _now()})
        return
    raise Terminal(f"unknown_kind:{kind}")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def drain(store, gw: Gateway, alert=None, limit: int = 10, budget_s: float = 45.0) -> DrainResult:
    res = DrainResult()
    worker = f"w-{uuid.uuid4().hex[:12]}"
    res.recovered = len(store.recover_expired_leases())
    store.purge_expired()
    t0 = time.monotonic()
    while time.monotonic() - t0 < budget_s:
        batch = store.claim_jobs(worker, limit)
        if not batch:
            break
        res.claimed += len(batch)
        for job in batch:
            try:
                handle(job, store, gw)
                if store.complete_job(job["id"], worker):
                    res.done += 1
            except Terminal as e:
                store.fail_job(job["id"], worker, str(e), retryable=False)
                res.failed += 1
            except Retry as e:
                st = store.fail_job(job["id"], worker, str(e), retryable=True)
                res.dead += st == "dead"
                res.retried += st == "queued"
            except Exception as e:                                 # unexpected: retry, record, alert
                st = store.fail_job(job["id"], worker, f"{type(e).__name__}", retryable=True)
                res.dead += st == "dead"
                res.retried += st == "queued"
                if alert:
                    alert("job_exception", f"{job['kind']} raised {type(e).__name__}", f"job:{job['id']}:{job['attempts']}",
                          source="job", shop_id=job.get("shop_id"))
    if alert:
        for j in store.stuck_jobs():
            alert("job_stuck", f"{j['kind']} job {j['status']} for >30 min", f"stuck:{j['id']}", source="scheduler")
            res.stuck_alerts += 1
    return res
