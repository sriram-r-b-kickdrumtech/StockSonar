"""PS2 risk detection tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.services.portfolio import PortfolioStore, sector_for
from stocksonar.tools.portfolio import _rl, _user_id
from stocksonar.upstream import mfapi, macro as macro_api, news as news_api
from stocksonar.util.response import ok_response


async def check_concentration_risk(ctx: Context) -> dict[str, Any]:
    """Flag single stock >20% or sector >40%."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="check_concentration_risk")
    uid = _user_id()
    store: PortfolioStore = ctx.lifespan_context["portfolio"]
    holdings = await store.load(uid)
    if not holdings:
        return ok_response({"flags": []}, "StockSonar")
    from stocksonar.tools.portfolio_metrics import valued_holdings

    hlist, _ = await valued_holdings(ctx)
    flags = []
    for h in hlist:
        ap = float(h.get("allocation_pct") or 0)
        if ap > 20:
            flags.append(
                {
                    "kind": "single_stock",
                    "symbol": h["symbol"],
                    "allocation_pct": ap,
                }
            )
    sector_map: dict[str, float] = {}
    for h in hlist:
        sec = h.get("sector") or "Other"
        sector_map[sec] = sector_map.get(sec, 0.0) + float(h.get("allocation_pct") or 0)
    for sec, pct in sector_map.items():
        if pct > 40:
            flags.append({"kind": "sector", "sector": sec, "allocation_pct": pct})
    out = ok_response({"flags": flags}, "StockSonar + Yahoo Finance")
    finish_audit_ok("check_concentration_risk")
    return out


async def check_mf_overlap(ctx: Context) -> dict[str, Any]:
    """Heuristic overlap: large-cap style schemes whose names mention held symbols."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="check_mf_overlap")
    uid = _user_id()
    store: PortfolioStore = ctx.lifespan_context["portfolio"]
    holdings = await store.load(uid)
    symbols = [h["symbol"] for h in holdings]
    overlapping_schemes: list[dict[str, Any]] = []
    for kw in ("large cap", "nifty 50", "flexi cap"):
        rows = await mfapi.search_schemes(kw)
        for row in rows[:30]:
            name = (row.get("scheme_name") or "").upper()
            hits = [s for s in symbols if s in name]
            if hits:
                overlapping_schemes.append(
                    {
                        "scheme_code": row.get("scheme_code"),
                        "scheme_name": row.get("scheme_name"),
                        "matched_symbols": hits,
                    }
                )
    out = ok_response(
        {
            "overlapping_schemes": overlapping_schemes[:25],
            "overlap_score": len(overlapping_schemes),
            "note": "Heuristic match: scheme name contains equity symbol (MFapi.in search).",
        },
        "MFapi.in + StockSonar",
    )
    finish_audit_ok("check_mf_overlap")
    return out


async def check_macro_sensitivity(ctx: Context) -> dict[str, Any]:
    """Flag holdings likely sensitive to rates/forex (rule-based)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="check_macro_sensitivity")
    uid = _user_id()
    store: PortfolioStore = ctx.lifespan_context["portfolio"]
    macro = macro_api.get_macro_snapshot()
    sensitive = []
    for h in await store.load(uid):
        sym = h["symbol"]
        sec = sector_for(sym)
        if sec == "Financials":
            sensitive.append(
                {
                    "symbol": sym,
                    "sensitivity_type": "interest_rate",
                    "reason": "Financials sector — margin sensitivity to RBI policy",
                }
            )
        if sec == "IT":
            sensitive.append(
                {
                    "symbol": sym,
                    "sensitivity_type": "forex",
                    "reason": "IT services — USD/INR revenue mix",
                }
            )
    macro_src = macro.get("source") or "macro snapshot"
    out = ok_response(
        {"macro": macro, "sensitive_holdings": sensitive},
        f"StockSonar rules + {macro_src}",
    )
    finish_audit_ok("check_macro_sensitivity")
    return out


async def detect_sentiment_shift(ctx: Context) -> dict[str, Any]:
    """Compare recent news volume/tone proxy vs prior window (lightweight heuristic)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="detect_sentiment_shift")
    uid = _user_id()
    store: PortfolioStore = ctx.lifespan_context["portfolio"]
    flags = []
    for h in await store.load(uid):
        sym = h["symbol"]
        try:
            recent, _ = await news_api.company_news(sym, max_results=5)
            older, _ = await news_api.company_news(f"{sym} stock", max_results=5)
        except ValueError as e:
            flags.append({"symbol": sym, "error": str(e)})
            continue
        score_recent = len(recent)
        score_older = len(older)
        if score_recent >= score_older + 2:
            flags.append(
                {
                    "symbol": sym,
                    "direction": "elevated_activity",
                    "magnitude": score_recent - score_older,
                    "note": "Article count proxy only — not NLP sentiment.",
                }
            )
    out = ok_response({"shifts": flags}, "GNews article-count heuristic")
    finish_audit_ok("detect_sentiment_shift")
    return out


def register_risk_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("portfolio:risk"))(check_concentration_risk)
    mcp.tool(auth=require_scopes("portfolio:risk"))(check_mf_overlap)
    mcp.tool(auth=require_scopes("portfolio:risk"))(check_macro_sensitivity)
    mcp.tool(auth=require_scopes("portfolio:risk"))(detect_sentiment_shift)
