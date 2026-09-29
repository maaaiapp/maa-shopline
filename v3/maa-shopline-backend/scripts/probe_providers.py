#!/usr/bin/env python3
"""Live entitlement probe for every model in the registry (plan blocker #5).
Run where egress to the provider hosts is allowed:  set -a; . ./.env; python scripts/probe_providers.py
Prints provider, model, HTTP status, latency. Never prints keys or completions."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
from app.inference.providers import BASE
from app.inference.registry import ROLES
KEYS = {"nvidia": os.environ.get("NVIDIA_API_KEY"), "groq": os.environ.get("GROQ_API_KEY"), "openrouter": os.environ.get("OPENROUTER_API_KEY")}
seen = set()
with httpx.Client(timeout=30) as c:
    if KEYS["openrouter"]:
        r = c.get(f"{BASE['openrouter']}/key", headers={"Authorization": f"Bearer {KEYS['openrouter']}"})
        print(f"openrouter key status {r.status_code} credits/limit: {r.json().get('data', {}).get('limit') if r.status_code == 200 else '-'}")
    for role in ROLES.values():
        for m in role.chain:
            k = (m.provider, m.model_id)
            if k in seen or m.model_id.startswith("VERIFY:") or m.provider not in BASE: continue
            seen.add(k); t = time.monotonic()
            try:
                r = c.post(f"{BASE[m.provider]}/chat/completions", headers={"Authorization": f"Bearer {KEYS[m.provider]}"},
                           json={"model": m.model_id, "messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 5})
                s = r.status_code
            except httpx.HTTPError as e:
                s = type(e).__name__
            print(f"{role.name:24} {m.provider:10} {m.model_id:45} {s} {int((time.monotonic()-t)*1000)}ms")
