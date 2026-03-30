"""Technicals: options chain + simple indicators from OHLCV (yfinance)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from stocksonar.upstream.yfinance_client import get_price_history, symbol_for_ticker


def get_options_chain(ticker: str, expiration: str | None = None) -> dict[str, Any]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    dates = list(t.options or [])
    if not dates:
        return {"expirations": [], "calls": [], "puts": []}
    exp = expiration or dates[0]
    if exp not in dates:
        exp = dates[0]
    chain = t.option_chain(exp)
    calls = chain.calls.to_dict(orient="records") if chain.calls is not None else []
    puts = chain.puts.to_dict(orient="records") if chain.puts is not None else []
    return {"expiration": exp, "expirations": dates, "calls": calls, "puts": puts}


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_g = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def get_technical_indicators(
    ticker: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> list[dict[str, Any]]:
    rows = get_price_history(ticker, start, end, interval)
    if not rows:
        return []
    df = pd.DataFrame(rows)
    if "close" not in df.columns and "Close" in df.columns:
        df["close"] = df["Close"]
    if "close" not in df.columns:
        return []
    close = pd.to_numeric(df["close"], errors="coerce")
    df["sma_20"] = close.rolling(20, min_periods=1).mean()
    df["sma_50"] = close.rolling(50, min_periods=1).mean()
    df["rsi_14"] = _rsi(close, 14)
    out = []
    for i, r in df.iterrows():
        out.append(
            {
                "date": r.get("date"),
                "close": float(r["close"]) if r["close"] == r["close"] else None,
                "sma_20": float(r["sma_20"]) if pd.notna(r["sma_20"]) else None,
                "sma_50": float(r["sma_50"]) if pd.notna(r["sma_50"]) else None,
                "rsi_14": float(r["rsi_14"]) if pd.notna(r["rsi_14"]) else None,
            }
        )
    return out
