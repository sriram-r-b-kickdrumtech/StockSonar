from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stocksonar.tools.cross_source import portfolio_risk_report


@pytest.mark.asyncio
@patch("stocksonar.middleware.tool_guard.get_access_token", return_value=None)
@patch("stocksonar.tools.portfolio_metrics.valued_holdings", new_callable=AsyncMock)
@patch("stocksonar.tools.cross_source.mfapi.search_schemes", new_callable=AsyncMock)
@patch("stocksonar.tools.cross_source.news_api.company_news", new_callable=AsyncMock)
@patch(
    "stocksonar.tools.cross_source.macro_api.get_macro_snapshot",
    return_value={
        "source": "test-rbi",
        "repo_rate_percent": 6.5,
        "note": "n",
        "as_of": "2026-01-01T00:00:00+00:00",
    },
)
async def test_portfolio_risk_report_combines_sources(
    _mock_macro, mock_news, mock_mf, mock_vh, _tok, tool_context
):
    mock_vh.return_value = (
        [
            {
                "symbol": "TCS",
                "allocation_pct": 50.0,
                "sector": "IT",
                "current_value": 100000,
            }
        ],
        200000.0,
    )
    mock_mf.return_value = [{"scheme_name": "ICICI Large Cap"}]
    mock_news.return_value = ([{"title": "Headline"}], 1)
    await tool_context.lifespan_context["portfolio"].save(
        "anonymous", [{"symbol": "TCS", "quantity": 1, "avg_buy_price": 1, "sector": "IT"}]
    )
    out = await portfolio_risk_report(tool_context)
    su = out["data"]["sources_used"]
    assert len(su) >= 3
