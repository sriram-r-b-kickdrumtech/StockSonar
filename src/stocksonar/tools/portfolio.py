"""PS2 portfolio CRUD and summary."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.services.portfolio import PortfolioStore, sector_for
from stocksonar.upstream import yfinance_client
from stocksonar.services.portfolio_alerts import HEALTH_SOURCE
from stocksonar.util.notifications import notify_portfolio_resources_updated
from stocksonar.util.response import ok_response


def _user_id() -> str:
    t = get_access_token()
    if t is None:
        return "anonymous"
    c = getattr(t, "claims", None) or {}
    return str(c.get("sub") or t.client_id)


def _store(ctx: Context) -> PortfolioStore:
    return ctx.lifespan_context["portfolio"]


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


async def _resolve_sector(sym: str) -> str:
    """Hardcoded map first, then Yahoo Finance info, then 'Other'."""
    known = sector_for(sym)
    if known != "Other":
        return known
    try:
        import yfinance as yf
        ticker_sym = f"{sym}.NS"
        info = await asyncio.to_thread(lambda: yf.Ticker(ticker_sym).info)
        yf_sector = (info or {}).get("sector") or ""
        if yf_sector:
            return str(yf_sector)
    except Exception:
        pass
    return "Other"


async def add_to_portfolio(
    ctx: Context,
    symbol: str,
    quantity: float,
    avg_buy_price: float,
) -> dict[str, Any]:
    """Add or update a holding (quantity and average buy price)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="add_to_portfolio")
    qty = float(quantity)
    price = float(avg_buy_price)
    if qty <= 0:
        return ok_response(
            {"error": True, "message": "quantity must be greater than 0"},
            "StockSonar",
        )
    if price <= 0:
        return ok_response(
            {"error": True, "message": "avg_buy_price must be greater than 0"},
            "StockSonar",
        )
    uid = _user_id()
    store = _store(ctx)
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")

    # Validate: check if Yahoo Finance knows this symbol
    is_valid = await asyncio.to_thread(yfinance_client.is_valid_ticker, sym)
    if not is_valid:
        finish_audit_ok("add_to_portfolio")
        return ok_response(
            {
                "error": True,
                "message": f"Symbol '{sym}' not found on NSE/BSE (Yahoo Finance returned no price for {sym}.NS). "
                "Use valid NSE symbols like RELIANCE, TCS, INFY, HDFCBANK, SBIN, ITC, etc.",
            },
            "StockSonar",
        )

    holdings = await store.load(uid)
    found = False
    for h in holdings:
        if h.get("symbol") == sym:
            h["quantity"] = qty
            h["avg_buy_price"] = price
            if h.get("sector") in ("Other", None):
                h["sector"] = await _resolve_sector(sym)
            found = True
            break
    if not found:
        sector = await _resolve_sector(sym)
        holdings.append(
            {
                "symbol": sym,
                "quantity": qty,
                "avg_buy_price": price,
                "sector": sector,
            }
        )
    await store.save(uid, holdings)
    await notify_portfolio_resources_updated(ctx, uid)
    out = ok_response({"holdings": holdings}, "StockSonar portfolio store + Yahoo Finance (sector)")
    finish_audit_ok("add_to_portfolio")
    return out


async def remove_from_portfolio(ctx: Context, symbol: str) -> dict[str, Any]:
    """Remove a holding by symbol."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="remove_from_portfolio")
    uid = _user_id()
    store = _store(ctx)
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    holdings = [h for h in await store.load(uid) if h.get("symbol") != sym]
    await store.save(uid, holdings)
    await notify_portfolio_resources_updated(ctx, uid)
    out = ok_response({"holdings": holdings}, "StockSonar portfolio store")
    finish_audit_ok("remove_from_portfolio")
    return out


async def get_portfolio_summary(ctx: Context) -> dict[str, Any]:
    """Current value, P&L, and allocation (uses Yahoo Finance LTP)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_portfolio_summary")
    uid = _user_id()
    store = _store(ctx)
    holdings = await store.load(uid)
    details = []
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
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
        cost = qty * avg
        total_value += cur
        total_cost += cost
        details.append(
            {
                "symbol": sym,
                "quantity": qty,
                "avg_buy_price": avg,
                "ltp": ltp_f,
                "current_value": cur,
                "pnl": cur - cost,
                "allocation_pct": None,
                "sector": h.get("sector") or sector_for(sym),
            }
        )
    for d in details:
        if total_value > 0:
            d["allocation_pct"] = round(100.0 * d["current_value"] / total_value, 2)
    out = ok_response(
        {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_value - total_cost, 2),
            "holdings": details,
        },
        "Yahoo Finance + StockSonar",
    )
    finish_audit_ok("get_portfolio_summary")
    return out


async def portfolio_health_check(ctx: Context) -> dict[str, Any]:
    """Concentration and sector exposure snapshot (Premium+)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="portfolio_health_check")
    uid = _user_id()
    store = _store(ctx)
    holdings = await store.load(uid)
    if not holdings:
        return ok_response(
            {"concentration_risk": [], "sector_exposure": {}, "top_holdings_pct": []},
            "StockSonar",
        )
    from stocksonar.tools.portfolio_metrics import valued_holdings

    hlist, _total_value = await valued_holdings(ctx)
    sector_map: dict[str, float] = {}
    for h in hlist:
        sec = h.get("sector") or "Other"
        sector_map[sec] = sector_map.get(sec, 0.0) + float(h.get("allocation_pct") or 0)
    flags = []
    for h in hlist:
        ap = float(h.get("allocation_pct") or 0)
        if ap > 20:
            flags.append(
                {
                    "type": "single_stock",
                    "symbol": h["symbol"],
                    "allocation_pct": ap,
                    "message": f"{h['symbol']} is {ap:.1f}% of portfolio (>20% threshold)",
                    "source": HEALTH_SOURCE,
                }
            )
    for sec, pct in sector_map.items():
        if pct > 40:
            flags.append(
                {
                    "type": "sector",
                    "sector": sec,
                    "allocation_pct": pct,
                    "message": f"{sec} sector is {pct:.1f}% (>40% threshold)",
                    "source": HEALTH_SOURCE,
                }
            )
    top = sorted(hlist, key=lambda x: x.get("allocation_pct") or 0, reverse=True)[:5]
    await store.set_alerts(uid, flags)
    await notify_portfolio_resources_updated(ctx, uid)
    out = ok_response(
        {
            "concentration_risk": flags,
            "sector_exposure": sector_map,
            "top_holdings_pct": top,
        },
        "StockSonar derived from Yahoo Finance quotes",
    )
    finish_audit_ok("portfolio_health_check")
    return out


def register_portfolio_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("portfolio:write", "portfolio:read"))(add_to_portfolio)
    mcp.tool(auth=require_scopes("portfolio:write", "portfolio:read"))(
        remove_from_portfolio
    )
    mcp.tool(auth=require_scopes("portfolio:read"))(get_portfolio_summary)
    mcp.tool(auth=require_scopes("portfolio:risk"))(portfolio_health_check)
