"""Server-wide GNews call budget (upstream quota + tier limits)."""

from __future__ import annotations

from datetime import date

import redis.asyncio as redis

from stocksonar.config import Settings, get_settings


class GnewsQuotaExceeded(Exception):
    """Raised when shared GNews daily quota is exhausted."""


async def acquire_gnews_slot(
    client: redis.Redis | None,
    settings: Settings | None = None,
) -> None:
    if client is None:
        return
    s = settings or get_settings()
    key = f"quota:gnews:{date.today().isoformat()}"
    n = await client.incr(key)
    if n == 1:
        await client.expire(key, 172800)
    if n > s.gnews_daily_quota:
        await client.decr(key)
        raise GnewsQuotaExceeded(
            f"GNews daily quota ({s.gnews_daily_quota}) reached — try again tomorrow or increase gnews_daily_quota."
        )
