"""FastMCP StockSonar server entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp import FastMCP

from stocksonar.auth.provider import build_auth_provider
from stocksonar.cache.redis_cache import RedisCache
from stocksonar.config import get_settings
from stocksonar.middleware.http_rate_limit import RateLimitHttpMiddleware
from stocksonar.middleware.rate_limiter import RedisRateLimiter
from stocksonar.services.portfolio import PortfolioStore
from stocksonar.services.watchlist import WatchlistStore
from stocksonar.tools.register import register_all_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as e:
        logger.warning("Redis ping failed: %s — tools may error at runtime", e)
    cache = RedisCache(client, settings)
    rate_limiter = RedisRateLimiter(client, settings)
    portfolio = PortfolioStore(client)
    watchlist = WatchlistStore(client)
    try:
        yield {
            "redis": client,
            "cache": cache,
            "rate_limiter": rate_limiter,
            "portfolio": portfolio,
            "watchlist": watchlist,
            "settings": settings,
        }
    finally:
        await client.aclose()


def create_app() -> FastMCP:
    settings = get_settings()
    auth = build_auth_provider(settings)
    mcp = FastMCP(
        "StockSonar",
        instructions=(
            "Indian financial intelligence MCP: market data, mutual funds, news, "
            "and PS2 portfolio risk tools. All outputs are JSON facts with sources — not advice."
        ),
        auth=auth,
        lifespan=lifespan,
    )
    register_all_tools(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "stocksonar",
                "redis_url_configured": bool(settings.redis_url),
            }
        )

    return mcp


mcp = create_app()


def main() -> None:
    import asyncio

    settings = get_settings()
    asyncio.run(
        mcp.run_http_async(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
            path=settings.streamable_http_path,
            json_response=settings.mcp_json_response,
            middleware=[
                Middleware(
                    RateLimitHttpMiddleware,
                    mcp_path=settings.streamable_http_path,
                ),
            ],
        )
    )


if __name__ == "__main__":
    main()
