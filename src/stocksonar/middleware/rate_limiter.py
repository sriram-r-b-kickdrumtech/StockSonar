"""Per-user sliding-window rate limits stored in Redis."""

from __future__ import annotations

import time
import uuid

import redis.asyncio as redis

from stocksonar.auth.scopes import tier_from_scopes
from stocksonar.config import Settings, get_settings


class RedisRateLimiter:
    WINDOW_SECONDS = 3600

    def __init__(self, client: redis.Redis, settings: Settings | None = None) -> None:
        self._r = client
        self._s = settings or get_settings()

    def _limit_for_tier(self, tier: str) -> int:
        if tier == "analyst":
            return self._s.rate_limit_analyst
        if tier == "premium":
            return self._s.rate_limit_premium
        return self._s.rate_limit_free

    async def check(self, user_key: str, scopes: frozenset[str]) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).
        If not allowed, retry_after is seconds until oldest slot frees (approx).
        """
        tier = tier_from_scopes(scopes)
        limit = self._limit_for_tier(tier)
        now = time.time()
        window_start = now - self.WINDOW_SECONDS
        key = f"ratelimit:{user_key}"

        member = f"{now}:{uuid.uuid4().hex}"
        pipe = self._r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()
        count = int(results[1])
        if count >= limit:
            oldest = await self._r.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_ts = float(oldest[0][1])
                retry_after = max(1, int(self.WINDOW_SECONDS - (now - oldest_ts)))
            else:
                retry_after = self.WINDOW_SECONDS
            return False, retry_after

        await self._r.zadd(key, {member: now})
        await self._r.expire(key, self.WINDOW_SECONDS)
        return True, 0
