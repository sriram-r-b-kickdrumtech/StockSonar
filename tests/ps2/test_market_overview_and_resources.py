from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from stocksonar.services.market_overview import build_market_overview_payload
from stocksonar.tools.market import refresh_market_overview


@pytest.mark.asyncio
async def test_build_market_overview_payload_structure(tool_context):
    with (
        patch(
            "stocksonar.services.market_overview.nse.get_index_data",
            return_value={"name": "NIFTY 50", "last": 1.0},
        ),
        patch(
            "stocksonar.services.market_overview.nse.get_top_movers_from_preopen",
            return_value={"gainers": [], "losers": []},
        ),
    ):
        p = await build_market_overview_payload(tool_context)
    assert "source" in p
    assert "disclaimer" in p
    assert "timestamp" in p
    assert "NIFTY_50" in p["data"]["indices"]


@pytest.mark.asyncio
async def test_refresh_market_overview_invalidates_cache(tool_context):
    with (
        patch(
            "stocksonar.services.market_overview.nse.get_index_data",
            return_value={"last": 2.0},
        ),
        patch(
            "stocksonar.services.market_overview.nse.get_top_movers_from_preopen",
            return_value={},
        ),
        patch(
            "stocksonar.tools.market.notify_market_overview_updated",
            new_callable=AsyncMock,
        ) as mock_notify,
    ):
        out = await refresh_market_overview(tool_context)
    mock_notify.assert_awaited()
    assert out["data"]["indices"]["NIFTY_50"]["last"] == 2.0
