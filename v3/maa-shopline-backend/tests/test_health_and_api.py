import os, subprocess, sys, time
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from app.config import IsolationError, Settings, assert_isolated
from app.intelligence.health_check import score
from app.main import create_app, issue_session, read_session

T = date(2026, 9, 27)

def orders(n_prev, n_cur, repeat_cur=0):
    rows = [{"customer_id": f"p{i}", "created": T - timedelta(days=100 + i % 70), "total": 100.0} for i in range(n_prev)]
    rows += [{"customer_id": f"c{i}", "created": T - timedelta(days=1 + i % 80), "total": 120.0} for i in range(n_cur)]
    rows += [{"customer_id": "c0", "created": T - timedelta(days=2), "total": 120.0}] * repeat_cur
    return rows

def test_missing_scope_is_unscored_never_estimated():
    r = score(None, False, T)
    assert r["overall"] is None and all(d["state"] == "unscored" for d in r["dimensions"])
    assert r["dimensions"][0]["needs"] == "orders_read"

def test_insufficient_history_path():
    r = score(orders(0, 10), True, T)
    assert r["overall"] is None and r["dimensions"][0]["state"] == "insufficient"

def test_scored_is_deterministic_and_evidenced():
    o = orders(40, 60, repeat_cur=3)
    a, b = score(o, True, T), score(o, True, T)
    assert a == b and a["overall"] is not None and a["coverage"] == "3 of 5"
    acq = a["dimensions"][0]
    assert acq["inputs"]["new_customers"] == 60 and acq["score"] == 75   # 60 vs 40 new customers = +50% → 50+25
    assert {d["key"]: d["state"] for d in a["dimensions"]}["market_position"] == "unscored"

def test_all_healthy_is_maintenance_not_invented_weakness():
    r = score(orders(40, 60, repeat_cur=3), True, T)
    if all(d["score"] >= 50 for d in r["dimensions"] if d["state"] == "scored"):
        assert r["maintenance"] and r["binding_constraint"] is None

def test_isolation_assertion(settings):
    assert_isolated(settings)  # test env: no raise
    bad = Settings(**{**settings.__dict__, "env": "prod", "supabase_url": "https://" + "z" * 20 + ".supabase.co"})
    with pytest.raises(IsolationError): assert_isolated(bad)
    with pytest.raises(IsolationError): assert_isolated(Settings(**{**settings.__dict__, "env": "prod", "supabase_ref": ""}))
    with pytest.raises(IsolationError): assert_isolated(Settings(**{**settings.__dict__, "env": "prod", "extra_endpoints": ["https://maa-os.example.com/rpc"]}))
    ok = Settings(**{**settings.__dict__, "env": "prod", "supabase_url": f"https://{'a'*20}.supabase.co",
                     "database_url": f"postgresql://postgres.{'a'*20}:pw@pooler.example:6543/postgres",
                     "drain_secret": "d" * 32, "admin_token": "t" * 32, "extra_endpoints": ["https://api.groq.com/x"]})
    assert_isolated(ok)
    with pytest.raises(IsolationError):   # production may not run on the in-memory store
        assert_isolated(Settings(**{**ok.__dict__, "database_url": ""}))
    with pytest.raises(IsolationError):   # alerts only to Slack/Discord
        assert_isolated(Settings(**{**ok.__dict__, "alert_webhook_url": "https://evil.example/hook"}))

def test_session_tamper_and_expiry():
    tok = issue_session("k", "shop_1")
    assert read_session("k", tok) == "shop_1"
    assert read_session("other", tok) is None
    assert read_session("k", tok[:-1] + ("0" if tok[-1] != "0" else "1")) is None
    assert read_session("k", issue_session("k", "shop_1", now=time.time() - 13 * 3600)) is None

def test_api_auth_required_and_tenant_from_session(settings):
    c = TestClient(create_app(settings))
    for m, p in [("get", "/api/health-check"), ("get", "/api/connection"), ("post", "/api/advisor")]:
        assert getattr(c, m)(p).status_code == 401
    r = c.get("/api/health-check", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401

def test_api_degraded_states_not_errors(settings):
    import hashlib
    from app.store import MemoryStore
    st = MemoryStore(); sid = st.upsert_installation("shop1", "ct", "", ["read_orders"])
    app = create_app(settings, store=st); c = TestClient(app)
    secret = hashlib.sha256(("session:" + settings.token_encryption_key).encode()).hexdigest()
    h = {"Authorization": "Bearer " + issue_session(secret, sid)}
    hc = c.get("/api/health-check", headers=h).json()
    assert hc["state"] == "degraded" and hc["result"]["overall"] is None
    adv = c.post("/api/advisor", json={"question": "Why is retention down?"}, headers=h).json()
    assert adv["state"] in {"queued", "last_valid", "not_computed", "live"} and "Traceback" not in str(adv)
    assert c.get("/auth/shopline/start", params={"handle": "evil.com/x"}, follow_redirects=False).status_code == 400
    loc = c.get("/auth/shopline/start", params={"handle": "shop1"}, follow_redirects=False).headers["location"]
    assert loc.startswith("https://shop1.myshopline.com/admin/oauth-web/")

def test_isolation_check_script(tmp_path):
    env = {**os.environ, "SHOPLINE_SUPABASE_REF": "a" * 20, "FORBIDDEN_IDENTIFIERS": "maa-main-prod"}
    (tmp_path / "ok.py").write_text(f"URL='https://{'a'*20}.supabase.co'")
    assert subprocess.run([sys.executable, "scripts/isolation_check.py", str(tmp_path)], env=env).returncode == 0
    (tmp_path / "bad.py").write_text(f"URL='https://{'b'*20}.supabase.co'  # maa-main-prod")
    assert subprocess.run([sys.executable, "scripts/isolation_check.py", str(tmp_path)], env=env, capture_output=True).returncode == 1


def test_uninstall_revokes_sessions(settings):
    import hashlib
    from app.store import MemoryStore
    st = MemoryStore(); sid = st.upsert_installation("shop1", "ct", "", [])
    c = TestClient(create_app(settings, store=st))
    secret = hashlib.sha256(("session:" + settings.token_encryption_key).encode()).hexdigest()
    h = {"Authorization": "Bearer " + issue_session(secret, sid)}
    assert c.get("/api/connection", headers=h).status_code == 200
    st.mark_uninstalled("shop1")
    r = c.get("/api/connection", headers=h)
    assert r.status_code == 401 and r.json()["detail"] == "session_revoked"

def test_internal_and_admin_endpoints_locked(settings):
    c = TestClient(create_app(settings))
    assert c.post("/internal/jobs/drain").status_code == 404          # disabled when no secret configured
    assert c.get("/admin/summary").status_code == 404
    s2 = Settings(**{**settings.__dict__, "drain_secret": "d" * 32, "admin_token": "t" * 32})
    c = TestClient(create_app(s2))
    for bad in ["", "Bearer wrong", "Bearer " + "t" * 32]:              # admin token must not open drain
        assert c.post("/internal/jobs/drain", headers={"Authorization": bad}).status_code == 401
    assert c.get("/admin/summary", headers={"Authorization": "Bearer " + "d" * 32}).status_code == 401
    assert c.get("/health").json() == {"status": "ok", "db": "ok"}


def _client_with_shop(settings):
    import hashlib
    from app.store import MemoryStore
    st = MemoryStore(); sid = st.upsert_installation("shop1", "ct", "", [])
    c = TestClient(create_app(settings, store=st))
    secret = hashlib.sha256(("session:" + settings.token_encryption_key).encode()).hexdigest()
    return st, sid, c, {"Authorization": "Bearer " + issue_session(secret, sid)}

def test_session_refresh_and_account_delete(settings):
    st, sid, c, h = _client_with_shop(settings)
    r = c.post("/api/session/refresh", headers=h)
    assert r.status_code == 200 and r.json()["session"]
    d = c.post("/api/account/delete", headers=h)
    assert d.json() == {"deleted": True, "next": "uninstall_in_shopline_admin"}
    assert st.get_installation("shop1") is None
    assert c.get("/api/connection", headers=h).status_code == 401          # deleted account = revoked session

def test_ios_start_marks_state_and_web_does_not(settings):
    from app.store import MemoryStore
    st = MemoryStore(); c = TestClient(create_app(settings, store=st), follow_redirects=False)
    ios = c.get("/auth/shopline/start", params={"handle": "shop1", "client": "ios"})
    web = c.get("/auth/shopline/start", params={"handle": "shop1"})
    assert ios.status_code == web.status_code == 302
    states = list(st.oauth_states.keys()) if hasattr(st, "oauth_states") else list(st.states.keys())
    assert sum(s.endswith("~ios") for s in states) == 1 and len(states) == 2
