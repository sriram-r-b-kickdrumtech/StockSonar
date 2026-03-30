"""Application settings from environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_files() -> tuple[str, ...]:
    """Load .env from the repo root (directory with pyproject.toml), then cwd if different.

    Order matches pydantic-settings: later files override earlier. Ensures keys work when
    PYTHONPATH=src and cwd is not the project root, and when running from a subfolder.
    """
    seen: set[Path] = set()
    paths: list[str] = []
    here = Path(__file__).resolve().parent
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            candidate = parent / ".env"
            if candidate.is_file():
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(str(resolved))
            break
    cwd_env = (Path.cwd() / ".env").resolve()
    if cwd_env.is_file() and cwd_env not in seen:
        paths.append(str(cwd_env))
    return tuple(paths)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Upstream
    gnews_api_key: str = ""
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""

    redis_url: str = "redis://localhost:6379/0"

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_base_url: str = "http://localhost:8000"
    streamable_http_path: str = "/mcp"
    # Strict rubric: JSON bodies enable HTTP 429 + Retry-After rewriting for tier limits.
    mcp_json_response: bool = True

    auth_mode: str = "keycloak"
    # When auth_mode=static: JSON object { "token-string": { "client_id": "...", "scopes": ["market:read"], "sub": "user1" } }
    static_tokens_json: str = "{}"
    # Keycloak public URL (host port 8090 in docker-compose; change if you remap)
    keycloak_issuer: str = "http://localhost:8090/realms/stocksonar"
    keycloak_jwks_uri: str = (
        "http://localhost:8090/realms/stocksonar/protocol/openid-connect/certs"
    )
    keycloak_authorization_server: str = "http://localhost:8090/realms/stocksonar"
    # RFC 8707 / JWT aud — Keycloak access tokens typically use "account"
    keycloak_audience: str = "account"

    rate_limit_free: int = 30
    rate_limit_premium: int = 150
    rate_limit_analyst: int = 500

    # Cache TTLs (seconds)
    ttl_quote: int = 60
    ttl_news: int = 1800
    ttl_financials: int = 86400
    ttl_mf_nav: int = 3600
    ttl_index: int = 60
    ttl_filings_meta: int = 86400
    ttl_macro_historical: int = 86400
    ttl_macro_snapshot: int = 3600

    # Shared upstream daily cap (GNews free tier is 100/day — stay under by default)
    gnews_daily_quota: int = 90

    disclaimer: str = (
        "Information is for informational purposes only and is not financial advice."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
