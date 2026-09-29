"""AI Marketing Health Check — deterministic layer (numerical truth).

Scores are computed from snapshot data against the store's OWN history (Blueprint
screen 09: no peer benchmark in MVP). A dimension without the data/scope that
feeds it is returned UNSCORED with the unlocking scope — never estimated.

The scoring formulas are PROVISIONAL: no source document defines them. They are
isolated here so the MAA scoring model can replace them without touching callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MIN_ORDERS = 30          # below this: insufficient-knowledge path
MIN_HISTORY_DAYS = 60


@dataclass
class Dimension:
    key: str
    state: str                 # scored | unscored | insufficient
    score: int | None = None
    needs: str | None = None   # scope or data requirement
    inputs: dict | None = None # evidence: the numbers behind the score


def _clamp(x: float) -> int:
    return max(0, min(100, round(x)))


def _ratio_score(current: float, baseline: float) -> int:
    """50 = at own baseline; +/-50 at +/-100% change."""
    if baseline <= 0:
        return 50
    return _clamp(50 + 50 * (current - baseline) / baseline)


def score(orders: list[dict] | None, customers_scope: bool, today: date,
          window_days: int = 90) -> dict:
    """orders: [{'customer_id': str|None, 'created': date, 'total': float}] or None if scope missing."""
    if orders is None:
        dims = [Dimension(k, "unscored", needs="orders_read") for k in ("acquisition", "retention", "customer_value")]
    elif len(orders) < MIN_ORDERS or (today - min(o["created"] for o in orders)).days < MIN_HISTORY_DAYS:
        need = f"at least {MIN_ORDERS} orders across {MIN_HISTORY_DAYS} days"
        dims = [Dimension(k, "insufficient", needs=need) for k in ("acquisition", "retention", "customer_value")]
    else:
        cur_start, prev_start = today - timedelta(days=window_days), today - timedelta(days=2 * window_days)
        cur = [o for o in orders if o["created"] > cur_start]
        prev = [o for o in orders if prev_start < o["created"] <= cur_start]
        seen_before: set = {o["customer_id"] for o in orders if o["created"] <= cur_start and o["customer_id"]}

        def new_customers(rows, before):
            return len({o["customer_id"] for o in rows if o["customer_id"] and o["customer_id"] not in before})

        def repeat_rate(rows):
            ids = [o["customer_id"] for o in rows if o["customer_id"]]
            if not ids:
                return 0.0
            return sum(1 for c in set(ids) if ids.count(c) > 1) / len(set(ids))

        def aov(rows):
            return sum(o["total"] for o in rows) / len(rows) if rows else 0.0

        prev_before = {o["customer_id"] for o in orders if o["created"] <= prev_start and o["customer_id"]}
        acq_c, acq_p = new_customers(cur, seen_before), new_customers(prev, prev_before)
        rr_c, rr_p = repeat_rate(cur), repeat_rate(prev)
        aov_c, aov_p = aov(cur), aov(prev)
        guest_share = sum(1 for o in cur if not o["customer_id"]) / max(1, len(cur))
        dims = [
            Dimension("acquisition", "scored", _ratio_score(acq_c, acq_p), inputs={"new_customers": acq_c, "prior": acq_p}),
            Dimension("retention", "scored", _ratio_score(rr_c, rr_p),
                      inputs={"repeat_rate": round(rr_c, 4), "prior": round(rr_p, 4), "guest_share": round(guest_share, 4)}),
            Dimension("customer_value", "scored", _ratio_score(aov_c, aov_p),
                      inputs={"aov": round(aov_c, 2), "prior": round(aov_p, 2)}),
        ]
        if not customers_scope:
            dims[1].needs = "customers_read (retention computed from order-linked ids only)"
    # Brand and market position have no SHOPLINE-confirmed data source in MVP.
    dims += [Dimension("brand", "unscored", needs="merchant brand inputs + validated signal source"),
             Dimension("market_position", "unscored", needs="Phase 2 external market provider")]
    scored = [d for d in dims if d.state == "scored"]
    overall = round(sum(d.score for d in scored) / len(scored)) if scored else None
    constraint = min(scored, key=lambda d: d.score).key if scored else None
    maintenance = bool(scored) and all(d.score >= 50 for d in scored)
    return {"overall": overall, "binding_constraint": None if maintenance else constraint,
            "maintenance": maintenance, "coverage": f"{len(scored)} of {len(dims)}",
            "dimensions": [d.__dict__ for d in dims]}
