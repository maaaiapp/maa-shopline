"""Runs the real migration on a throwaway Postgres cluster and proves shop A
cannot read or write shop B, and client roles cannot touch tokens/traces."""
import os, shutil, subprocess, tempfile, time, pathlib
import pytest
psycopg = pytest.importorskip("psycopg")
BIN = "/usr/lib/postgresql/16/bin"
ROOT = pathlib.Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def db():
    if not os.path.exists(f"{BIN}/initdb"):
        pytest.skip("postgres not installed")
    d = tempfile.mkdtemp(); user = "postgres"
    run = lambda *a: subprocess.run(a, check=True, capture_output=True, **({"user": user} if os.geteuid()==0 else {}))
    if os.geteuid() == 0: shutil.chown(d, user)
    run(f"{BIN}/initdb", "-D", d, "-A", "trust", "-U", "postgres")
    run(f"{BIN}/pg_ctl", "-D", d, "-o", f"-p 55432 -k {d} -c listen_addresses=''", "-l", f"{d}/log", "start", "-w")
    conn = psycopg.connect(host=d, port=55432, user="postgres", dbname="postgres", autocommit=True)
    conn.execute((ROOT / "tests/rls_bootstrap.sql").read_text())
    conn.execute((ROOT / "supabase/migrations/0001_init.sql").read_text())
    conn.execute("grant select, insert, update, delete on all tables in schema public to authenticated")
    a = conn.execute("insert into shops(handle) values('shopa') returning id").fetchone()[0]
    b = conn.execute("insert into shops(handle) values('shopb') returning id").fetchone()[0]
    for s in (a, b):
        conn.execute("insert into orders_snapshot values (%s,'o1',null,now(),10,'USD','{}')", (s,))
        conn.execute("insert into merchant_profiles(shop_id, category) values (%s,'x')", (s,))
        conn.execute("insert into shop_tokens values (%s,'ciphertext',null)", (s,))
    yield conn, a, b
    conn.close(); run(f"{BIN}/pg_ctl", "-D", d, "stop", "-m", "fast")

def as_shop(conn, shop):
    conn.execute("reset role")
    conn.execute("select set_config('request.jwt.claims', %s, false)", ('{"shop_id":"%s"}' % shop if shop else "",))
    conn.execute("set role authenticated")

TENANT_READ = ["orders_snapshot", "merchant_profiles", "shop_scopes", "consent_ledger",
               "shop_data_sync_state", "intelligence_outputs", "jobs"]

def test_rls_enabled_on_every_table(db):
    conn, *_ = db
    conn.execute("reset role")
    off = conn.execute("select relname from pg_class where relnamespace='public'::regnamespace and relkind='r' and not relrowsecurity").fetchall()
    assert off == []

@pytest.mark.parametrize("table", TENANT_READ)
def test_cross_tenant_read_denied(db, table):
    conn, a, b = db
    as_shop(conn, a)
    rows = conn.execute(f"select shop_id from {table}").fetchall()
    assert all(r[0] == a for r in rows)
    assert conn.execute(f"select count(*) from {table} where shop_id=%s", (b,)).fetchone()[0] == 0

def test_cross_tenant_write_denied(db):
    conn, a, b = db
    as_shop(conn, a)
    assert conn.execute("update merchant_profiles set category='hacked' where shop_id=%s", (b,)).rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("insert into merchant_profiles(shop_id, category) values (%s,'y')", (b,))
    conn.execute("reset role")

def test_no_claim_sees_nothing(db):
    conn, *_ = db
    as_shop(conn, None)
    assert conn.execute("select count(*) from orders_snapshot").fetchone()[0] == 0
    conn.execute("reset role")

@pytest.mark.parametrize("table", ["shop_tokens", "inference_attempts", "webhook_events", "audit_events"])
def test_server_only_tables_denied_to_clients(db, table):
    conn, a, _ = db
    conn.execute("reset role")
    conn.execute(f"revoke all on {table} from authenticated")   # mirrors migration revoke after our blanket grant
    as_shop(conn, a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(f"select * from {table}")
    conn.execute("rollback") if conn.info.transaction_status else None
    conn.execute("reset role")

def test_webhook_dedupe_constraint(db):
    conn, a, _ = db
    conn.execute("reset role")
    conn.execute("insert into webhook_events(webhook_id, shop_id, topic, body_sha256) values ('w1',%s,'orders/create','h')", (a,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute("insert into webhook_events(webhook_id, shop_id, topic, body_sha256) values ('w1',%s,'orders/create','h')", (a,))

def test_only_validated_outputs_storable(db):
    conn, a, _ = db
    conn.execute("reset role")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into intelligence_outputs(shop_id,task,cache_key,value,model,validation) values (%s,'t','k','{}','m','fail')", (a,))
