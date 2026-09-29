# Model routing matrix

Source: plan role table (26 Sep). IDs live only in `app/inference/registry.py`.

| Role | Primary | Backups (admitted?) | On exhausted | Live probe |
|---|---|---|---|---|
| reasoning_interactive (hedged) | nvidia/nemotron-3-super-120b-a12b | mistral-nemotron (no), groq gpt-oss-120b (no), OpenRouter paid (unresolved ID) | last valid | BLOCKED |
| reasoning_batch | groq openai/gpt-oss-120b | nemotron-3-super (no), mistral-nemotron (no), OR (unresolved) | queue | BLOCKED |
| fast | mistral-nemotron | groq gpt-oss-20b (no), nemotron-super (no), OR | queue | BLOCKED |
| structured_json | groq gpt-oss-20b | nvidia gpt-oss-20b (no), groq 120b (no), nemotron-super (no) | queue | BLOCKED |
| cot_analysis | deepseek-v4-pro-0813 | nemotron-super, groq 120b, OR | queue | BLOCKED |
| arabic_copy | z-ai/glm-5.3 | mistral-nemotron, nemotron-super | queue (no free admitted backup) | BLOCKED |
| judge | mistral-nemotron | groq 20b, nvidia 20b | NOT COMPUTED; **shadow mode** (threshold 0.35 uncalibrated) | BLOCKED |
| safety | nemotron-3.5-content-safety | none | block (fail closed) — **no safety checker wired yet** | BLOCKED |

No backup is admitted: the golden-set run (~50 EN + ~50 AR per role, ≥90% win/tie) has not been done. Until then every role runs its primary only and then walks the never-error ladder — so today there is **no failover to a different model in production config**. The failover machinery is tested with admitted test models (tests/test_gateway.py).

**Why BLOCKED:** this session's network policy returned 403 on CONNECT to integrate.api.nvidia.com, api.groq.com and openrouter.ai, from both the cloud workspace and your computer. Run `scripts/probe_providers.py` where egress is allowed.

## Merchant-data approval (§7.3, §7.4, §8.1)
`APPROVED_FOR_MERCHANT_DATA = {}`. No provider's retention/training terms are recorded, so every merchant_confidential call queues. Add a provider only after recording its terms here:

| Provider | Retention | Trains on prompts | Region | Approved |
|---|---|---|---|---|
| NVIDIA API catalog | TBD | TBD | US | no (also dev/test licence only) |
| Groq | TBD | TBD | US | no |
| OpenRouter | per-route; `data_collection: deny` sent | per-route | varies | no (402 unfunded per plan) |
