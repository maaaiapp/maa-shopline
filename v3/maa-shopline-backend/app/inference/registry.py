"""Model registry — the only place model IDs live.

Source: 'App Architecture & Resilient Inference Plan' (26 Sep 2026), role table.
`verified=False` means the ID has not passed a live probe on current keys
(scripts/probe_providers.py). `admitted=False` means the backup has not passed
backup admission (golden set, >=90% win/tie); non-admitted backups are skipped
for merchant-facing output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DataClass(str, Enum):
    PUBLIC = "public"                              # public or synthetic data only
    INTERNAL = "internal"                          # MAA-internal, no merchant data
    MERCHANT_CONFIDENTIAL = "merchant_confidential"  # agreement §8.1 Confidential Information
    SENSITIVE = "sensitive"                        # never sent to any model provider


class Budget(str, Enum):
    INTERACTIVE = "interactive"
    STANDARD = "standard"
    BATCH = "batch"


FIRST_TOKEN_S = {Budget.INTERACTIVE: 4, Budget.STANDARD: 20, Budget.BATCH: 60}
TOTAL_S = {Budget.INTERACTIVE: 8, Budget.STANDARD: 30, Budget.BATCH: 90}


@dataclass(frozen=True)
class Model:
    provider: str          # nvidia | groq | openrouter | gemini
    model_id: str
    family: str            # for judge independence
    verified: bool = False
    admitted: bool = False  # backups only; a role's primary (index 0) is always eligible


@dataclass(frozen=True)
class Role:
    name: str
    chain: tuple[Model, ...]
    on_exhausted: str      # last_valid | queue | not_computed | block
    budget: Budget
    output: str = "text"   # text | json
    hedge: bool = False


# Merchant-confidential approval (agreement §7.3, §7.4, §8.1). EMPTY until each
# provider's retention/training terms are recorded in docs/model-routing-matrix.md.
# While empty, merchant_confidential calls cannot run — this is the blocker #3
# in the plan, enforced in code rather than by convention.
APPROVED_FOR_MERCHANT_DATA: set[str] = set()


def M(p, mid, fam, **kw):
    return Model(p, mid, fam, **kw)


NEMO_SUPER = M("nvidia", "nvidia/nemotron-3-super-120b-a12b", "nemotron")
MISTRAL_NEMO = M("nvidia", "mistralai/mistral-nemotron", "mistral")
GROQ_120 = M("groq", "openai/gpt-oss-120b", "gpt-oss", verified=False)
GROQ_20 = M("groq", "openai/gpt-oss-20b", "gpt-oss", verified=False)
NV_OSS_20 = M("nvidia", "openai/gpt-oss-20b", "gpt-oss")
OR_PAID = M("openrouter", "VERIFY:openrouter-free", "openrouter")  # unfunded: free models only, PUBLIC only

ROLES: dict[str, Role] = {r.name: r for r in [
    Role("reasoning_interactive", (NEMO_SUPER, MISTRAL_NEMO, GROQ_120, OR_PAID), "last_valid", Budget.INTERACTIVE, hedge=True),
    Role("reasoning_batch", (M("groq", "openai/gpt-oss-120b", "gpt-oss"), NEMO_SUPER, MISTRAL_NEMO, OR_PAID), "queue", Budget.BATCH),
    Role("fast", (MISTRAL_NEMO, GROQ_20, NEMO_SUPER, OR_PAID), "queue", Budget.INTERACTIVE),
    Role("structured_json", (M("groq", "openai/gpt-oss-20b", "gpt-oss"), NV_OSS_20, GROQ_120, NEMO_SUPER), "queue", Budget.STANDARD, output="json"),
    Role("cot_analysis", (M("nvidia", "deepseek-ai/deepseek-v4-pro-0813", "deepseek"), NEMO_SUPER, GROQ_120, OR_PAID), "queue", Budget.BATCH),
    # Arabic customer copy: no admitted free backup -> queue rather than degrade.
    Role("arabic_copy", (M("nvidia", "z-ai/glm-5.3", "glm"), MISTRAL_NEMO, NEMO_SUPER), "queue", Budget.STANDARD),
    Role("judge", (MISTRAL_NEMO, GROQ_20, NV_OSS_20), "not_computed", Budget.STANDARD),
    Role("safety", (M("nvidia", "nvidia/nemotron-3.5-content-safety", "nemotron-safety"),), "block", Budget.INTERACTIVE),
]}

# Judge is in shadow mode until calibrated (plan blocker #4). Threshold 0.35 is uncalibrated.
JUDGE_ENFORCED = False
JUDGE_THRESHOLD = 0.35

# Role used per product task.
TASKS = {
    "advisor_answer": "reasoning_interactive",
    "home_briefing": "reasoning_interactive",
    "health_check_narrative": "reasoning_batch",
    "voc_themes": "reasoning_batch",
    "strategy": "reasoning_batch",
    "campaign_plan": "structured_json",
    "swot": "cot_analysis",
    "arabic_briefing": "arabic_copy",
}


def eligible(m: Model, data_class: DataClass, approved: set[str]) -> bool:
    """Provider eligibility per data class. The router may never widen this.

    - SENSITIVE: no provider.
    - OpenRouter: unfunded, so only ':free' models, and free providers may log
      prompts -> PUBLIC data only, regardless of the approved list.
    - INTERNAL / MERCHANT_CONFIDENTIAL: only providers whose data terms are recorded
      and approved (APPROVED_FOR_MERCHANT_DATA).
    - PUBLIC: any provider.
    """
    if data_class is DataClass.SENSITIVE:
        return False
    if m.provider == "openrouter":
        return m.model_id.endswith(":free") and data_class is DataClass.PUBLIC
    if data_class in (DataClass.INTERNAL, DataClass.MERCHANT_CONFIDENTIAL):
        return m.provider in approved
    return True
