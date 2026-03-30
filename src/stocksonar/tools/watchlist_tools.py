"""User watchlist CRUD."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.services.watchlist import WatchlistStore
from stocksonar.util.notifications import notify_watchlist_resource_updated
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


def _uid() -> str:
    t = get_access_token()
    if t is None:
        return "anonymous"
    c = getattr(t, "claims", None) or {}
    return str(c.get("sub") or t.client_id)


def _store(ctx: Context) -> WatchlistStore:
    return ctx.lifespan_context["watchlist"]


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


async def add_watchlist_symbol(ctx: Context, symbol: str) -> dict[str, Any]:
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="add_watchlist_symbol")
    uid = _uid()
    store = _store(ctx)
    cur = await store.load(uid)
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    if sym not in cur:
        cur.append(sym)
    await store.save(uid, cur)
    await notify_watchlist_resource_updated(ctx, uid)
    finish_audit_ok("add_watchlist_symbol")
    return ok_response({"tickers": cur}, "StockSonar watchlist")


async def remove_watchlist_symbol(ctx: Context, symbol: str) -> dict[str, Any]:
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="remove_watchlist_symbol")
    uid = _uid()
    store = _store(ctx)
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    cur = [x for x in await store.load(uid) if x != sym]
    await store.save(uid, cur)
    await notify_watchlist_resource_updated(ctx, uid)
    finish_audit_ok("remove_watchlist_symbol")
    return ok_response({"tickers": cur}, "StockSonar watchlist")


async def list_watchlist(ctx: Context) -> dict[str, Any]:
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="list_watchlist")
    uid = _uid()
    cur = await _store(ctx).load(uid)
    finish_audit_ok("list_watchlist")
    return ok_response({"tickers": cur}, "StockSonar watchlist")


def register_watchlist_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("watchlist:write", "watchlist:read"))(add_watchlist_symbol)
    mcp.tool(auth=require_scopes("watchlist:write", "watchlist:read"))(remove_watchlist_symbol)
    mcp.tool(auth=require_scopes("watchlist:read"))(list_watchlist)
