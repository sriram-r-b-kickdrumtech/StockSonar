"""Tests for rubric extension tools (mocked upstreams)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from stocksonar.tools.cross_source import cross_reference_signals
from stocksonar.tools.filings_tools import get_filing_document, list_company_filings
from stocksonar.tools.fundamentals_tools import get_corporate_actions, get_financial_statements
from stocksonar.tools.macro_tools import get_macro_historical_series, get_macro_snapshot_tool
from stocksonar.tools.market import get_price_history
from stocksonar.tools.mutual_funds import compare_mutual_funds
from stocksonar.tools.news_tools import analyze_news_sentiment, get_company_news
from stocksonar.tools.technicals_tools import get_technical_indicators
from stocksonar.tools.watchlist_tools import add_watchlist_symbol, list_watchlist


@pytest.mark.asyncio
@patch("stocksonar.upstream.fundamentals_data.get_cashflow_statement", return_value=[])
@patch("stocksonar.upstream.fundamentals_data.get_balance_sheet", return_value=[])
@patch("stocksonar.upstream.fundamentals_data.get_income_statement", return_value=[{"m": 1}])
async def test_get_financial_statements(mock_inc, mock_bs, mock_cf, tool_context):
    out = await get_financial_statements(tool_context, "RELIANCE.NS", quarterly=False)
    assert "Yahoo Finance" in out["source"]
    assert out["data"]["income_statement"] == [{"m": 1}]


@pytest.mark.asyncio
@patch("stocksonar.upstream.fundamentals_data.get_corporate_actions", return_value=[{"a": 1}])
async def test_get_corporate_actions(mock_ga, tool_context):
    out = await get_corporate_actions(tool_context, "RELIANCE.NS")
    assert out["data"]["actions"] == [{"a": 1}]


@pytest.mark.asyncio
@patch(
    "stocksonar.upstream.technicals_data.get_technical_indicators",
    return_value=[{"date": "2024-01-01", "close": 1.0, "rsi_14": 50.0}],
)
async def test_get_technical_indicators(mock_ti, tool_context):
    out = await get_technical_indicators(
        tool_context, "RELIANCE.NS", "2024-01-01", "2024-06-01"
    )
    assert len(out["data"]["indicators"]) == 1


@pytest.mark.asyncio
@patch(
    "stocksonar.tools.filings_tools.fu.list_filings",
    new_callable=AsyncMock,
)
async def test_list_company_filings(mock_list, tool_context):
    mock_list.return_value = [
        {
            "filing_id": "stub:X:2025-01-01:annual",
            "symbol": "X",
            "form_type": "ANNUAL_REPORT",
            "filed_date": "2025-01-01",
            "title": "t",
            "source_url": None,
            "exchange": "BSE/NSE illustrative + Finnhub",
        }
    ]
    out = await list_company_filings(tool_context, "RELIANCE.NS", limit=5)
    assert len(out["data"]["filings"]) == 1
    assert out["data"]["pagination"]["next_cursor"] is None


@pytest.mark.asyncio
@patch("stocksonar.tools.filings_tools.fu.stub_pdf_placeholder", return_value=b"%PDF-1.4")
async def test_get_filing_document_stub(mock_stub, tool_context):
    out = await get_filing_document(tool_context, "stub:RELIANCE:2025-01-01:annual")
    assert "content_base64" in out["data"]
    assert out["data"]["mime_type"] == "application/pdf"


@pytest.mark.asyncio
@patch(
    "stocksonar.tools.macro_tools.macro_api.get_macro_snapshot",
    return_value={
        "source": "test",
        "repo_rate_percent": 6.5,
        "note": "test note",
        "as_of": "2026-01-01T00:00:00+00:00",
    },
)
async def test_get_macro_snapshot_tool(_mock_snap, tool_context):
    out = await get_macro_snapshot_tool(tool_context)
    assert out["data"]["repo_rate_percent"] == 6.5
    assert "note" in out["data"]


@pytest.mark.asyncio
@patch("stocksonar.tools.macro_tools.mh.get_macro_series", return_value=[{"date": "2025-01-01"}])
async def test_get_macro_historical_series(mock_series, tool_context):
    out = await get_macro_historical_series(
        tool_context, series_id="repo_rate", days=10, limit=5
    )
    assert out["data"]["series_id"] == "repo_rate"
    assert len(out["data"]["points"]) <= 5


@pytest.mark.asyncio
@patch("stocksonar.tools.market.yfinance_client.get_price_history", return_value=[{"date": "d", "close": 1.0}])
async def test_get_price_history_paginated(mock_gh, tool_context):
    out = await get_price_history(
        tool_context,
        "RELIANCE.NS",
        "2024-01-01",
        "2024-06-01",
        limit=50,
    )
    assert out["data"]["ohlcv"][0]["close"] == 1.0
    assert "pagination" in out["data"]


@pytest.mark.asyncio
@patch("stocksonar.tools.mutual_funds.mfapi.get_nav", new_callable=AsyncMock)
async def test_compare_mutual_funds(mock_nav, tool_context):
    mock_nav.side_effect = [{"meta": "a"}, {"meta": "b"}]
    out = await compare_mutual_funds(tool_context, "111", "222")
    assert out["data"]["scheme_a"]["nav_payload"] == {"meta": "a"}


@pytest.mark.asyncio
@patch("stocksonar.tools.news_tools.news_api.company_news", new_callable=AsyncMock)
async def test_get_company_news_paginated(mock_cn, tool_context):
    mock_cn.return_value = ([{"title": "t"}], 99)
    out = await get_company_news(
        tool_context, "Reliance", max_results=5, limit=1, cursor=None
    )
    assert len(out["data"]["articles"]) == 1
    assert out["data"]["pagination"]["total"] == 1


@pytest.mark.asyncio
@patch("stocksonar.tools.news_tools.news_api.company_news", new_callable=AsyncMock)
async def test_analyze_news_sentiment(mock_cn, tool_context):
    mock_cn.return_value = ([{"title": "Stock gains on strong results"}], 1)
    out = await analyze_news_sentiment(tool_context, "ACME", max_results=3)
    assert "aggregate_score" in out["data"]
    assert out["data"]["articles"][0]["sentiment"]["label"]


@pytest.mark.asyncio
@patch("stocksonar.tools.watchlist_tools.get_access_token", return_value=None)
async def test_watchlist_crud(_tok, tool_context):
    await add_watchlist_symbol(tool_context, "TCS")
    out = await list_watchlist(tool_context)
    assert "TCS" in out["data"]["tickers"]


@pytest.mark.asyncio
@patch("stocksonar.middleware.tool_guard.get_access_token", return_value=None)
@patch("stocksonar.tools.cross_source.news_api.company_news", new_callable=AsyncMock)
@patch("stocksonar.tools.cross_source.mfapi.search_schemes", new_callable=AsyncMock)
@patch("stocksonar.tools.cross_source.asyncio.to_thread", new_callable=AsyncMock)
async def test_cross_reference_signals(mock_tt, mock_mf, mock_news, _tg, tool_context):
    mock_tt.return_value = {"ticker": "TCS.NS", "change_pct": 1.5, "ltp": 100}
    mock_news.return_value = ([{"title": "TCS stock rises on deal win"}], 3)
    mock_mf.return_value = [{"scheme_name": "TCS focused fund"}]
    out = await cross_reference_signals(tool_context, "TCS.NS")
    assert out["data"]["confirmations"]
    assert "sources_used" in out["data"]
