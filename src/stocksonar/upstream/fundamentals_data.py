"""Fundamentals via yfinance (financials, holders, actions, calendar)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from stocksonar.upstream.yfinance_client import symbol_for_ticker


def _df_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    try:
        flat = df.copy()
        flat.columns = [
            "|".join(str(x) for x in c) if isinstance(c, tuple) else str(c)
            for c in flat.columns
        ]
        out = []
        for row in flat.reset_index().to_dict(orient="records"):
            clean = {}
            for k, v in row.items():
                key = str(k)
                if hasattr(v, "isoformat"):
                    clean[key] = v.isoformat()
                elif isinstance(v, float) and pd.isna(v):
                    clean[key] = None
                else:
                    clean[key] = v
            out.append(clean)
        return out
    except Exception:
        return []


def get_income_statement(ticker: str, *, quarterly: bool = False) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    df = t.quarterly_income_stmt if quarterly else t.income_stmt
    return _df_to_records(df)


def get_balance_sheet(ticker: str, *, quarterly: bool = False) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    df = t.quarterly_balance_sheet if quarterly else t.balance_sheet
    return _df_to_records(df)


def get_cashflow_statement(ticker: str, *, quarterly: bool = False) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    df = t.quarterly_cashflow if quarterly else t.cashflow
    return _df_to_records(df)


def get_major_holders(ticker: str) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    return _df_to_records(t.major_holders)


def get_institutional_holders(ticker: str) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    return _df_to_records(t.institutional_holders)


def get_corporate_actions(ticker: str) -> list[dict[str, Any]]:
    sym = symbol_for_ticker(ticker)
    t = yf.Ticker(sym)
    return _df_to_records(t.actions)


def get_earnings_calendar(ticker: str) -> list[dict[str, Any]]:
    try:
        sym = symbol_for_ticker(ticker)
        t = yf.Ticker(sym)
        cal = t.calendar
        if cal is None:
            return []
        if isinstance(cal, dict):
            return [cal]
        if isinstance(cal, pd.DataFrame):
            return _df_to_records(cal)
    except Exception:
        pass
    return []
