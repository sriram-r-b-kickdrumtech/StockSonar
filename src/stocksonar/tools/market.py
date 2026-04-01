"""Base market data MCP tools."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import nse, yfinance_client
from stocksonar.services.market_overview import (
    build_market_overview_payload,
    invalidate_market_overview_cache,
)
from stocksonar.util.notifications import notify_market_overview_updated
from stocksonar.util.pagination import paginate_slice, pagination_meta
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.middleware.rate_limiter import RedisRateLimiter
    from stocksonar.cache.redis_cache import RedisCache


def _rl(ctx: Context) -> RedisRateLimiter | None:
    return ctx.lifespan_context.get("rate_limiter")


def _cache(ctx: Context) -> RedisCache | None:
    return ctx.lifespan_context.get("cache")


async def get_stock_quote(ctx: Context, ticker: str) -> dict[str, Any]:
    """Live/latest quote for an NSE/BSE Yahoo symbol (e.g. RELIANCE.NS)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_stock_quote")
    cache = _cache(ctx)
    cache_key = ticker.upper()
    if cache:
        hit = await cache.get_json("quote", cache_key)
        if hit is not None:
            finish_audit_ok("get_stock_quote")
            return hit

    try:
        yq = await asyncio.to_thread(yfinance_client.get_quote, ticker)
    except Exception:
        yq = {}
    try:
        sym = yfinance_client.symbol_for_ticker(ticker)
        nse_q = await asyncio.to_thread(
            nse.get_nse_equity_quote, sym.replace(".NS", "").replace(".BO", "")
        )
    except Exception:
        nse_q = {}
    merged = {**yq, "nse": nse_q}
    out = ok_response(merged, "Yahoo Finance + NSE India (jugaad-data)")
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json("quote", cache_key, out, get_settings().ttl_quote)
    finish_audit_ok("get_stock_quote")
    return out


async def get_price_history(
    ctx: Context,
    ticker: str,
    start: str,
    end: str,
    interval: str = "1d",
    cursor: str | None = None,
    limit: int = 120,
) -> dict[str, Any]:
    """Historical OHLCV from Yahoo Finance (paginated)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_price_history")
    cache = _cache(ctx)
    ck = f"{ticker.upper()}:{start}:{end}:{interval}"
    if cache:
        hit = await cache.get_json("ohlcv", ck)
        if hit is not None:
            items = (hit.get("data") or {}).get("ohlcv") or hit.get("ohlcv") or []
            if isinstance(items, list):
                page, next_c = paginate_slice(items, cursor=cursor, limit=limit)
                finish_audit_ok("get_price_history")
                return ok_response(
                    {
                        "ticker": ticker,
                        "ohlcv": page,
                        "pagination": pagination_meta(
                            total=len(items),
                            limit=limit,
                            cursor_in=cursor,
                            next_cursor=next_c,
                        ),
                    },
                    "Yahoo Finance",
                )
    rows = await asyncio.to_thread(
        yfinance_client.get_price_history, ticker, start, end, interval
    )
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json(
            "ohlcv",
            ck,
            {"data": {"ohlcv": rows}},
            get_settings().ttl_quote * 2,
        )
    page, next_c = paginate_slice(list(rows), cursor=cursor, limit=limit)
    finish_audit_ok("get_price_history")
    return ok_response(
        {
            "ticker": ticker,
            "ohlcv": page,
            "pagination": pagination_meta(
                total=len(rows),
                limit=limit,
                cursor_in=cursor,
                next_cursor=next_c,
            ),
        },
        "Yahoo Finance",
    )


async def get_index_data(ctx: Context, index_name: str = "NIFTY 50") -> dict[str, Any]:
    """NSE index snapshot (e.g. NIFTY 50, NIFTY BANK)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_index_data")
    data = await asyncio.to_thread(nse.get_index_data, index_name)
    out = ok_response(data, "NSE India (jugaad-data)")
    finish_audit_ok("get_index_data")
    return out


async def refresh_market_overview(ctx: Context) -> dict[str, Any]:
    """Invalidate cache, rebuild NSE overview, notify subscribers of market://overview (PS2)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="refresh_market_overview")
    await invalidate_market_overview_cache(ctx)
    payload = await build_market_overview_payload(ctx)
    await notify_market_overview_updated(ctx)
    out = ok_response(payload["data"], payload["source"])
    finish_audit_ok("refresh_market_overview")
    return out


async def get_top_gainers_losers(ctx: Context, exchange: str = "NSE") -> dict[str, Any]:
    """Top movers from NSE snapshot (pre-open style listing)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_top_gainers_losers")
    key = "NIFTY" if exchange.upper() == "NSE" else "NIFTY"
    data = await asyncio.to_thread(nse.get_top_movers_from_preopen, key)
    out = ok_response(data, "NSE India (jugaad-data)")
    finish_audit_ok("get_top_gainers_losers")
    return out


def register_market_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("market:read"))(get_stock_quote)
    mcp.tool(auth=require_scopes("market:read"))(get_price_history)
    mcp.tool(auth=require_scopes("market:read"))(get_index_data)
    mcp.tool(auth=require_scopes("portfolio:risk"))(refresh_market_overview)
    mcp.tool(auth=require_scopes("market:read"))(get_top_gainers_losers)
