"""PDF / problem-statement tool names as thin aliases (same behavior as underlying tools)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.tools.portfolio import _rl
from stocksonar.upstream import macro as macro_api
from stocksonar.upstream import news as news_api
from stocksonar.upstream.gnews_quota import GnewsQuotaExceeded, acquire_gnews_slot
from stocksonar.util.response import ok_response


def _redis(ctx: Context):
    return ctx.lifespan_context.get("redis")


async def get_rbi_rates(ctx: Context) -> dict[str, Any]:
    """Alias: policy repo / MSF / SDF from RBI homepage snapshot (same as macro snapshot)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_rbi_rates")
    snap = await asyncio.to_thread(macro_api.get_macro_snapshot)
    data = {
        "repo_rate_percent": snap.get("repo_rate_percent"),
        "marginal_standing_facility_percent": snap.get("marginal_standing_facility_percent"),
        "standing_deposit_facility_percent": snap.get("standing_deposit_facility_percent"),
        "as_of": snap.get("as_of"),
        "note": snap.get("note"),
        "degraded": snap.get("degraded"),
    }
    src = snap.get("source") or "RBI (via StockSonar macro snapshot)"
    finish_audit_ok("get_rbi_rates")
    return ok_response(data, src)


async def get_inflation_data(ctx: Context) -> dict[str, Any]:
    """Alias: CPI placeholder + macro note (full series use macro:historical tools)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_inflation_data")
    snap = await asyncio.to_thread(macro_api.get_macro_snapshot)
    data = {
        "inflation_cpi_percent": snap.get("inflation_cpi_percent"),
        "as_of": snap.get("as_of"),
        "note": snap.get("note"),
        "hint": "Headline CPI is often null in the live RBI homepage scrape; use get_macro_historical_series for DBIE-style series.",
    }
    finish_audit_ok("get_inflation_data")
    return ok_response(data, snap.get("source") or "StockSonar macro")


async def get_news_sentiment(
    ctx: Context,
    company_name: str,
    max_results: int = 15,
) -> dict[str, Any]:
    """Alias for lexicon sentiment over headlines (same as analyze_news_sentiment)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_news_sentiment")
    r = _redis(ctx)
    try:
        await acquire_gnews_slot(r)
    except GnewsQuotaExceeded as e:
        finish_audit_ok("get_news_sentiment")
        return ok_response(
            {"error": True, "code": "upstream_quota", "message": str(e)},
            "StockSonar",
        )
    try:
        articles, _ = await news_api.company_news(company_name, max_results=max_results)
    except ValueError as e:
        finish_audit_ok("get_news_sentiment")
        return ok_response({"error": True, "code": "config", "message": str(e)}, "StockSonar")
    scored = []
    for a in articles:
        title = a.get("title") or ""
        s = news_api.score_title_sentiment(title)
        scored.append({**a, "sentiment": s})
    agg = sum(s["sentiment"]["score"] for s in scored)
    finish_audit_ok("get_news_sentiment")
    return ok_response(
        {
            "company": company_name,
            "articles": scored,
            "aggregate_score": agg,
            "note": "Lexicon heuristic — same as analyze_news_sentiment.",
        },
        "GNews + StockSonar lexicon",
    )


def register_ps2_alias_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("macro:read"))(get_rbi_rates)
    mcp.tool(auth=require_scopes("macro:read"))(get_inflation_data)
    mcp.tool(auth=require_scopes("news:sentiment"))(get_news_sentiment)
