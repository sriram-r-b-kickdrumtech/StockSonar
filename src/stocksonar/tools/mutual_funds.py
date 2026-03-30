"""Mutual fund tools (MFapi.in)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import mfapi
from stocksonar.util.pagination import paginate_slice, pagination_meta
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.middleware.rate_limiter import RedisRateLimiter
    from stocksonar.cache.redis_cache import RedisCache


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


def _cache(ctx: Context) -> RedisCache | None:
    return ctx.lifespan_context.get("cache")


async def search_mutual_funds(
    ctx: Context,
    query: str,
    cursor: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Search AMFI schemes via MFapi.in (paginated)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="search_mutual_funds")
    cache = _cache(ctx)
    qk = query.strip().lower()[:80]
    if cache:
        hit = await cache.get_json("mf_search", qk)
        if hit is not None:
            rows = hit.get("rows")
            if rows is None and isinstance(hit.get("data"), list):
                rows = hit["data"]
            if isinstance(rows, list):
                page, next_c = paginate_slice(rows, cursor=cursor, limit=limit)
                finish_audit_ok("search_mutual_funds")
                return ok_response(
                    {
                        "schemes": page,
                        "pagination": pagination_meta(
                            total=len(rows),
                            limit=limit,
                            cursor_in=cursor,
                            next_cursor=next_c,
                        ),
                    },
                    "MFapi.in",
                )
    rows = await mfapi.search_schemes(query)
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json(
            "mf_search", qk, {"rows": rows}, get_settings().ttl_mf_nav
        )
    page, next_c = paginate_slice(list(rows), cursor=cursor, limit=limit)
    finish_audit_ok("search_mutual_funds")
    return ok_response(
        {
            "schemes": page,
            "pagination": pagination_meta(
                total=len(rows),
                limit=limit,
                cursor_in=cursor,
                next_cursor=next_c,
            ),
        },
        "MFapi.in",
    )


async def get_fund_nav(ctx: Context, scheme_code: str) -> dict[str, Any]:
    """Latest and historical NAV for a scheme code."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_fund_nav")
    cache = _cache(ctx)
    ck = scheme_code.strip()
    if cache:
        hit = await cache.get_json("mf_nav", ck)
        if hit is not None:
            finish_audit_ok("get_fund_nav")
            return hit
    raw = await mfapi.get_nav(scheme_code)
    out = ok_response(raw, "MFapi.in")
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json("mf_nav", ck, out, get_settings().ttl_mf_nav)
    finish_audit_ok("get_fund_nav")
    return out


async def compare_mutual_funds(
    ctx: Context,
    scheme_code_a: str,
    scheme_code_b: str,
) -> dict[str, Any]:
    """Side-by-side latest NAV metadata for two schemes (MFapi.in)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="compare_mutual_funds")
    a, b = await mfapi.get_nav(scheme_code_a), await mfapi.get_nav(scheme_code_b)
    finish_audit_ok("compare_mutual_funds")
    return ok_response(
        {
            "scheme_a": {"code": scheme_code_a, "nav_payload": a},
            "scheme_b": {"code": scheme_code_b, "nav_payload": b},
        },
        "MFapi.in",
    )


def register_mf_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("mf:read"))(search_mutual_funds)
    mcp.tool(auth=require_scopes("mf:read"))(get_fund_nav)
    mcp.tool(auth=require_scopes("mf:read"))(compare_mutual_funds)
