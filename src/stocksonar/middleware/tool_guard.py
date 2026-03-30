"""Rate limit + audit around MCP tool execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp.server.dependencies import get_access_token

from stocksonar.auth.scopes import tier_from_scopes
from stocksonar.exceptions import RateLimitToolError
from stocksonar.middleware.audit import audit_tool_event

if TYPE_CHECKING:
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


async def enforce_tool_policies(
    *,
    rate_limiter: RedisRateLimiter | None,
    tool_name: str,
) -> None:
    token = get_access_token()
    if token is None:
        # STDIO / tests without HTTP auth
        return
    scopes = frozenset(token.scopes)
    tier = tier_from_scopes(scopes)
    user_id = (
        str(token.claims.get("sub"))
        if getattr(token, "claims", None) and token.claims.get("sub")
        else token.client_id
    )
    if rate_limiter is not None:
        ok, retry_after = await rate_limiter.check(user_id, scopes)
        if not ok:
            audit_tool_event(
                tool_name=tool_name,
                user_id=user_id,
                tier=tier,
                success=False,
                detail={"error": "rate_limit", "retry_after": retry_after},
            )
            raise RateLimitToolError(retry_after)


def finish_audit_ok(tool_name: str, token_scopes: frozenset[str] | None = None) -> None:
    token = get_access_token()
    if token is None:
        return
    scopes = frozenset(token.scopes) if token_scopes is None else token_scopes
    tier = tier_from_scopes(scopes)
    user_id = (
        str(token.claims.get("sub"))
        if getattr(token, "claims", None) and token.claims.get("sub")
        else token.client_id
    )
    audit_tool_event(
        tool_name=tool_name, user_id=user_id, tier=tier, success=True, detail={}
    )
