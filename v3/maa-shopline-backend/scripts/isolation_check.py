#!/usr/bin/env python3
"""Fail CI if main-MAA-platform identifiers appear in the SHOPLINE repo.

Env:
  SHOPLINE_SUPABASE_REF   allowed Supabase project ref (required)
  FORBIDDEN_IDENTIFIERS   comma-separated main-platform refs/hosts/key prefixes
Usage: isolation_check.py [repo_root]   -> exit 1 on any finding
"""
import os, re, sys, pathlib

SKIP = {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build", ".next", "venv", ".venv"}
allowed = os.environ.get("SHOPLINE_SUPABASE_REF", "").strip()
forbidden = [f.strip() for f in os.environ.get("FORBIDDEN_IDENTIFIERS", "").split(",") if f.strip()]
if not allowed:
    sys.exit("SHOPLINE_SUPABASE_REF not set")
if not forbidden:
    print("WARNING: FORBIDDEN_IDENTIFIERS empty; only unknown-ref check active")

ref_re = re.compile(r"([a-z0-9]{20})\.supabase\.(?:co|in)")
findings = []
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
for p in root.rglob("*"):
    if not p.is_file() or SKIP & set(p.parts):
        continue
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        continue
    findings += [f"{p}: forbidden identifier '{f}'" for f in forbidden if f in text]
    findings += [f"{p}: unknown Supabase ref '{m}'" for m in ref_re.findall(text) if m != allowed]

if findings:
    print("\n".join(findings)); sys.exit(1)
print("isolation check passed")
