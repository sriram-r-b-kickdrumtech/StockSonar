"""Shared portfolio valuation helpers (no extra tool audit/rate-limit)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context

from stocksonar.services.portfolio import PortfolioStore, sector_for
from stocksonar.tools.portfolio import _store, _user_id
from stocksonar.upstream import yfinance_client


async def valued_holdings(ctx: Context) -> tuple[list[dict[str, Any]], float]:
    uid = _user_id()
    store: PortfolioStore = _store(ctx)
    raw = await store.load(uid)
    hlist = []
    total_value = 0.0
    for h in raw:
        sym = h["symbol"]
        qty = float(h["quantity"])
        avg = float(h["avg_buy_price"])
        try:
            q = await asyncio.to_thread(yfinance_client.get_quote, sym)
        except Exception:
            q = {}
        ltp = q.get("ltp") or avg
        try:
            ltp_f = float(ltp)
        except (TypeError, ValueError):
            ltp_f = avg
        cur = qty * ltp_f
        total_value += cur
        hlist.append(
            {
                "symbol": sym,
                "quantity": qty,
                "avg_buy_price": avg,
                "ltp": ltp_f,
                "current_value": cur,
                "pnl": cur - qty * avg,
                "allocation_pct": None,
                "sector": h.get("sector") or sector_for(sym),
            }
        )
    for d in hlist:
        if total_value > 0:
            d["allocation_pct"] = round(100.0 * d["current_value"] / total_value, 2)
    return hlist, total_value
