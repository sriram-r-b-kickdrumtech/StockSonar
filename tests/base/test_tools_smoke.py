from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stocksonar.tools.market import get_top_gainers_losers
from stocksonar.tools.mutual_funds import search_mutual_funds


@pytest.mark.asyncio
async def test_get_top_gainers_losers_schema(tool_context):
    sample = {
        "gainers": [{"symbol": "A", "ltp": 1, "change_pct": 2}],
        "losers": [{"symbol": "B", "ltp": 1, "change_pct": -2}],
    }
    with patch("stocksonar.tools.market.nse.get_top_movers_from_preopen", return_value=sample):
        out = await get_top_gainers_losers(tool_context, "NSE")
    assert "source" in out
    assert out["data"]["gainers"]


@pytest.mark.asyncio
@patch("stocksonar.tools.mutual_funds.mfapi.search_schemes", new_callable=AsyncMock)
async def test_search_mutual_funds_schema(mock_search, tool_context):
    mock_search.return_value = [{"scheme_code": "119551", "scheme_name": "Test Fund"}]
    out = await search_mutual_funds(tool_context, "HDFC")
    assert "MFapi.in" in out["source"]
    assert out["data"]["schemes"][0]["scheme_code"] == "119551"
