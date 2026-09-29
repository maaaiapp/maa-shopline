"""Deterministic output validators. They outrank any LLM judge.

Each returns None when valid or a short rejection reason (never model text).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")
COT_LEAK = re.compile(r"(<think>|</think>|\bchain[- ]of[- ]thought\b|^\s*(reasoning|thought)\s*:|let me think)",
                      re.I | re.M)
NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?")


@dataclass
class Contract:
    """What a valid answer must satisfy, independent of which model produced it."""
    output: str = "text"                       # text | json
    language: str = "en"                       # en | ar
    required_keys: tuple[str, ...] = ()
    enums: dict[str, set] = field(default_factory=dict)
    # Numbers the answer may cite (from deterministic computation / SHOPLINE data).
    # Any other number in customer-facing text = invented fact -> reject.
    allowed_numbers: set[str] | None = None
    min_chars: int = 1
    extra: list[Callable[[Any], str | None]] = field(default_factory=list)


def _norm_num(n: str) -> str:
    return n.replace(",", "").rstrip("%").lstrip("+")


def check(text: str, finish_reason: str, c: Contract) -> tuple[Any, str | None]:
    if finish_reason == "length":
        return None, "truncated"
    if not text or len(text.strip()) < c.min_chars:
        return None, "empty"
    if COT_LEAK.search(text):
        return None, "cot_leak"
    parsed: Any = text
    if c.output == "json":
        try:
            parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
        except ValueError:
            return None, "invalid_json"
        if not isinstance(parsed, dict):
            return None, "invalid_json"
        missing = [k for k in c.required_keys if k not in parsed]
        if missing:
            return None, "missing_fields"
        for k, allowed in c.enums.items():
            if k in parsed and parsed[k] not in allowed:
                return None, "bad_enum"
        prose = json.dumps(parsed, ensure_ascii=False)
    else:
        prose = text
    letters_ar, letters_lat = len(ARABIC.findall(prose)), len(LATIN.findall(prose))
    if c.language == "ar" and letters_ar < max(10, letters_lat):
        return None, "wrong_language"
    if c.language == "en" and letters_ar > letters_lat:
        return None, "wrong_language"
    if c.allowed_numbers is not None:
        allowed = {_norm_num(n) for n in c.allowed_numbers}
        for n in NUMBER.findall(prose):
            v = _norm_num(n)
            if v not in allowed and not re.fullmatch(r"[0-9]", v):  # single digits (list numbering) ok
                return None, "unsupported_number"
    for fn in c.extra:
        reason = fn(parsed)
        if reason:
            return None, reason
    return parsed, None
