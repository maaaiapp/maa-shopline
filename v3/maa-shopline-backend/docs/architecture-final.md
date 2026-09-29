# Architecture

Independent product. Code may be forked from MAA OS; no runtime, DB, bucket, key, queue or deployment is shared.

```
iOS client ──HTTPS──> FastAPI (app/main.py)
                        │ session (HMAC, shop_id bound at OAuth) — tenant never from client input
   ┌────────────────────┼──────────────────────────────┐
   │ shopline/oauth     │ shopline/webhooks             │ intelligence/health_check (deterministic)
   │ signing (HMAC hex) │ verify→auth→authorize→dedupe  │
   │                    │ →ack→enqueue                  │
   └──── policy/access_policy (PartnershipAccessPolicy: capability must be CONFIRMED) ───┘
                        │
               inference/gateway.generate(task, contract, context, policy)
                 filter: data class → admission → breaker → quota → judge independence
                 attempt: budgets, 1 JSON repair, deterministic validators, safety (fail closed)
                 ladder: live → last valid (dated) → queued (1/5/15 min) → NOT COMPUTED
                 trace row per attempt (destination log)
                        │
               providers: NVIDIA / Groq / OpenRouter (OpenAI-compatible)
                        │
               Store port → Supabase Postgres (SHOPLINE project only), RLS on every table
```

Isolation guards: `scripts/isolation_check.py` (CI), `config.assert_isolated` (startup, prod).
