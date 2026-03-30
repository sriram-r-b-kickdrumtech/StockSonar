"""User-scoped portfolio in Redis."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

# Rough sector map for Indian large caps (extend as needed)
SYMBOL_SECTOR: dict[str, str] = {
    "RELIANCE": "Energy",
    "TCS": "IT",
    "INFY": "IT",
    "HDFCBANK": "Financials",
    "ICICIBANK": "Financials",
    "SBIN": "Financials",
    "BHARTIARTL": "Telecom",
    "ITC": "FMCG",
    "LT": "Industrials",
    "AXISBANK": "Financials",
    "KOTAKBANK": "Financials",
    "WIPRO": "IT",
    "HCLTECH": "IT",
    "TECHM": "IT",
}


def sector_for(symbol: str) -> str:
    base = symbol.replace(".NS", "").replace(".BO", "").upper()
    return SYMBOL_SECTOR.get(base, "Other")


class PortfolioStore:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def _key(self, user_id: str) -> str:
        return f"portfolio:{user_id}:holdings"

    def _alerts_key(self, user_id: str) -> str:
        return f"portfolio:{user_id}:alerts"

    async def load(self, user_id: str) -> list[dict[str, Any]]:
        raw = await self._r.get(self._key(user_id))
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    async def save(self, user_id: str, holdings: list[dict[str, Any]]) -> None:
        await self._r.set(self._key(user_id), json.dumps(holdings))

    async def set_alerts(self, user_id: str, alerts: list[dict[str, Any]]) -> None:
        await self._r.set(self._alerts_key(user_id), json.dumps(alerts), ex=86400)

    async def load_alerts(self, user_id: str) -> list[dict[str, Any]]:
        raw = await self._r.get(self._alerts_key(user_id))
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
