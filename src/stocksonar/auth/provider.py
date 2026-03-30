"""Build FastMCP AuthProvider (Keycloak + RFC 9728, or static tokens for dev/tests)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import AnyHttpUrl

from fastmcp.server.auth.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier, StaticTokenVerifier

from stocksonar.auth.role_verifier import RoleMappingJWTVerifier
from stocksonar.auth.scopes import ALL_SCOPES
from stocksonar.config import Settings


def build_auth_provider(settings: Settings) -> Any:
    if settings.auth_mode == "static":
        raw: dict[str, Any] = json.loads(settings.static_tokens_json or "{}")
        # Normalize: each value must have client_id + scopes; optional sub for audit
        tokens: dict[str, dict[str, Any]] = {}
        for key, meta in raw.items():
            entry = dict(meta)
            entry.setdefault("client_id", "static-client")
            entry.setdefault("scopes", [])
            tokens[key] = entry
        inner = StaticTokenVerifier(tokens=tokens, required_scopes=None)
        return RemoteAuthProvider(
            token_verifier=inner,
            authorization_servers=[AnyHttpUrl(settings.keycloak_authorization_server)],
            base_url=AnyHttpUrl(settings.mcp_base_url),
            scopes_supported=sorted(ALL_SCOPES),
            resource_name="StockSonar MCP",
        )

    aud = (settings.keycloak_audience or "").strip() or "account"
    jwt_inner = JWTVerifier(
        jwks_uri=settings.keycloak_jwks_uri,
        issuer=settings.keycloak_issuer,
        audience=aud,
        required_scopes=None,
    )
    verifier = RoleMappingJWTVerifier(jwt_inner)
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(settings.keycloak_authorization_server)],
        base_url=AnyHttpUrl(settings.mcp_base_url),
        scopes_supported=sorted(ALL_SCOPES),
        resource_name="StockSonar MCP",
    )
