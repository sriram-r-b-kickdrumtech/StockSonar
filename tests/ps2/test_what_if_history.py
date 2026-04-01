from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from stocksonar.tools.cross_source import what_if_analysis


@pytest.mark.asyncio
@patch("stocksonar.middleware.tool_guard.get_access_token", return_value=None)
@patch("stocksonar.tools.cross_source.valued_holdings", new_callable=AsyncMock)
@patch(
    "stocksonar.tools.cross_source.yfinance_client.get_price_history",
    return_value=[
        {"close": 100.0},
        {"close": 102.0},
    ],
)
async def test_what_if_includes_historical_reaction(
    _mock_hist, mock_vh, _tok, tool_context
):
    mock_vh.return_value = (
        [{"symbol": "SBIN", "sector": "Financials", "allocation_pct": 100.0}],
        100000.0,
    )
    out = await what_if_analysis(tool_context, rbi_rate_change_bps=-25)
    hist = out["data"]["historical_reaction_nifty"]
    assert hist
    assert hist[0].get("return_pct_approx") is not None
