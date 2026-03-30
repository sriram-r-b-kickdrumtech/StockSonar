"""Fundamentals (financials, holders, actions, calendar) — Premium scope."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import fundamentals_data as fd
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.cache.redis_cache import RedisCache
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


def _cache(ctx: Context) -> RedisCache | None:
    return ctx.lifespan_context.get("cache")


async def get_financial_statements(
    ctx: Context,
    ticker: str,
    quarterly: bool = False,
) -> dict[str, Any]:
    """Income statement, balance sheet, and cash flow (Yahoo Finance)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_financial_statements")
    cache = _cache(ctx)
    ck = f"{ticker.upper()}:q={quarterly}"
    if cache:
        hit = await cache.get_json("financials", ck)
        if hit is not None:
            finish_audit_ok("get_financial_statements")
            return hit
    inc, bal, cf = await asyncio.gather(
        asyncio.to_thread(fd.get_income_statement, ticker, quarterly=quarterly),
        asyncio.to_thread(fd.get_balance_sheet, ticker, quarterly=quarterly),
        asyncio.to_thread(fd.get_cashflow_statement, ticker, quarterly=quarterly),
    )
    payload = {
        "ticker": ticker,
        "quarterly": quarterly,
        "income_statement": inc,
        "balance_sheet": bal,
        "cashflow": cf,
    }
    out = ok_response(payload, "Yahoo Finance fundamentals")
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json("financials", ck, out, get_settings().ttl_financials)
    finish_audit_ok("get_financial_statements")
    return out


async def get_shareholding_structure(ctx: Context, ticker: str) -> dict[str, Any]:
    """Major + institutional holders."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_shareholding_structure")
    cache = _cache(ctx)
    ck = ticker.upper()
    if cache:
        hit = await cache.get_json("holders", ck)
        if hit is not None:
            finish_audit_ok("get_shareholding_structure")
            return hit
    maj, inst = await asyncio.gather(
        asyncio.to_thread(fd.get_major_holders, ticker),
        asyncio.to_thread(fd.get_institutional_holders, ticker),
    )
    out = ok_response(
        {"ticker": ticker, "major_holders": maj, "institutional_holders": inst},
        "Yahoo Finance holders",
    )
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json("holders", ck, out, get_settings().ttl_financials)
    finish_audit_ok("get_shareholding_structure")
    return out


async def get_corporate_actions(ctx: Context, ticker: str) -> dict[str, Any]:
    """Splits, dividends, and similar corporate actions."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_corporate_actions")
    rows = await asyncio.to_thread(fd.get_corporate_actions, ticker)
    finish_audit_ok("get_corporate_actions")
    return ok_response({"ticker": ticker, "actions": rows}, "Yahoo Finance actions")


async def get_earnings_calendar(ctx: Context, ticker: str) -> dict[str, Any]:
    """Upcoming / historical earnings dates when available from Yahoo."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_earnings_calendar")
    rows = await asyncio.to_thread(fd.get_earnings_calendar, ticker)
    finish_audit_ok("get_earnings_calendar")
    return ok_response({"ticker": ticker, "calendar": rows}, "Yahoo Finance calendar")


def register_fundamentals_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("fundamentals:read"))(get_financial_statements)
    mcp.tool(auth=require_scopes("fundamentals:read"))(get_shareholding_structure)
    mcp.tool(auth=require_scopes("fundamentals:read"))(get_corporate_actions)
    mcp.tool(auth=require_scopes("fundamentals:read"))(get_earnings_calendar)
