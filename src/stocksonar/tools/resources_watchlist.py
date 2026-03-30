"""Watchlist MCP resource."""

from __future__ import annotations

import json

from fastmcp import Context
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token

from stocksonar.services.watchlist import WatchlistStore


def _uid() -> str:
    t = get_access_token()
    if t is None:
        return "anonymous"
    c = getattr(t, "claims", None) or {}
    return str(c.get("sub") or t.client_id)


def register_watchlist_resources(mcp) -> None:
    @mcp.resource(
        "watchlist://{user_id}/tickers",
        auth=require_scopes("watchlist:read"),
    )
    async def watchlist_tickers(user_id: str, ctx: Context) -> str:
        if user_id != _uid():
            return json.dumps({"error": "forbidden", "message": "Resource scoped to token sub"})
        store: WatchlistStore = ctx.lifespan_context["watchlist"]
        data = await store.load(user_id)
        return json.dumps({"tickers": data}, indent=2)
