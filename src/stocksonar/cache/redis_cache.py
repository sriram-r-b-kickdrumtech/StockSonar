"""TTL cache on Redis."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from stocksonar.config import Settings, get_settings


class RedisCache:
    def __init__(self, client: redis.Redis, settings: Settings | None = None) -> None:
        self._r = client
        self._s = settings or get_settings()

    def _key(self, data_type: str, identifier: str) -> str:
        return f"cache:{data_type}:{identifier}"

    async def get_json(self, data_type: str, identifier: str) -> Any | None:
        raw = await self._r.get(self._key(data_type, identifier))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(
        self, data_type: str, identifier: str, value: Any, ttl_seconds: int
    ) -> None:
        await self._r.set(
            self._key(data_type, identifier),
            json.dumps(value, default=str),
            ex=ttl_seconds,
        )

    async def set_json_forever(self, data_type: str, identifier: str, value: Any) -> None:
        """No TTL (e.g. filings body cache per rubric)."""
        await self._r.set(
            self._key(data_type, identifier),
            json.dumps(value, default=str),
        )

    async def delete(self, data_type: str, identifier: str) -> None:
        await self._r.delete(self._key(data_type, identifier))
