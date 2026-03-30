"""Per-user watchlist in Redis (scoped by token sub)."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


class WatchlistStore:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def _key(self, user_id: str) -> str:
        return f"watchlist:{user_id}"

    async def load(self, user_id: str) -> list[str]:
        raw = await self._r.get(self._key(user_id))
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return [str(x).upper().strip() for x in data if x]
        except (json.JSONDecodeError, TypeError):
            return []

    async def save(self, user_id: str, tickers: list[str]) -> None:
        clean = sorted({str(t).upper().strip() for t in tickers if t})
        await self._r.set(self._key(user_id), json.dumps(clean))
