"""Portfolio MCP resources (auth-scoped)."""

from __future__ import annotations

import json

from fastmcp import Context
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token

from stocksonar.services.portfolio import PortfolioStore


def _uid() -> str:
    t = get_access_token()
    if t is None:
        return "anonymous"
    c = getattr(t, "claims", None) or {}
    return str(c.get("sub") or t.client_id)


def register_portfolio_resources(mcp) -> None:
    @mcp.resource(
        "portfolio://{user_id}/holdings",
        auth=require_scopes("portfolio:read"),
    )
    async def portfolio_holdings(user_id: str, ctx: Context) -> str:
        if user_id != _uid():
            return json.dumps({"error": "forbidden", "message": "Resource scoped to token sub"})
        store: PortfolioStore = ctx.lifespan_context["portfolio"]
        data = await store.load(user_id)
        return json.dumps({"holdings": data}, indent=2)

    @mcp.resource(
        "portfolio://{user_id}/alerts",
        auth=require_scopes("portfolio:risk"),
    )
    async def portfolio_alerts(user_id: str, ctx: Context) -> str:
        if user_id != _uid():
            return json.dumps({"error": "forbidden"})
        store: PortfolioStore = ctx.lifespan_context["portfolio"]
        data = await store.load_alerts(user_id)
        return json.dumps({"alerts": data}, indent=2)

    @mcp.resource(
        "portfolio://{user_id}/risk_score",
        auth=require_scopes("portfolio:risk"),
    )
    async def portfolio_risk_score(user_id: str, ctx: Context) -> str:
        if user_id != _uid():
            return json.dumps({"error": "forbidden"})
        store: PortfolioStore = ctx.lifespan_context["portfolio"]
        alerts = await store.load_alerts(user_id)
        score = max(0, 100 - min(100, len(alerts) * 15))
        return json.dumps({"risk_score": score, "alert_count": len(alerts)})
