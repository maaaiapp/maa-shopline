#!/usr/bin/env python3
"""Fail if credentials appear in tracked files, or anywhere in git history (--history)."""
import pathlib, re, subprocess, sys
PATTERNS = {
    "nvidia": r"nvapi-[A-Za-z0-9_-]{20,}",
    "groq": r"gsk_[A-Za-z0-9]{20,}",
    "openrouter": r"sk-or-v1-[a-f0-9]{32,}",
    "google_api_key": r"AIza[0-9A-Za-z_\-]{35}",
    "supabase_jwt": r"eyJhbGciOiJ[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{20,}",
    "supabase_secret": r"sb_secret_[A-Za-z0-9_\-]{20,}",
    "pg_url_with_password": r"postgres(?:ql)?://[^:\s/]+:[^@\s{<$]{6,}@",
    "slack_webhook": r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{20,}",
    "discord_webhook": r"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]{40,}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{36,}",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "hex40_secret": r"(?i)(app[_ ]?secret|app[_ ]?key)\W{0,4}[0-9a-f]{40}",
}
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
ALLOW = {"scripts/secret_scan.py"}            # this file contains the patterns themselves


def scan_text(label, text):
    return [f"{label}: {n}" for n, rx in PATTERNS.items() if re.search(rx, text)]


def main(argv):
    history = "--history" in argv
    args = [a for a in argv if a != "--history"]
    root = pathlib.Path(args[0] if args else ".").resolve()
    hits = []
    if history:
        log = subprocess.run(["git", "-C", str(root), "log", "-p", "--all", "--no-color"],
                             capture_output=True, text=True, errors="ignore")
        if log.returncode != 0:
            print("not a git repository; history scan skipped"); return 0
        chunks = re.split(r"^diff --git a/(\S+)", log.stdout, flags=re.M)
        for i in range(1, len(chunks), 2):
            if chunks[i] not in ALLOW:
                hits += scan_text(f"history:{chunks[i]}", chunks[i + 1])
    else:
        for p in root.rglob("*"):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and not SKIP & set(p.parts) and rel not in ALLOW:
                hits += scan_text(rel, p.read_text(errors="ignore"))
    hits = sorted(set(hits))
    print("\n".join(hits) or ("history" if history else "tree") + " secret scan passed")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
