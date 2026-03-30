"""Macro snapshot + historical series."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import macro as macro_api
from stocksonar.upstream import macro_historical as mh
from stocksonar.util.pagination import paginate_slice, pagination_meta
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.cache.redis_cache import RedisCache
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


def _cache(ctx: Context) -> RedisCache | None:
    return ctx.lifespan_context.get("cache")


async def get_macro_snapshot_tool(ctx: Context) -> dict[str, Any]:
    """Current RBI policy rates (homepage scrape) plus honest gaps for CPI; Premium."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_macro_snapshot_tool")
    snap = await asyncio.to_thread(macro_api.get_macro_snapshot)
    src = snap.get("source") or "StockSonar macro"
    finish_audit_ok("get_macro_snapshot_tool")
    return ok_response(snap, src)


async def get_macro_historical_series(
    ctx: Context,
    series_id: str = "repo_rate",
    days: int = 365,
    cursor: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Historical macro series: illustrative paths; repo last point tied to live RBI when available."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_macro_historical_series")
    cache = _cache(ctx)
    ck = f"{series_id}:{days}"
    if cache:
        hit = await cache.get_json("macro_hist", ck)
        if hit is not None:
            items = hit.get("series") or []
            page, next_c = paginate_slice(items, cursor=cursor, limit=limit)
            finish_audit_ok("get_macro_historical_series")
            return ok_response(
                {
                    "series_id": series_id,
                    "points": page,
                    "series_methodology": mh.series_methodology_note(series_id),
                    "pagination": pagination_meta(
                        total=len(items),
                        limit=limit,
                        cursor_in=cursor,
                        next_cursor=next_c,
                    ),
                },
                "StockSonar illustrative macro series (see series_methodology)",
            )
    series = await asyncio.to_thread(mh.get_macro_series, series_id, days)
    payload = {"series": series, "series_id": series_id}
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json("macro_hist", ck, payload, get_settings().ttl_macro_historical)
    page, next_c = paginate_slice(list(series), cursor=cursor, limit=limit)
    finish_audit_ok("get_macro_historical_series")
    return ok_response(
        {
            "series_id": series_id,
            "points": page,
            "series_methodology": mh.series_methodology_note(series_id),
            "pagination": pagination_meta(
                total=len(series),
                limit=limit,
                cursor_in=cursor,
                next_cursor=next_c,
            ),
        },
        "StockSonar illustrative macro series (see series_methodology)",
    )


def register_macro_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("macro:read"))(get_macro_snapshot_tool)
    mcp.tool(auth=require_scopes("macro:historical"))(get_macro_historical_series)
