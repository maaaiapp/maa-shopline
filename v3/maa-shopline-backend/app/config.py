"""Settings + production isolation assertion.

All secrets come from the environment (server side only). Nothing here is ever
serialised to a client response.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Unresolved: sources disagree (jojyjj… vs j0jyjj…). Must be set explicitly per
# environment after confirming in the Supabase dashboard. No default on purpose.
SUPABASE_REF_ENV = "SHOPLINE_SUPABASE_REF"

# Hosts the app is allowed to talk to. Anything else configured as an endpoint
# fails the startup assertion in production.
PROVIDER_HOSTS = {
    "integrate.api.nvidia.com",
    "api.groq.com",
    "openrouter.ai",
    "generativelanguage.googleapis.com",
}
SHOPLINE_HOST_RE = re.compile(r"^[a-z0-9-]+\.myshopline\.com$")


class IsolationError(RuntimeError):
    pass


@dataclass
class Settings:
    env: str = "dev"
    supabase_ref: str = ""
    database_url: str = ""
    supabase_url: str = ""
    shopline_app_key: str = ""
    shopline_app_secret: str = ""
    shopline_redirect_uri: str = ""
    shopline_scopes: str = ""
    token_encryption_key: str = ""
    nvidia_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    gemini_api_key: str = ""
    extra_endpoints: list[str] = field(default_factory=list)
    drain_secret: str = ""            # shared with pg_cron (Vault) and GitHub Actions
    admin_token: str = ""             # /admin access
    alert_webhook_url: str = ""       # Slack or Discord incoming webhook
    webhook_ts_header: str = ""       # SHOPLINE timestamp header name, once confirmed
    webhook_max_age_s: int = 300
    ios_callback_url: str = "maashopline://auth"   # ASWebAuthenticationSession callback

    @classmethod
    def from_env(cls) -> "Settings":
        g = os.environ.get
        return cls(
            env=g("APP_ENV", "dev"),
            supabase_ref=g(SUPABASE_REF_ENV, ""),
            database_url=g("DATABASE_URL", ""),
            supabase_url=g("SUPABASE_URL", ""),
            shopline_app_key=g("SHOPLINE_APP_KEY", ""),
            shopline_app_secret=g("SHOPLINE_APP_SECRET", ""),
            shopline_redirect_uri=g("SHOPLINE_REDIRECT_URI", ""),
            shopline_scopes=g("SHOPLINE_SCOPES", ""),
            token_encryption_key=g("TOKEN_ENCRYPTION_KEY", ""),
            nvidia_api_key=g("NVIDIA_API_KEY", ""),
            groq_api_key=g("GROQ_API_KEY", ""),
            openrouter_api_key=g("OPENROUTER_API_KEY", ""),
            gemini_api_key=g("GEMINI_API_KEY", ""),
            extra_endpoints=[e for e in g("EXTRA_ENDPOINTS", "").split(",") if e],
            drain_secret=g("DRAIN_SECRET", ""),
            admin_token=g("ADMIN_TOKEN", ""),
            alert_webhook_url=g("ALERT_WEBHOOK_URL", ""),
            webhook_ts_header=g("SHOPLINE_WEBHOOK_TS_HEADER", ""),
            webhook_max_age_s=int(g("SHOPLINE_WEBHOOK_MAX_AGE_S", "300")),
            ios_callback_url=g("IOS_CALLBACK_URL", "maashopline://auth"),
        )


def assert_isolated(s: Settings) -> None:
    """Refuse to boot in production if anything points outside the SHOPLINE project."""
    problems: list[str] = []
    ref = s.supabase_ref.strip()
    if not re.fullmatch(r"[a-z0-9]{20}", ref or ""):
        problems.append("SHOPLINE_SUPABASE_REF missing or malformed")
    if s.supabase_url:
        host = urlparse(s.supabase_url).hostname or ""
        if host != f"{ref}.supabase.co":
            problems.append(f"SUPABASE_URL host {host!r} is not the SHOPLINE project")
    if s.database_url:
        # Supabase DB hosts/users carry the project ref (db.<ref>.supabase.co or postgres.<ref>@pooler)
        if ref not in s.database_url:
            problems.append("DATABASE_URL does not reference the SHOPLINE project ref")
    for ep in s.extra_endpoints:
        host = urlparse(ep).hostname or ""
        if host not in PROVIDER_HOSTS and not SHOPLINE_HOST_RE.match(host) and not host.endswith(f"{ref}.supabase.co"):
            problems.append(f"endpoint {host!r} is outside the allowed set")
    if s.alert_webhook_url:
        ah = urlparse(s.alert_webhook_url).hostname or ""
        if ah not in ("hooks.slack.com", "discord.com", "discordapp.com"):
            problems.append(f"alert webhook host {ah!r} is not Slack or Discord")
    for name in ("shopline_app_secret", "token_encryption_key", "database_url", "drain_secret", "admin_token"):
        if not getattr(s, name):
            problems.append(f"{name.upper()} not set")
    if problems and s.env == "prod":
        raise IsolationError("; ".join(problems))
    return None
