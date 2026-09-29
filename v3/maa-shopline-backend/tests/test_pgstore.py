"""PgStore, queue, drain, shared provider state and monitoring against real Postgres 16."""
import concurrent.futures as cf, hashlib, hmac, base64, json, time, pytest
psycopg = pytest.importorskip("psycopg")
from tests import pgcluster
from app.pgstore import PgStore, redact
from app.inference import registry as reg
from app.inference.gateway import Gateway, Policy
from app.inference.providers import Completion, ProviderError
from app.inference.validators import Contract
from app.jobs import drain
from app.alerts import Alerter
from app.shopline import webhooks

@pytest.fixture(scope="module")
def pg():
    if not pgcluster.available():
        pytest.skip("postgres not installed")
    conn, dsn, stop = pgcluster.start(55433)
    yield conn, dsn
    stop()

@pytest.fixture
def st(pg):
    conn, dsn = pg
    conn.execute("truncate jobs, errors, provider_state, oauth_states, output_cache, webhook_events, inference_attempts, audit_events, shops cascade")
    s = PgStore(dsn); yield s; s.close()

class Fake:
    def __init__(self, outs): self.outs, self.calls = list(outs), 0
    def complete(self, provider, model, messages, *, timeout_s, json_mode=False, max_tokens=1500):
        self.calls += 1
        o = self.outs.pop(0) if len(self.outs) > 1 else self.outs[0]
        if isinstance(o, Exception): raise o
        return Completion(o, "stop", 5, {})

A = reg.Model("nvidia", "prim", "fa", admitted=True); B = reg.Model("groq", "back", "fb", admitted=True)
def gateway(store, outs, on="queue"):
    role = reg.Role("r", (A, B), on, reg.Budget.STANDARD)
    return Gateway(Fake(outs), store, roles={"r": role}, tasks={"t": "r"}, approved={"nvidia", "groq"})

# ---------- OAuth + installs ----------
def test_oauth_state_single_use_and_ttl(st):
    st.save_oauth_state("s1", "shopa"); assert st.pop_oauth_state("s1") == "shopa"; assert st.pop_oauth_state("s1") is None
    st.save_oauth_state("s2", "shopa", ttl_s=-1); assert st.pop_oauth_state("s2") is None

def test_install_lookup_uninstall_destroys_token(st, pg):
    sid = st.upsert_installation("shopa", "ciphertext", "2030-01-01T00:00:00Z", ["read_orders", "read_products"])
    inst = st.get_installation("shopa")
    assert inst["shop_id"] == sid and inst["status"] == "active" and sorted(inst["scopes"]) == ["read_orders", "read_products"]
    assert st.get_installation_by_shop(sid)["handle"] == "shopa"
    assert st.get_installation_by_shop("not-a-uuid") is None
    st.mark_uninstalled("shopa")
    assert st.get_installation("shopa")["status"] == "uninstalled"
    assert pg[0].execute("select count(*) from shop_tokens").fetchone()[0] == 0
    assert st.upsert_installation("shopa", "ct2", "", []) == sid             # reinstall keeps shop identity

# ---------- webhooks: durable dedupe survives restart; stale rejected ----------
def _signed(body, secret="s3cret"):
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()

def test_webhook_dedupe_survives_restart(st, pg):
    st.upsert_installation("shopa", "ct", "", [])
    body = b'{"id": 42}'
    from app.shopline.signing import verify_webhook
    import app.shopline.signing as sg
    h = {"X-Shopline-Topic": "orders/create", "X-Shopline-Shop-Domain": "shopa.myshopline.com",
         "X-Shopline-Webhook-Id": "wh-1"}
    sig = sg._hmac_hex("s3cret", body) if hasattr(sg, "_hmac_hex") else _signed(body)
    h["X-Shopline-Hmac-Sha256"] = sig
    assert webhooks.receive(st, "s3cret", h, body).outcome == "accepted"
    fresh = PgStore(pg[1])                                            # new process / instance
    assert webhooks.receive(fresh, "s3cret", h, body).outcome == "duplicate"
    fresh.close()
    assert pg[0].execute("select count(*) from jobs where idempotency_key='wh:wh-1'").fetchone()[0] == 1
    old = {**h, "X-Shopline-Webhook-Id": "wh-2", "X-Test-Ts": str(int((time.time() - 3600) * 1000))}
    assert webhooks.receive(st, "s3cret", old, body, ts_header="X-Test-Ts").outcome == "rejected_stale"
    new = {**h, "X-Shopline-Webhook-Id": "wh-3", "X-Test-Ts": str(int(time.time() * 1000))}
    assert webhooks.receive(st, "s3cret", new, body, ts_header="X-Test-Ts").outcome == "accepted"

# ---------- queue ----------
def test_enqueue_idempotent(st):
    a = st.enqueue({"kind": "precompute", "idempotency_key": "k1"}); b = st.enqueue({"kind": "precompute", "idempotency_key": "k1"})
    assert a == b

def test_concurrent_claims_are_disjoint(st):
    for i in range(20): st.enqueue({"kind": "precompute"})
    with cf.ThreadPoolExecutor(4) as ex:
        got = list(ex.map(lambda w: st.claim_jobs(f"w{w}", 10), range(4)))
    ids = [j["id"] for g in got for j in g]
    assert len(ids) == 20 and len(set(ids)) == 20

def test_backoff_dead_terminal_and_lease_owner(st, pg):
    j = st.enqueue({"kind": "generate", "max_attempts": 2})
    c = st.claim_jobs("w1", 1)[0]
    assert not st.complete_job(j, "intruder")                         # only the lease owner may complete
    assert st.fail_job(j, "w1", "capacity") == "queued"
    ra = pg[0].execute("select run_after > now() + interval '50 seconds' from jobs where id=%s", (j,)).fetchone()[0]
    assert ra                                                          # 1-minute backoff applied
    pg[0].execute("update jobs set run_after=now() where id=%s", (j,))
    st.claim_jobs("w2", 1); assert st.fail_job(j, "w2", "capacity") == "dead"
    k = st.enqueue({"kind": "review"}); st.claim_jobs("w3", 5)
    assert st.fail_job(k, "w3", "needs_human_review", retryable=False) == "failed"
    assert st.replay_job(k) and pg[0].execute("select status, attempts from jobs where id=%s", (k,)).fetchone() == ("queued", 0)

def test_expired_lease_recovered_and_stuck_detected(st, pg):
    j = st.enqueue({"kind": "precompute"}); st.claim_jobs("ghost", 1)
    pg[0].execute("update jobs set locked_at=now()-interval '11 minutes', created_at=now()-interval '31 minutes' where id=%s", (j,))
    rec = st.recover_expired_leases()
    assert rec == [{"id": j, "status": "queued"}]
    assert [x["id"] for x in st.stuck_jobs()] == [j]

def test_job_status_is_tenant_scoped(st):
    a = st.upsert_installation("shopa", "c", "", []); b = st.upsert_installation("shopb", "c", "", [])
    j = st.enqueue({"kind": "precompute", "shop_id": a})
    assert st.get_job(j, a)["status"] == "queued"
    assert st.get_job(j, b) is None

# ---------- drain end to end ----------
def test_drain_processes_every_kind(st, pg):
    sid = st.upsert_installation("shopa", "c", "", [])
    ok = st.enqueue({"kind": "generate", "shop_id": sid, "task": "t", "data_class": "public", "context": {"q": 1}})
    rv = st.enqueue({"kind": "review", "shop_id": sid})
    sy = st.enqueue({"kind": "sync", "shop_id": sid, "topic": "orders/create"})
    pc = st.enqueue({"kind": "precompute", "shop_id": sid})
    res = drain(st, gateway(st, ["All good."]), budget_s=5)
    rows = dict(pg[0].execute("select id::text, status from jobs").fetchall())
    assert rows[ok] == "done" and rows[pc] == "done"
    assert rows[rv] == "failed" and rows[sy] == "failed"
    err = pg[0].execute("select last_error from jobs where id=%s", (sy,)).fetchone()[0]
    assert err == "capability_blocked:orders_read"
    assert st.last_output(f"{sid}:health_check:nightly:none")["value"]["overall"] is None   # unscored, never estimated
    assert res.done == 2 and res.failed == 2

def test_drain_retries_when_no_provider(st, pg):
    sid = st.upsert_installation("shopa", "c", "", [])
    j = st.enqueue({"kind": "generate", "shop_id": sid, "task": "t", "data_class": "public", "context": {}})
    drain(st, gateway(st, [ProviderError("server")]), budget_s=5)
    status, attempts = pg[0].execute("select status, attempts from jobs where id=%s", (j,)).fetchone()
    assert status == "queued" and attempts == 1                      # backed off, not re-enqueued as a new job
    assert pg[0].execute("select count(*) from jobs").fetchone()[0] == 1

def test_drain_is_safe_under_overlapping_triggers(st, pg):
    sid = st.upsert_installation("shopa", "c", "", [])
    for _ in range(10): st.enqueue({"kind": "precompute", "shop_id": sid})
    g = gateway(st, ["x"])
    with cf.ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda _: drain(st, g, budget_s=5), range(3)))    # pg_cron + GitHub + retry overlap
    assert pg[0].execute("select count(*) from jobs where status='done'").fetchone()[0] == 10

# ---------- confidential routing + shared breaker ----------
def test_confidential_job_never_reaches_unapproved_provider(st, pg):
    role = reg.Role("r", (reg.Model("openrouter", "some/model:free", "or", admitted=True),), "queue", reg.Budget.STANDARD)
    fake = Fake(["leak"])
    g = Gateway(fake, st, roles={"r": role}, tasks={"t": "r"}, approved=set())
    out = g.generate("t", Contract(), {}, Policy(reg.DataClass.MERCHANT_CONFIDENTIAL, "s"))
    assert out.state == "queued" and fake.calls == 0
    assert g.generate("t", Contract(), {}, Policy(reg.DataClass.PUBLIC, "s")).state == "live" and fake.calls == 1
    assert g.generate("t", Contract(), {}, Policy(reg.DataClass.SENSITIVE, "s")).state == "not_computed"

def test_breaker_state_is_shared_across_instances(st, pg):
    alerts = []
    g1 = gateway(st, [ProviderError("server")]); g1.alert = lambda k, t, r: alerts.append(k)
    for _ in range(3): g1.generate("t", Contract(), {"n": _}, Policy(reg.DataClass.PUBLIC, "s"))
    assert "breaker_open" in alerts
    fake2 = Fake(["fine"]); g2 = Gateway(fake2, st, roles=g1.roles, tasks=g1.tasks, approved=g1.approved)
    g2.generate("t", Contract(), {"n": 9}, Policy(reg.DataClass.PUBLIC, "s"))
    tr = pg[0].execute("select model from inference_attempts order by id desc limit 1").fetchone()[0]
    assert tr == "back"                                              # second instance skipped the open primary

# ---------- monitoring ----------
def test_alerts_recorded_deduped_and_redacted(st, pg):
    sent = []
    class H:
        def post(self, url, json): sent.append(json); return type("R", (), {"status_code": 200})()
    a = Alerter(st, "https://hooks.slack.com/services/x", "test", http=H())
    a("job_stuck", "precompute job queued for >30 min, key nvapi-ABCDEF123456789", "stuck:1")
    a("job_stuck", "again", "stuck:1")
    assert len(sent) == 1 and "nvapi-" not in sent[0]["text"] and "[REDACTED]" in sent[0]["text"]
    assert pg[0].execute("select count(*), bool_and(alerted) from errors").fetchone() == (1, True)
    assert redact("gsk_abcdefghijklmnop sk-or-1234567890abc") == "[REDACTED] [REDACTED]"

def test_ops_tables_closed_to_clients(st, pg):
    conn = pg[0]
    st.record_error("api", "x", "y"); st.save_provider_state("k", {}, {}); st.save_oauth_state("s", "h")
    conn.execute("set role authenticated")
    try:
        for t in ["errors", "provider_state", "oauth_states", "output_cache", "webhook_events", "inference_attempts"]:
            assert conn.execute(f"select count(*) from {t}").fetchone()[0] == 0, t
    finally:
        conn.execute("reset role")

def test_trace_accepts_all_data_classes(st):
    for dc in ["public", "internal", "merchant_confidential", "sensitive"]:
        st.append_trace({"role": "r", "data_class": dc, "provider": "p", "model": "m", "attempt": 1,
                         "latency_ms": 1, "validation": "pass"})


def test_terminal_jobs_drop_merchant_context(st, pg):
    sid = st.upsert_installation("shopa", "c", "", [])
    j = st.enqueue({"kind": "review", "shop_id": sid, "context": {"instruction": "Merchant question: secret plan"}})
    drain(st, gateway(st, ["x"]), budget_s=5)
    payload = pg[0].execute("select payload from jobs where id=%s", (j,)).fetchone()[0]
    assert "context" not in payload

def test_expired_oauth_states_purged(st, pg):
    st.save_oauth_state("old", "h", ttl_s=-5); st.save_oauth_state("new", "h")
    st.purge_expired()
    assert [r[0] for r in pg[0].execute("select state from oauth_states").fetchall()] == ["new"]

def test_erase_shop_removes_everything_keyed_to_it(st, pg):
    a = st.upsert_installation("shopa", "c", "", ["read_orders"]); b = st.upsert_installation("shopb", "c", "", [])
    st.enqueue({"kind": "precompute", "shop_id": a}); st.enqueue({"kind": "precompute", "shop_id": b})
    st.save_output(f"{a}:t:x:none", {"value": {"v": 1}, "model": "m", "generated_at": "2026-09-27T00:00:00+00:00"})
    st.append_trace({"shop_id": a, "role": "r", "data_class": "public", "provider": "p", "model": "m",
                     "attempt": 1, "latency_ms": 1, "validation": "pass"})
    st.audit("installed", {"shop_id": a})
    assert st.erase_shop(a)
    c = pg[0]
    assert c.execute("select count(*) from shops where id=%s", (a,)).fetchone()[0] == 0
    assert c.execute("select count(*) from jobs where shop_id=%s", (a,)).fetchone()[0] == 0
    assert c.execute("select count(*) from output_cache").fetchone()[0] == 0
    assert c.execute("select count(*) from inference_attempts where shop_id is not null").fetchone()[0] == 0
    assert c.execute("select count(*) from jobs where shop_id=%s", (b,)).fetchone()[0] == 1       # other tenant untouched
    assert st.get_installation("shopb")["status"] == "active"

def test_http_e2e_advisor_queue_drain_status(st, pg, settings):
    """API -> Postgres -> gateway -> queue -> authenticated drain -> status, over HTTP."""
    import hashlib
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app, issue_session
    s = Settings(**{**settings.__dict__, "drain_secret": "d" * 32, "admin_token": "t" * 32})
    sid = st.upsert_installation("shopa", "c", "", [])
    gw = gateway(st, [ProviderError("server")], on="queue")
    gw.tasks = {"advisor_answer": "r"}
    c = TestClient(create_app(s, store=st, gateway=gw))
    h = {"Authorization": "Bearer " + issue_session(hashlib.sha256(("session:" + s.token_encryption_key).encode()).hexdigest(), sid)}
    out = c.post("/api/advisor", json={"question": "Why did repeat orders drop?"}, headers=h).json()
    assert out["state"] == "queued" and out["job_id"]                  # every eligible provider failed -> queued, not an error
    assert c.get(f"/api/jobs/{out['job_id']}", headers=h).json() == {"state": "preparing"}
    r = c.post("/internal/jobs/drain", headers={"Authorization": "Bearer " + "d" * 32})
    assert r.status_code == 200 and r.json()["claimed"] == 1
    other = st.upsert_installation("shopb", "c", "", [])
    h2 = {"Authorization": "Bearer " + issue_session(hashlib.sha256(("session:" + s.token_encryption_key).encode()).hexdigest(), other)}
    assert c.get(f"/api/jobs/{out['job_id']}", headers=h2).status_code == 404   # no cross-tenant visibility
    summ = c.get("/admin/summary", headers={"Authorization": "Bearer " + "t" * 32}).json()
    assert summ["jobs"].get("queued") == 1 and "Why did" not in json.dumps(summ)  # admin shows counts, not content
    assert c.get("/health").json()["db"] == "ok"
