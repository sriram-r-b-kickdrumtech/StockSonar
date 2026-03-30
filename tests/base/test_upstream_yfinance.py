from __future__ import annotations

from unittest.mock import MagicMock, patch

from stocksonar.upstream import yfinance_client


def test_symbol_for_ticker_appends_ns():
    assert yfinance_client.symbol_for_ticker("reliance") == "RELIANCE.NS"
    assert yfinance_client.symbol_for_ticker("INFY.NS") == "INFY.NS"


@patch("stocksonar.upstream.yfinance_client.yf.Ticker")
def test_get_quote_valid_ticker(mock_ticker):
    inst = MagicMock()
    inst.fast_info = {
        "lastPrice": 100.0,
        "previousClose": 99.0,
        "lastVolume": 1000,
        "marketCap": 1e12,
        "fiftyTwoWeekHigh": 110,
        "fiftyTwoWeekLow": 90,
    }
    inst.info = {"trailingPE": 20}
    mock_ticker.return_value = inst
    q = yfinance_client.get_quote("TEST")
    assert q["ltp"] == 100.0
    assert q["change_pct"] is not None


@patch("stocksonar.upstream.yfinance_client.yf.Ticker")
def test_get_price_history_empty(mock_ticker):
    inst = MagicMock()
    hist = MagicMock()
    hist.empty = True
    inst.history.return_value = hist
    mock_ticker.return_value = inst
    assert yfinance_client.get_price_history("X", "2020-01-01", "2020-01-02") == []
