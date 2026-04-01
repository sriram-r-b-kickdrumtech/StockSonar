"""yfinance wrapper for quotes and OHLCV."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import yfinance as yf


def symbol_for_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.startswith("^"):
        return t
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    return f"{t}.NS"


def get_quote(ticker: str) -> dict[str, Any]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    try:
        info = dict(t.fast_info or {})
    except (KeyError, Exception):
        info = {}
    try:
        full = t.info or {}
    except Exception:
        full = {}
    ltp = info.get("lastPrice") or full.get("currentPrice") or full.get("regularMarketPrice")
    prev = info.get("previousClose") or full.get("previousClose")
    change_pct = None
    if ltp is not None and prev:
        try:
            change_pct = round((float(ltp) - float(prev)) / float(prev) * 100, 4)
        except (TypeError, ValueError, ZeroDivisionError):
            change_pct = None
    return {
        "ticker": sym,
        "ltp": ltp,
        "change_pct": change_pct,
        "volume": info.get("lastVolume") or full.get("volume"),
        "market_cap": info.get("marketCap") or full.get("marketCap"),
        "pe_ratio": full.get("trailingPE"),
        "week_52_high": info.get("fiftyTwoWeekHigh") or full.get("fiftyTwoWeekHigh"),
        "week_52_low": info.get("fiftyTwoWeekLow") or full.get("fiftyTwoWeekLow"),
        "valid": ltp is not None,
    }


def is_valid_ticker(ticker: str) -> bool:
    """Quick check: does Yahoo Finance return a last price for this symbol?"""
    try:
        q = get_quote(ticker)
        return bool(q.get("ltp"))
    except Exception:
        return False


def get_price_history(
    ticker: str,
    start: str | date | datetime,
    end: str | date | datetime,
    interval: str = "1d",
) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    hist = t.history(start=start, end=end, interval=interval, auto_adjust=True)
    if hist is None or hist.empty:
        return []
    out: list[dict[str, Any]] = []
    for idx, row in hist.iterrows():
        out.append(
            {
                "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                "open": float(row["Open"]) if row["Open"] == row["Open"] else None,
                "high": float(row["High"]) if row["High"] == row["High"] else None,
                "low": float(row["Low"]) if row["Low"] == row["Low"] else None,
                "close": float(row["Close"]) if row["Close"] == row["Close"] else None,
                "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else None,
            }
        )
    return out
