"""Build cached market overview payload for MCP resource market://overview."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from stocksonar.config import get_settings
from stocksonar.upstream import nse


MARKET_OVERVIEW_CACHE_TYPE = "market_overview"
MARKET_OVERVIEW_CACHE_ID = "global"


async def build_market_overview_payload(ctx: Any) -> dict[str, Any]:
    """Indices + top movers; Redis TTL via ttl_index when cache available."""
    settings = get_settings()
    cache = ctx.lifespan_context.get("cache")
    if cache:
        hit = await cache.get_json(MARKET_OVERVIEW_CACHE_TYPE, MARKET_OVERVIEW_CACHE_ID)
        if hit is not None:
            return hit

    nifty, bank, movers = await asyncio.gather(
        asyncio.to_thread(nse.get_index_data, "NIFTY 50"),
        asyncio.to_thread(nse.get_index_data, "NIFTY BANK"),
        asyncio.to_thread(nse.get_top_movers_from_preopen, "NIFTY"),
    )

    movers_trimmed: dict[str, Any] = movers if isinstance(movers, dict) else {}
    if isinstance(movers_trimmed, dict):
        for k in ("gainers", "losers"):
            v = movers_trimmed.get(k)
            if isinstance(v, list):
                movers_trimmed[k] = v[:8]

    payload = {
        "source": "NSE India (jugaad-data)",
        "disclaimer": settings.disclaimer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "indices": {
                "NIFTY_50": nifty,
                "NIFTY_BANK": bank,
            },
            "top_movers_sample": movers_trimmed,
        },
    }
    if cache:
        await cache.set_json(
            MARKET_OVERVIEW_CACHE_TYPE,
            MARKET_OVERVIEW_CACHE_ID,
            payload,
            settings.ttl_index,
        )
    return payload


async def invalidate_market_overview_cache(ctx: Any) -> None:
    """Clear cached overview so next read rebuilds (used by refresh tool)."""
    cache = ctx.lifespan_context.get("cache")
    if cache:
        await cache.delete(MARKET_OVERVIEW_CACHE_TYPE, MARKET_OVERVIEW_CACHE_ID)
