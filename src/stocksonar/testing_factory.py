"""Build a FastMCP app without HTTP auth (for in-process / unit tests)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import fakeredis.aioredis as fakeredis_aioredis
from fastmcp import FastMCP

from stocksonar.cache.redis_cache import RedisCache
from stocksonar.config import get_settings
from stocksonar.middleware.rate_limiter import RedisRateLimiter
from stocksonar.services.portfolio import PortfolioStore
from stocksonar.services.watchlist import WatchlistStore
from stocksonar.tools.register import register_all_tools


@asynccontextmanager
async def test_lifespan(_server: FastMCP) -> AsyncIterator[dict]:
    settings = get_settings()
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
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


def create_test_mcp() -> FastMCP:
    """MCP server with tools registered and **no** auth (works with in-memory Client)."""

    @asynccontextmanager
    async def lf(s: FastMCP):
        async with test_lifespan(s) as ctx:
            yield ctx

    mcp = FastMCP(
        "StockSonarTest",
        instructions="Test server",
        auth=None,
        lifespan=lf,
    )
    register_all_tools(mcp)
    return mcp
