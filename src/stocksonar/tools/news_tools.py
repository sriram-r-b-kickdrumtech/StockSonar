"""News tools (GNews)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import news as news_api
from stocksonar.upstream.gnews_quota import GnewsQuotaExceeded, acquire_gnews_slot
from stocksonar.util.pagination import paginate_slice, pagination_meta
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.cache.redis_cache import RedisCache
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


def _cache(ctx: Context) -> RedisCache | None:
    return ctx.lifespan_context.get("cache")


def _redis(ctx: Context):
    return ctx.lifespan_context.get("redis")


async def get_company_news(
    ctx: Context,
    company_name: str,
    max_results: int = 10,
    cursor: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Latest news articles for a company (GNews). Paginated via cursor/limit on cached fetch."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_company_news")
    cache = _cache(ctx)
    ck = f"{company_name.lower()}:{max_results}"
    if cache:
        hit = await cache.get_json("news_company", ck)
        if hit is not None:
            items = hit.get("articles") or []
            page, next_c = paginate_slice(items, cursor=cursor, limit=limit)
            finish_audit_ok("get_company_news")
            return ok_response(
                {
                    "articles": page,
                    "pagination": pagination_meta(
                        total=len(items),
                        limit=limit,
                        cursor_in=cursor,
                        next_cursor=next_c,
                    ),
                },
                "GNews",
            )
    r = _redis(ctx)
    try:
        await acquire_gnews_slot(r)
    except GnewsQuotaExceeded as e:
        return ok_response(
            {"error": True, "code": "upstream_quota", "message": str(e)},
            "StockSonar",
        )
    try:
        articles, total = await news_api.company_news(company_name, max_results=max_results)
    except ValueError as e:
        return ok_response({"error": True, "code": "config", "message": str(e)}, "StockSonar")
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json(
            "news_company",
            ck,
            {"articles": articles, "totalArticles": total},
            get_settings().ttl_news,
        )
    items = articles
    page, next_c = paginate_slice(list(items), cursor=cursor, limit=limit)
    finish_audit_ok("get_company_news")
    return ok_response(
        {
            "articles": page,
            "pagination": pagination_meta(
                total=len(items),
                limit=limit,
                cursor_in=cursor,
                next_cursor=next_c,
            ),
            "gnews_total_hint": total,
        },
        "GNews",
    )


async def get_market_news(
    ctx: Context,
    max_results: int = 10,
    cursor: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Broad Indian market news (paginated)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_market_news")
    cache = _cache(ctx)
    ck = f"market:{max_results}"
    if cache:
        hit = await cache.get_json("news_market", ck)
        if hit is not None:
            items = hit.get("articles") or []
            page, next_c = paginate_slice(items, cursor=cursor, limit=limit)
            finish_audit_ok("get_market_news")
            return ok_response(
                {
                    "articles": page,
                    "pagination": pagination_meta(
                        total=len(items),
                        limit=limit,
                        cursor_in=cursor,
                        next_cursor=next_c,
                    ),
                },
                "GNews",
            )
    r = _redis(ctx)
    try:
        await acquire_gnews_slot(r)
    except GnewsQuotaExceeded as e:
        return ok_response(
            {"error": True, "code": "upstream_quota", "message": str(e)},
            "StockSonar",
        )
    try:
        articles, total = await news_api.market_news(max_results=max_results)
    except ValueError as e:
        return ok_response({"error": True, "code": "config", "message": str(e)}, "StockSonar")
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json(
            "news_market",
            ck,
            {"articles": articles, "totalArticles": total},
            get_settings().ttl_news,
        )
    page, next_c = paginate_slice(list(articles), cursor=cursor, limit=limit)
    finish_audit_ok("get_market_news")
    return ok_response(
        {
            "articles": page,
            "pagination": pagination_meta(
                total=len(articles),
                limit=limit,
                cursor_in=cursor,
                next_cursor=next_c,
            ),
            "gnews_total_hint": total,
        },
        "GNews",
    )


async def analyze_news_sentiment(
    ctx: Context,
    company_name: str,
    max_results: int = 15,
) -> dict[str, Any]:
    """Premium: lexicon-based sentiment per headline + aggregate (not a trading signal)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="analyze_news_sentiment")
    r = _redis(ctx)
    try:
        await acquire_gnews_slot(r)
    except GnewsQuotaExceeded as e:
        return ok_response(
            {"error": True, "code": "upstream_quota", "message": str(e)},
            "StockSonar",
        )
    try:
        articles, _ = await news_api.company_news(company_name, max_results=max_results)
    except ValueError as e:
        return ok_response({"error": True, "code": "config", "message": str(e)}, "StockSonar")
    scored = []
    for a in articles:
        title = a.get("title") or ""
        s = news_api.score_title_sentiment(title)
        scored.append({**a, "sentiment": s})
    agg = sum(s["sentiment"]["score"] for s in scored)
    finish_audit_ok("analyze_news_sentiment")
    return ok_response(
        {
            "company": company_name,
            "articles": scored,
            "aggregate_score": agg,
            "note": "Lexicon heuristic — verify with a real sentiment model in production.",
        },
        "GNews + StockSonar lexicon",
    )


def register_news_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("news:read"))(get_company_news)
    mcp.tool(auth=require_scopes("news:read"))(get_market_news)
    mcp.tool(auth=require_scopes("news:sentiment"))(analyze_news_sentiment)
