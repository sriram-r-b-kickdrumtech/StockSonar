"""NSE India via jugaad-data (live quotes, indices, movers from pre-open data)."""

from __future__ import annotations

from typing import Any

from stocksonar.config import get_settings


def _live():
    from jugaad_data.nse import live

    return live.NSELive()


def get_nse_equity_quote(symbol: str) -> dict[str, Any]:
    """Live equity quote (NSE). symbol without .NS suffix."""
    sym = symbol.replace(".NS", "").replace(".BO", "").upper()
    n = _live()
    raw = n.stock_quote(sym)
    d = raw.get("info", raw)
    return {
        "symbol": sym,
        "last_price": d.get("lastPrice"),
        "change": d.get("change"),
        "p_change": d.get("pChange"),
        "total_traded_volume": d.get("totalTradedVolume"),
    }


def get_index_data(index_name: str = "NIFTY 50") -> dict[str, Any]:
    n = _live()
    raw = n.live_index(index_name)
    data = raw.get("data", raw)
    if isinstance(data, list) and data:
        latest = data[0]
    elif isinstance(data, dict):
        latest = data
    else:
        latest = {}
    return {
        "name": index_name,
        "value": latest.get("last") or latest.get("lastPrice"),
        "change": latest.get("variation") or latest.get("change"),
        "raw": latest,
    }


def get_top_movers_from_preopen(key: str = "NIFTY") -> dict[str, list[dict[str, Any]]]:
    """Use pre-open / intra-day style list sorted by percent change."""
    n = _live()
    raw = n.pre_open_market(key)
    rows = raw.get("data") or []
    parsed: list[dict[str, Any]] = []
    for item in rows:
        meta = item.get("metadata") or {}
        parsed.append(
            {
                "symbol": meta.get("symbol"),
                "ltp": meta.get("lastPrice"),
                "change_pct": meta.get("pChange"),
                "volume": meta.get("finalQuantity"),
            }
        )
    parsed.sort(key=lambda x: (x.get("change_pct") is not None, x.get("change_pct") or 0))
    losers = [x for x in parsed if (x.get("change_pct") or 0) < 0]
    gainers = [x for x in parsed if (x.get("change_pct") or 0) >= 0]
    gainers.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
    losers.sort(key=lambda x: x.get("change_pct") or 0)
    top_n = 15
    return {
        "gainers": gainers[:top_n],
        "losers": losers[:top_n],
        "note": "Sorted from NSE pre-open snapshot (jugaad-data / NSE India).",
    }


def cache_ttl_index() -> int:
    return get_settings().ttl_index
