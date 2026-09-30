"""PostgreSQL/Supabase implementation of the Store port, plus the durable job
queue, error log and shared provider state.

Connects with the backend DATABASE_URL (table owner / service role), which
bypasses RLS by design; RLS protects the tables from anon/authenticated
clients. Every method takes shop scoping from its arguments, never from a client.

Works through the Supabase transaction pooler (prepare_threshold=None).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Retry delays for jobs: plan says 1, 5, 15 minutes, then widen.
BACKOFF_S = (60, 300, 900, 1800, 3600)
LEASE_MIN = 10          # a running job whose worker vanished is reclaimed after this
STUCK_MIN = 30          # plan: jobs older than 30 min are flagged to /admin, not the merchant

_SECRETISH = re.compile(r"(nvapi-|gsk_|sk-or-|sk-|eyJ)[A-Za-z0-9._\-]{8,}")


def redact(text: str, limit: int = 500) -> str:
    return _SECRETISH.sub("[REDACTED]", str(text))[:limit]


def _uuid_or_none(v: Any) -> str | None:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError):
        return None


class PgStore:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 5):
        clean_dsn = dsn
        if clean_dsn.startswith("postgres://"):
            clean_dsn = clean_dsn.replace("postgres://", "postgresql://", 1)

        self.pool = ConnectionPool(
            clean_dsn,
            min_size=min_size,
            max_size=max_size,
            open=True,
            kwargs={
                "autocommit": True,
                "prepare_threshold": None,
                "row_factory": dict_row,
            },
        )

    def close(self):
        self.pool.close()

    def _q(self, sql: str, args: tuple = (), one=False, many=False):
        with self.pool.connection() as c:
            cur = c.execute(sql, args)
            if one:
                return cur.fetchone()
            if many:
                return cur.fetchall()
            return cur.rowcount

    def ping(self) -> bool:
        try:
            return self._q("select 1 as ok", one=True)["ok"] == 1
        except Exception:
            return False

    # ---------- OAuth ----------
    def save_oauth_state(self, state, handle, ttl_s=600):
        self._q("insert into oauth_states(state, handle, expires_at) values (%s,%s, now() + make_interval(secs => %s))",
                (state, handle, ttl_s))

    def pop_oauth_state(self, state):
        row = self._q("delete from oauth_states where state=%s returning handle, expires_at > now() as live",
                      (state,), one=True)                      # single use: delete-returning is atomic
        return row["handle"] if row and row["live"] else None

    # ---------- installations ----------
    def upsert_installation(self, handle, enc_token, expires_at, scopes):
        with self.pool.connection() as c, c.transaction():
            shop = c.execute("""insert into shops(handle, status) values (%s,'active')
                                on conflict (handle) do update set status='active', uninstalled_at=null
                                returning id""", (handle,)).fetchone()["id"]
            exp = None
            try:
                exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) if expires_at else None
            except ValueError:
                exp = None
            c.execute("""insert into shop_tokens(shop_id, enc_access_token, expires_at) values (%s,%s,%s)
                         on conflict (shop_id) do update set enc_access_token=excluded.enc_access_token,
                         expires_at=excluded.expires_at, updated_at=now()""", (shop, enc_token, exp))
            c.execute("delete from shop_scopes where shop_id=%s", (shop,))
            for sc in scopes:
                c.execute("insert into shop_scopes(shop_id, scope) values (%s,%s) on conflict do nothing", (shop, sc))
        return str(shop)

    def _inst(self, where: str, arg) -> dict | None:
        row = self._q(f"""select s.id::text as shop_id, s.handle, s.status, t.enc_access_token as enc_token,
                              t.expires_at, coalesce(array_agg(sc.scope) filter (where sc.scope is not null), '{{}}') as scopes
                          from shops s left join shop_tokens t on t.shop_id=s.id
                          left join shop_scopes sc on sc.shop_id=s.id
                          where {where} group by s.id, t.enc_access_token, t.expires_at""", (arg,), one=True)
        return dict(row) if row else None

    def get_installation(self, handle):
        return self._inst("s.handle = %s", handle)

    def get_installation_by_shop(self, shop_id):
        sid = _uuid_or_none(shop_id)
        return self._inst("s.id = %s", sid) if sid else None

    def mark_uninstalled(self, handle):
        with self.pool.connection() as c, c.transaction():
            row = c.execute("update shops set status='uninstalled', uninstalled_at=now() where handle=%s returning id",
                            (handle,)).fetchone()
            if row:
                c.execute("delete from shop_tokens where shop_id=%s", (row["id"],))   # token destroyed on uninstall

    # ---------- webhooks ----------
    def insert_webhook_event(self, webhook_id, row):
        n = self._q("""insert into webhook_events(webhook_id, shop_id, topic, body_sha256, status, sent_at)
                       values (%s,%s,%s,%s,%s,%s) on conflict (webhook_id) do nothing""",
                    (webhook_id, _uuid_or_none(row.get("shop_id")), row["topic"], row["body_sha256"],
                     row.get("status", "received"), row.get("sent_at")))
        return n == 1

    # ---------- traces / audit / errors ----------
    def append_trace(self, r):
        self._q("""insert into inference_attempts(shop_id, role, data_class, provider, model, attempt, trigger,
                   latency_ms, tokens, validation) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (_uuid_or_none(r.get("shop_id")), r["role"], r["data_class"], r["provider"], r["model"],
                 r["attempt"], r.get("trigger"), r["latency_ms"], r.get("tokens", 0), r["validation"]))

    def audit(self, event, detail):
        self._q("insert into audit_events(shop_id, event, detail) values (%s,%s,%s)",
                (_uuid_or_none(detail.get("shop_id")), event, json.dumps(detail, default=str)))

    def record_error(self, source: str, kind: str, message: str, shop_id=None, context: dict | None = None) -> int:
        row = self._q("""insert into errors(source, kind, message, shop_id, context) values (%s,%s,%s,%s,%s)
                         returning id""", (source, kind[:120], redact(message), _uuid_or_none(shop_id),
                                           json.dumps(context or {}, default=str)), one=True)
        return row["id"]

    def mark_alerted(self, error_id: int):
        self._q("update errors set alerted=true where id=%s", (error_id,))

    def error_exists(self, kind: str, ref: str) -> bool:
        return bool(self._q("select 1 from errors where kind=%s and context->>'ref'=%s limit 1", (kind, ref), one=True))

    # ---------- output cache ----------
    def save_output(self, key, value):
        self._q("""insert into output_cache(cache_key, shop_id, value, model, generated_at) values (%s,%s,%s,%s,%s)
                   on conflict (cache_key) do update set value=excluded.value, model=excluded.model,
                   generated_at=excluded.generated_at""",
                (key, _uuid_or_none(key.split(":", 1)[0]), json.dumps(value["value"], default=str),
                 value["model"], value["generated_at"]))

    def last_output(self, key):
        row = self._q("select value, model, generated_at from output_cache where cache_key=%s", (key,), one=True)
        if not row:
            return None
        return {"value": row["value"], "model": row["model"], "generated_at": row["generated_at"].isoformat()}

    # ---------- job queue ----------
    def enqueue(self, job: dict[str, Any]) -> str:
        job = dict(job)
        kind = job.pop("kind")
        shop = _uuid_or_none(job.pop("shop_id", None))
        key = job.pop("idempotency_key", None)
        max_attempts = int(job.pop("max_attempts", 5))
        delay = int(job.pop("delay_s", 0))
        row = self._q("""insert into jobs(shop_id, kind, payload, idempotency_key, max_attempts, run_after)
                         values (%s,%s,%s,%s,%s, now() + make_interval(secs => %s))
                         on conflict (idempotency_key) where idempotency_key is not null
                         do update set updated_at = jobs.updated_at      -- no-op, returns existing id
                         returning id::text""",
                      (shop, kind, json.dumps(job, default=str), key, max_attempts, delay), one=True)
        return row["id"]

    def claim_jobs(self, worker: str, limit: int) -> list[dict]:
        rows = self._q("""with c as (select id from jobs where status='queued' and run_after <= now()
                                     order by run_after limit %s for update skip locked)
                          update jobs j set status='running', attempts=j.attempts+1, locked_at=now(),
                                 locked_by=%s, started_at=coalesce(j.started_at, now()), updated_at=now()
                          from c where j.id=c.id
                          returning j.id::text, j.shop_id::text, j.kind, j.payload, j.attempts, j.max_attempts""",
                       (limit, worker), many=True)
        return [dict(r) for r in rows]

    def complete_job(self, job_id: str, worker: str) -> bool:
        return self._q("""update jobs set status='done', finished_at=now(), locked_at=null, locked_by=null,
                          last_error=null, updated_at=now(), payload = payload - 'context'
                          where id=%s and locked_by=%s and status='running'""",
                       (job_id, worker)) == 1

    def fail_job(self, job_id: str, worker: str, error: str, retryable: bool = True) -> str:
        row = self._q("select attempts, max_attempts from jobs where id=%s and locked_by=%s and status='running'",
                      (job_id, worker), one=True)
        if not row:
            return "lost_lease"
        if not retryable:
            status, delay = "failed", 0
        elif row["attempts"] >= row["max_attempts"]:
            status, delay = "dead", 0
        else:
            status, delay = "queued", BACKOFF_S[min(row["attempts"] - 1, len(BACKOFF_S) - 1)]
        self._q("""update jobs set status=%s, last_error=%s, locked_at=null, locked_by=null, updated_at=now(),
                   run_after = now() + make_interval(secs => %s),
                   finished_at = case when %s in ('failed','dead') then now() else null end,
                   payload = case when %s in ('failed','dead') then payload - 'context' else payload end
                   where id=%s""", (status, redact(error, 300), delay, status, status, job_id))
        return status

    def recover_expired_leases(self) -> list[dict]:
        rows = self._q(f"""update jobs set status = case when attempts >= max_attempts then 'dead' else 'queued' end,
                               last_error='lease_expired', locked_at=null, locked_by=null, updated_at=now(),
                               finished_at = case when attempts >= max_attempts then now() else null end
                           where status='running' and locked_at < now() - interval '{LEASE_MIN} minutes'
                           returning id::text, status""", many=True)
        return [dict(r) for r in rows]

    def purge_expired(self) -> dict:
        """Housekeeping run by every drain. Only purges data whose purpose has ended."""
        return {"oauth_states": self._q("delete from oauth_states where expires_at < now()")}

    def erase_shop(self, shop_id: str) -> bool:
        """Hard-delete a shop and everything keyed to it (FK cascades). Audit keeps only the event."""
        sid = _uuid_or_none(shop_id)
        if not sid:
            return False
        with self.pool.connection() as c, c.transaction():
            n = c.execute("delete from shops where id=%s", (sid,)).rowcount
            c.execute("delete from jobs where shop_id=%s", (sid,))
            c.execute("delete from output_cache where cache_key like %s", (sid + ":%",))
            c.execute("update inference_attempts set shop_id=null where shop_id=%s", (sid,))
            c.execute("update errors set shop_id=null where shop_id=%s", (sid,))
            c.execute("delete from audit_events where shop_id=%s", (sid,))
            c.execute("insert into audit_events(event, detail) values ('shop_erased', '{}')")
        return n == 1

    def stuck_jobs(self) -> list[dict]:
        rows = self._q(f"""select id::text, kind, status, attempts, created_at from jobs
                           where status in ('queued','running') and created_at < now() - interval '{STUCK_MIN} minutes'
                           order by created_at limit 50""", many=True)
        return [dict(r) for r in rows]

    def replay_job(self, job_id: str) -> bool:
        return self._q("""update jobs set status='queued', attempts=0, run_after=now(), last_error=null,
                          finished_at=null, updated_at=now() where id=%s and status in ('failed','dead')""",
                       (job_id,)) == 1

    def get_job(self, job_id: str, shop_id: str) -> dict | None:
        sid, jid = _uuid_or_none(shop_id), _uuid_or_none(job_id)
        if not sid or not jid:
            return None
        row = self._q("select id::text, kind, status, attempts, run_after, finished_at from jobs where id=%s and shop_id=%s",
                      (jid, sid), one=True)
        return dict(row) if row else None

    # ---------- provider state (shared breakers/quotas) ----------
    def load_provider_states(self, keys: list[str]) -> dict[str, dict]:
        rows = self._q("""select key, breaker, case when bucket_day = current_date then bucket else '{}'::jsonb end as bucket
                          from provider_state where key = any(%s)""", (keys,), many=True)
        return {r["key"]: {"breaker": r["breaker"], "bucket": r["bucket"]} for r in rows}

    def save_provider_state(self, key: str, breaker: dict, bucket: dict):
        self._q("""insert into provider_state(key, breaker, bucket, bucket_day) values (%s,%s,%s,current_date)
                   on conflict (key) do update set breaker=excluded.breaker, bucket=excluded.bucket,
                   bucket_day=current_date, updated_at=now()""", (key, json.dumps(breaker), json.dumps(bucket)))

    # ---------- admin ----------
    def admin_summary(self) -> dict:
        jobs = {r["status"]: r["n"] for r in self._q("select status, count(*) n from jobs group by status", many=True)}
        errs = self._q("""select source, kind, created_at from errors where created_at > now() - interval '24 hours'
                          order by created_at desc limit 50""", many=True)
        prov = self._q("select key, breaker->>'open_since' is not null as open, bucket, updated_at from provider_state",
                       many=True)
        return {"jobs": jobs, "stuck": len(self.stuck_jobs()),
                "errors_24h": [{"source": e["source"], "kind": e["kind"], "at": e["created_at"].isoformat()} for e in errs],
                "providers": [{"key": p["key"], "breaker_open": p["open"],
                               "used": (p["bucket"] or {}).get("used"), "limit": (p["bucket"] or {}).get("daily_limit")}
                              for p in prov]}