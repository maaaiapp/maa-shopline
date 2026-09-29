"""PartnershipAccessPolicy — every SHOPLINE capability traced to its authority.

A capability is usable only if its status is CONFIRMED. Anything else is
blocked at the adapter, so no code path can use an unconfirmed API "because it
exists". Statuses move to CONFIRMED only with a TD-nn decision reference from the
Technical Kickoff Pack §6 log.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    CONFIRMED = "CONFIRMED"            # written SHOPLINE confirmation or public doc + sandbox test
    PUBLIC_DOC = "PUBLIC_DOC"          # documented on developer.shopline.com, not yet sandbox-tested
    UNCONFIRMED = "UNCONFIRMED"        # TBD · REQUIRES TECHNICAL VALIDATION
    NOT_IN_SCOPE = "NOT_IN_SCOPE"


@dataclass(frozen=True)
class Capability:
    key: str
    clause: str            # agreement / proposal authority
    validation_item: str   # Kickoff Pack item
    access: str            # read | write
    retention: str
    owner: str             # owning service module
    screens: tuple[str, ...]
    status: Status
    evidence: str = ""


CAPABILITIES: dict[str, Capability] = {c.key: c for c in [
    Capability("oauth_install", "Sched. I §2 API connectivity", "P0-1/P1-5 · TD-09", "read",
               "token until uninstall", "shopline.oauth", ("02", "30"), Status.PUBLIC_DOC,
               "developer.shopline.com app-authorization"),
    Capability("webhooks", "Sched. I §2 data synchronization", "P1-2 · TD-06", "read",
               "webhook_events 30d", "shopline.webhooks", ("06", "10", "30"), Status.PUBLIC_DOC,
               "developer.shopline.com webhooks overview; topic list unconfirmed"),
    Capability("orders_read", "Sched. I §2; §7.3 minimum data", "P0-1 · TD-01", "read",
               "snapshot 13 months", "shopline.client", ("04", "06", "08", "09", "11", "13", "26"), Status.UNCONFIRMED),
    Capability("customers_read", "Sched. I §2; §7.3", "P0-1 · TD-01", "read",
               "snapshot 13 months, pseudonymised", "shopline.client", ("04", "09", "13"), Status.UNCONFIRMED),
    Capability("products_read", "Sched. I §2; §7.3", "P0-1 · TD-01", "read",
               "snapshot current", "shopline.client", ("05", "09"), Status.UNCONFIRMED),
    Capability("reviews_read", "Proposal pilot: VoC subject to merchant permission", "P0-2 · TD-02", "read",
               "verbatims 13 months, PII filtered", "shopline.client", ("14",), Status.UNCONFIRMED),
    Capability("campaign_write", "Proposal: AI Campaign Planner", "P0-3 · TD-03", "write",
               "campaign ids", "shopline.client", ("25",), Status.UNCONFIRMED),
    Capability("audience_write", "Proposal: AI Campaign Planner", "P1-3 · TD-07", "write",
               "segment ids", "shopline.client", ("24", "25"), Status.UNCONFIRMED),
    Capability("campaign_metrics_read", "Sched. I §4 live testing & validation", "P0-4 · TD-04", "read",
               "13 months", "shopline.client", ("26",), Status.UNCONFIRMED),
    Capability("competitor_data", "—", "Phase 2", "read", "—", "—", ("12", "15"), Status.NOT_IN_SCOPE),
    Capability("other_platform_connectors", "§5.3(c) prohibits", "—", "read", "—", "—", (), Status.NOT_IN_SCOPE),
]}


class CapabilityBlocked(Exception):
    def __init__(self, key: str, status: Status):
        super().__init__(f"capability {key} is {status.value}")
        self.key, self.status = key, status


def require(key: str, *, allow_public_doc: bool = True) -> Capability:
    cap = CAPABILITIES.get(key)
    if cap is None:
        raise CapabilityBlocked(key, Status.NOT_IN_SCOPE)
    ok = cap.status is Status.CONFIRMED or (allow_public_doc and cap.status is Status.PUBLIC_DOC)
    if not ok:
        raise CapabilityBlocked(key, cap.status)
    return cap
