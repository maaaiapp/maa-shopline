"""Throwaway Postgres 16 cluster with the Supabase shims and ALL migrations applied."""
import os, shutil, subprocess, tempfile, pathlib
BIN = "/usr/lib/postgresql/16/bin"
ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS = ["0001_init.sql", "0002_ops.sql"]   # 0003 needs pg_cron/pg_net + Vault (Supabase only)


def available() -> bool:
    return os.path.exists(f"{BIN}/initdb")


def start(port: int):
    import psycopg
    d = tempfile.mkdtemp(); user = "postgres"
    kw = {"user": user} if os.geteuid() == 0 else {}
    run = lambda *a: subprocess.run(a, check=True, capture_output=True, **kw)
    if os.geteuid() == 0: shutil.chown(d, user)
    run(f"{BIN}/initdb", "-D", d, "-A", "trust", "-U", "postgres")
    run(f"{BIN}/pg_ctl", "-D", d, "-o", f"-p {port} -k {d} -c listen_addresses=''", "-l", f"{d}/log", "start", "-w")
    conn = psycopg.connect(host=d, port=port, user="postgres", dbname="postgres", autocommit=True)
    conn.execute((ROOT / "tests/rls_bootstrap.sql").read_text())
    for m in MIGRATIONS:
        conn.execute((ROOT / "supabase/migrations" / m).read_text())
    conn.execute("grant select, insert, update, delete on all tables in schema public to authenticated")
    dsn = f"host={d} port={port} user=postgres dbname=postgres"
    stop = lambda: (conn.close(), run(f"{BIN}/pg_ctl", "-D", d, "stop", "-m", "fast"))
    return conn, dsn, stop
