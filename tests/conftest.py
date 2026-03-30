from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import fakeredis.aioredis as fakeredis_aioredis
import pytest

from stocksonar.cache.redis_cache import RedisCache
from stocksonar.config import get_settings
from stocksonar.middleware.rate_limiter import RedisRateLimiter
from stocksonar.services.portfolio import PortfolioStore
from stocksonar.services.watchlist import WatchlistStore


@pytest.fixture
async def tool_context() -> AsyncIterator[Any]:
    settings = get_settings()
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    cache = RedisCache(client, settings)
    rl = RedisRateLimiter(client, settings)
    portfolio = PortfolioStore(client)
    watchlist = WatchlistStore(client)
    ctx = SimpleNamespace(
        lifespan_context={
            "redis": client,
            "cache": cache,
            "rate_limiter": rl,
            "portfolio": portfolio,
            "watchlist": watchlist,
            "settings": settings,
        }
    )
    yield ctx
    await client.aclose()
