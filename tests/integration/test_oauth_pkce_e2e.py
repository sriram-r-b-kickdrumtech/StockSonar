"""
End-to-end: Keycloak Authorization Code + PKCE, then MCP session lists PS2 prompts.

Requires ``docker compose up -d`` with Keycloak (8090), MCP (8000), Redis.

Run::

    pytest tests/integration/test_oauth_pkce_e2e.py -v -m integration

Environment (optional overrides):

- ``STOCKSONAR_KEYCLOAK_BASE`` (default ``http://localhost:8090``)
- ``STOCKSONAR_MCP_URL`` (default ``http://localhost:8000/mcp``)
- ``STOCKSONAR_PKCE_USER`` / ``STOCKSONAR_PKCE_PASSWORD`` (default ``analyst`` / ``analystpass``)
- ``STOCKSONAR_INTEGRATION_TIMEOUT`` (default ``15`` seconds per HTTP call)
- ``STOCKSONAR_INTEGRATION_RETRIES`` / ``STOCKSONAR_INTEGRATION_RETRY_PAUSE`` — backoff while stack boots
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from tests.integration.keycloak_pkce import obtain_tokens_authorization_code_pkce

pytest.importorskip("bs4")


def _services_available() -> bool:
    """Probe stack with retries — Keycloak/MCP can be slow right after ``docker compose up``."""
    kc = os.environ.get("STOCKSONAR_KEYCLOAK_BASE", "http://localhost:8090").rstrip("/")
    mcp_base = os.environ.get("STOCKSONAR_MCP_BASE", "http://localhost:8000").rstrip("/")
    timeout = float(os.environ.get("STOCKSONAR_INTEGRATION_TIMEOUT", "15"))
    openid = f"{kc}/realms/stocksonar/.well-known/openid-configuration"
    attempts = int(os.environ.get("STOCKSONAR_INTEGRATION_RETRIES", "5"))
    pause = float(os.environ.get("STOCKSONAR_INTEGRATION_RETRY_PAUSE", "1.0"))

    for attempt in range(attempts):
        try:
            r1 = httpx.get(openid, timeout=timeout, follow_redirects=True)
            r1.raise_for_status()
            body = r1.json()
            if not isinstance(body, dict) or "issuer" not in body:
                raise ValueError("unexpected openid-configuration body")
            r2 = httpx.get(f"{mcp_base}/health", timeout=timeout, follow_redirects=True)
            r2.raise_for_status()
            return True
        except Exception:
            if attempt + 1 >= attempts:
                return False
            time.sleep(pause)
    return False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pkce_authorization_code_then_mcp_lists_ps2_prompts():
    if not _services_available():
        pytest.skip(
            "Keycloak or MCP not reachable — start stack: docker compose up -d",
        )

    kc = os.environ.get("STOCKSONAR_KEYCLOAK_BASE", "http://localhost:8090").rstrip("/")
    mcp_url = os.environ.get("STOCKSONAR_MCP_URL", "http://localhost:8000/mcp")
    user = os.environ.get("STOCKSONAR_PKCE_USER", "analyst")
    password = os.environ.get("STOCKSONAR_PKCE_PASSWORD", "analystpass")
    # Any http(s) callback is accepted by imported realm (redirectUris: "*"); no listener required.
    # Prefer localhost — some Keycloak builds treat 127.0.0.1 redirects differently.
    redirect_uri = os.environ.get(
        "STOCKSONAR_PKCE_REDIRECT_URI",
        "http://localhost:59999/oauth/callback",
    )

    tokens = obtain_tokens_authorization_code_pkce(
        keycloak_base=kc,
        realm="stocksonar",
        client_id="stocksonar-mcp",
        redirect_uri=redirect_uri,
        username=user,
        password=password,
    )
    assert "access_token" in tokens
    access = tokens["access_token"]
    assert isinstance(access, str) and len(access) > 20

    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    transport = StreamableHttpTransport(
        mcp_url,
        auth=access,
        headers={"Accept": "application/json"},
    )
    async with Client(transport) as client:
        plist = await client.list_prompts()
        names = {p.name for p in plist}

    assert "morning_risk_brief" in names
    assert "rebalance_suggestions" in names
    assert "earnings_exposure" in names
