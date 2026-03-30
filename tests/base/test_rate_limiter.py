from __future__ import annotations

import pytest

from stocksonar.config import get_settings


@pytest.mark.asyncio
async def test_free_tier_allows_30_per_hour():
    import fakeredis.aioredis as fa

    from stocksonar.middleware.rate_limiter import RedisRateLimiter

    r = fa.FakeRedis(decode_responses=True)
    s = get_settings()
    lim = RedisRateLimiter(r, s)
    scopes = frozenset(["market:read"])
    for _ in range(30):
        ok, _ = await lim.check("user1", scopes)
        assert ok
    ok, ra = await lim.check("user1", scopes)
    assert not ok
    assert ra >= 1
    await r.aclose()


@pytest.mark.asyncio
async def test_rate_limit_per_user():
    import fakeredis.aioredis as fa

    from stocksonar.middleware.rate_limiter import RedisRateLimiter

    r = fa.FakeRedis(decode_responses=True)
    lim = RedisRateLimiter(r, get_settings())
    scopes = frozenset(["market:read"])
    ok, _ = await lim.check("u_a", scopes)
    assert ok
    ok2, _ = await lim.check("u_b", scopes)
    assert ok2
    await r.aclose()
