"""Wrap JWT verification and add scopes from Keycloak realm_access.roles."""

from __future__ import annotations

from typing import Any

from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier

from stocksonar.auth.scopes import scopes_for_realm_roles


class RoleMappingJWTVerifier(TokenVerifier):
    """Delegate to JWTVerifier, then union scope strings from realm roles."""

    def __init__(self, inner: JWTVerifier) -> None:
        super().__init__(required_scopes=None)
        self._inner = inner

    async def verify_token(self, token: str) -> AccessToken | None:
        at = await self._inner.verify_token(token)
        if at is None:
            return None
        claims: dict[str, Any] = dict(at.claims) if at.claims else {}
        realm_access = claims.get("realm_access") or {}
        roles: list[str] = list(realm_access.get("roles") or [])
        from_roles = scopes_for_realm_roles(roles)
        merged = list(dict.fromkeys([*at.scopes, *from_roles]))
        return at.model_copy(update={"scopes": merged})
