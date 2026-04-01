"""MCP resource update notifications (subscriptions / PS2)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp.types import AnyUrl, ResourceUpdatedNotification, ResourceUpdatedNotificationParams

if TYPE_CHECKING:
    from fastmcp import Context

logger = logging.getLogger(__name__)


async def notify_portfolio_resources_updated(ctx: Context, user_id: str) -> None:
    """Fire notifications/resources/updated for portfolio URIs (client must subscribe)."""
    try:
        for path in ("holdings", "alerts", "risk_score"):
            uri = f"portfolio://{user_id}/{path}"
            await ctx.send_notification(
                ResourceUpdatedNotification(
                    params=ResourceUpdatedNotificationParams(uri=AnyUrl(uri))
                )
            )
    except Exception:
        logger.debug("portfolio resource notify skipped", exc_info=True)


async def notify_market_overview_updated(ctx: Context) -> None:
    """Fire resources/updated for market://overview (subscription demo)."""
    try:
        uri = "market://overview"
        await ctx.send_notification(
            ResourceUpdatedNotification(
                params=ResourceUpdatedNotificationParams(uri=AnyUrl(uri))
            )
        )
    except Exception:
        logger.debug("market overview notify skipped", exc_info=True)


async def notify_watchlist_resource_updated(ctx: Context, user_id: str) -> None:
    try:
        uri = f"watchlist://{user_id}/tickers"
        await ctx.send_notification(
            ResourceUpdatedNotification(
                params=ResourceUpdatedNotificationParams(uri=AnyUrl(uri))
            )
        )
    except Exception:
        logger.debug("watchlist resource notify skipped", exc_info=True)
