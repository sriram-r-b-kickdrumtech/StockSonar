from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stocksonar.tools.portfolio import (
    add_to_portfolio,
    get_portfolio_summary,
    remove_from_portfolio,
)


@pytest.mark.asyncio
@patch("stocksonar.tools.portfolio.get_access_token", return_value=None)
async def test_add_and_remove_portfolio(_tok, tool_context):
    r = await add_to_portfolio(tool_context, "RELIANCE", 10, 2500.0)
    assert any(h["symbol"] == "RELIANCE" for h in r["data"]["holdings"])
    r2 = await remove_from_portfolio(tool_context, "RELIANCE")
    assert not any(h["symbol"] == "RELIANCE" for h in r2["data"]["holdings"])


@pytest.mark.asyncio
@patch("stocksonar.tools.portfolio.get_access_token", return_value=None)
@patch("stocksonar.tools.portfolio.asyncio.to_thread", new_callable=AsyncMock)
async def test_get_portfolio_summary(mock_tt, _tok, tool_context):
    mock_tt.return_value = {
        "ltp": 110.0,
        "change_pct": 0.0,
        "volume": 1,
        "market_cap": 1,
        "pe_ratio": 1,
        "week_52_high": 120,
        "week_52_low": 90,
    }
    await add_to_portfolio(tool_context, "RELIANCE", 2, 100.0)
    out = await get_portfolio_summary(tool_context)
    assert out["data"]["total_value"] > 0
    assert len(out["data"]["holdings"]) == 1
