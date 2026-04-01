"""Global market and macro MCP resources (auth-scoped)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.config import get_settings
from stocksonar.services.market_overview import build_market_overview_payload
from stocksonar.upstream import macro as macro_api


def register_market_macro_resources(mcp) -> None:
    @mcp.resource(
        "market://overview",
        auth=require_scopes("market:read"),
    )
    async def market_overview(_ctx: Context) -> str:
        payload = await build_market_overview_payload(_ctx)
        return json.dumps(payload, indent=2, default=str)

    @mcp.resource(
        "macro://snapshot",
        auth=require_scopes("macro:read"),
    )
    async def macro_snapshot_resource(_ctx: Context) -> str:
        snap = await asyncio.to_thread(macro_api.get_macro_snapshot)
        settings = get_settings()

        out = {
            "source": snap.get("source") or "StockSonar macro",
            "disclaimer": settings.disclaimer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": snap,
        }
        return json.dumps(out, indent=2, default=str)
