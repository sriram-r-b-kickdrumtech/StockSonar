from __future__ import annotations

import pytest

from stocksonar.cache.redis_cache import RedisCache
from stocksonar.config import get_settings


@pytest.mark.asyncio
async def test_cache_set_and_get():
    import fakeredis.aioredis as fa

    r = fa.FakeRedis(decode_responses=True)
    c = RedisCache(r, get_settings())
    await c.set_json("quote", "X", {"a": 1}, 60)
    v = await c.get_json("quote", "X")
    assert v == {"a": 1}
    await r.aclose()


@pytest.mark.asyncio
async def test_cache_miss_returns_none():
    import fakeredis.aioredis as fa

    r = fa.FakeRedis(decode_responses=True)
    c = RedisCache(r, get_settings())
    assert await c.get_json("nope", "id") is None
    await r.aclose()


@pytest.mark.asyncio
async def test_cache_key_format():
    import fakeredis.aioredis as fa

    r = fa.FakeRedis(decode_responses=True)
    c = RedisCache(r, get_settings())
    await c.set_json("t", "id", [1], 10)
    raw = await r.get("cache:t:id")
    assert raw is not None
    await r.aclose()
