"""Circuit breakers and quota buckets (plan: 'Circuit breakers', 'Quota budgeting')."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Breaker:
    consecutive_limit: int = 3
    window: int = 50
    fail_ratio: float = 0.40
    probe_interval_s: float = 60.0
    close_after: int = 2
    _recent: deque = field(default_factory=lambda: deque(maxlen=50))
    _consecutive: int = 0
    _open_since: float | None = None
    _last_probe: float = 0.0
    _probe_successes: int = 0

    def allow(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        if self._open_since is None:
            return True
        if now - self._last_probe >= self.probe_interval_s:
            self._last_probe = now
            return True  # half-open probe
        return False

    def to_dict(self) -> dict:
        return {"recent": list(self._recent), "consecutive": self._consecutive, "open_since": self._open_since,
                "last_probe": self._last_probe, "probe_successes": self._probe_successes}

    @classmethod
    def from_dict(cls, d: dict) -> "Breaker":
        b = cls()
        b._recent.extend(bool(x) for x in d.get("recent", [])[-b.window:])
        b._consecutive = int(d.get("consecutive", 0))
        b._open_since = d.get("open_since")
        b._last_probe = float(d.get("last_probe", 0.0))
        b._probe_successes = int(d.get("probe_successes", 0))
        return b

    @property
    def is_open(self) -> bool:
        return self._open_since is not None

    def record(self, ok: bool, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self._recent.append(ok)
        if self._open_since is not None:
            if ok:
                self._probe_successes += 1
                if self._probe_successes >= self.close_after:
                    self._open_since, self._probe_successes, self._consecutive = None, 0, 0
            else:
                self._probe_successes = 0
            return
        self._consecutive = 0 if ok else self._consecutive + 1
        fails = self._recent.count(False)
        if self._consecutive >= self.consecutive_limit or (
                len(self._recent) >= 10 and fails / len(self._recent) > self.fail_ratio):
            self._open_since, self._last_probe = now, now


@dataclass
class Bucket:
    """Daily request bucket; batch stops drawing at the interactive reserve."""
    daily_limit: int
    reserve_ratio: float = 0.30
    used: int = 0

    def update_from_headers(self, headers: dict[str, str]) -> None:
        h = {k.lower(): v for k, v in headers.items()}
        rem = h.get("x-ratelimit-remaining-requests") or h.get("x-ratelimit-remaining")
        lim = h.get("x-ratelimit-limit-requests") or h.get("x-ratelimit-limit")
        if rem and rem.isdigit() and lim and lim.isdigit():
            self.daily_limit, self.used = int(lim), int(lim) - int(rem)

    def can_spend(self, interactive: bool) -> bool:
        remaining = self.daily_limit - self.used
        return remaining > 0 if interactive else remaining > self.daily_limit * self.reserve_ratio

    def to_dict(self) -> dict:
        return {"daily_limit": self.daily_limit, "used": self.used}

    @classmethod
    def from_dict(cls, d: dict, default_limit: int) -> "Bucket":
        return cls(int(d.get("daily_limit", default_limit)), used=int(d.get("used", 0)))

    @property
    def below_reserve(self) -> bool:
        return self.daily_limit - self.used <= self.daily_limit * self.reserve_ratio

    def spend(self) -> None:
        self.used += 1

    def exhaust(self) -> None:
        self.used = self.daily_limit
