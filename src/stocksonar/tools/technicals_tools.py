"""Technicals + option chains — Premium scope."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import technicals_data as td
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


async def get_options_chain(
    ctx: Context,
    ticker: str,
    expiration: str | None = None,
) -> dict[str, Any]:
    """Listed options chain (nearest expiration if omitted)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_options_chain")
    data = await asyncio.to_thread(td.get_options_chain, ticker, expiration)
    finish_audit_ok("get_options_chain")
    return ok_response(data, "Yahoo Finance options")


async def get_technical_indicators(
    ctx: Context,
    ticker: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> dict[str, Any]:
    """RSI(14) and SMA bands from historical closes (Yahoo OHLCV)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_technical_indicators")
    rows = await asyncio.to_thread(td.get_technical_indicators, ticker, start, end, interval)
    finish_audit_ok("get_technical_indicators")
    return ok_response({"ticker": ticker, "indicators": rows}, "Yahoo Finance + StockSonar")


def register_technicals_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("technicals:read"))(get_options_chain)
    mcp.tool(auth=require_scopes("technicals:read"))(get_technical_indicators)
