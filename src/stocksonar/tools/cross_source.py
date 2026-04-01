"""PS2 analyst-only cross-source tools."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.tools.portfolio import _rl
from stocksonar.tools.portfolio_metrics import valued_holdings
from stocksonar.upstream import fundamentals_data as fd
from stocksonar.upstream import macro as macro_api
from stocksonar.upstream import mfapi
from stocksonar.upstream import news as news_api
from stocksonar.upstream import yfinance_client
from stocksonar.util.response import ok_response


async def portfolio_risk_report(ctx: Context) -> dict[str, Any]:
    """Combine prices, sectors, live RBI policy snapshot (when available), news, MF overlap."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="portfolio_risk_report")
    hlist, total = await valued_holdings(ctx)
    macro = macro_api.get_macro_snapshot()
    overlap = await mfapi.search_schemes("large cap")
    overlap_note = [o.get("scheme_name") for o in overlap[:5]]
    narrative_parts = []
    sources_used = ["Yahoo Finance (prices)", "StockSonar (sectors)"]
    if hlist:
        top = max(hlist, key=lambda x: x.get("allocation_pct") or 0)
        narrative_parts.append(
            f"Largest position {top['symbol']} at {top.get('allocation_pct')}% of ₹{total:,.0f} portfolio value."
        )
    repo = macro.get("repo_rate_percent")
    repo_s = f"policy repo {repo}%" if repo is not None else "policy repo not parsed"
    narrative_parts.append(
        f"Macro ({repo_s}; {macro.get('source', 'unknown')}): {macro.get('note', '')}"
    )
    sources_used.append(macro.get("source") or "RBI macro snapshot")
    # News sample for first holding
    news_bits = []
    if hlist:
        try:
            art, _ = await news_api.company_news(hlist[0]["symbol"], max_results=3)
            news_bits = [a.get("title") for a in art]
            sources_used.append("GNews")
        except ValueError as e:
            news_bits = [str(e)]
    fundamentals_slice: list[dict[str, Any]] = []
    if hlist:
        topn = sorted(hlist, key=lambda x: x.get("allocation_pct") or 0, reverse=True)[:3]
        for row in topn:
            sym = row["symbol"]
            try:
                q = await asyncio.to_thread(yfinance_client.get_quote, sym)
            except Exception:
                q = {}
            try:
                inc = await asyncio.to_thread(fd.get_income_statement, sym, quarterly=True)
            except Exception:
                inc = []
            fundamentals_slice.append(
                {
                    "symbol": sym,
                    "quote_pe": q.get("pe_ratio"),
                    "quote_market_cap": q.get("market_cap"),
                    "income_statement_quarterly_preview": (inc[:2] if inc else []),
                }
            )
        sources_used.append("Yahoo Finance fundamentals")
    narrative_parts.append(f"Sample MF universe overlap search returned {len(overlap)} schemes; e.g. {overlap_note}.")
    sources_used.append("MFapi.in")
    if fundamentals_slice:
        narrative_parts.append(
            f"Fundamentals preview (top holdings): {len(fundamentals_slice)} symbols with PE and latest quarterly income rows."
        )
    confirmations = []
    contradictions = []
    if hlist and news_bits:
        confirmations.append(
            {
                "finding": "Recent headlines exist for top holding",
                "sources": ["GNews", "Yahoo Finance"],
            }
        )
    out = ok_response(
        {
            "portfolio_value": round(total, 2),
            "holdings": hlist,
            "macro": macro,
            "mf_large_cap_sample": overlap_note,
            "headlines_sample": news_bits,
            "fundamentals_slice": fundamentals_slice,
            "narrative": " ".join(narrative_parts),
            "sources_used": sources_used,
            "confirmations": confirmations,
            "contradictions": contradictions,
        },
        "Cross-source: Yahoo Finance + fundamentals + MFapi.in + GNews + StockSonar",
    )
    finish_audit_ok("portfolio_risk_report")
    return out


async def what_if_analysis(ctx: Context, rbi_rate_change_bps: int = -25) -> dict[str, Any]:
    """Simple scenario: assumed linear sensitivity for Financials / IT."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="what_if_analysis")
    hlist, total = await valued_holdings(ctx)
    historical_reaction: list[dict[str, Any]] = []
    if rbi_rate_change_bps < 0:
        for start, end, label in (
            ("2024-05-01", "2024-07-15", "Around mid-2024 easing narrative (illustrative)"),
            ("2023-02-01", "2023-04-30", "Early-2023 window (illustrative)"),
        ):
            rows = await asyncio.to_thread(
                yfinance_client.get_price_history, "^NSEI", start, end, "1d"
            )
            if len(rows) >= 2:
                c0 = rows[0].get("close")
                c1 = rows[-1].get("close")
                ch = None
                if c0 and c1:
                    try:
                        ch = round((float(c1) - float(c0)) / float(c0) * 100, 3)
                    except (TypeError, ValueError, ZeroDivisionError):
                        ch = None
                historical_reaction.append(
                    {
                        "benchmark": "^NSEI",
                        "window": label,
                        "start": start,
                        "end": end,
                        "return_pct_approx": ch,
                        "bars": len(rows),
                    }
                )
    impacts = []
    for h in hlist:
        sec = h.get("sector") or "Other"
        direction = "neutral"
        magnitude = 0.0
        reasoning = "No simple rule"
        if sec == "Financials" and rbi_rate_change_bps < 0:
            direction = "positive"
            magnitude = 0.15 * abs(rbi_rate_change_bps) / 25
            reasoning = "Lower policy rate — heuristic positive for banks/NBFCs"
        elif sec == "IT" and rbi_rate_change_bps < 0:
            direction = "mixed"
            magnitude = 0.05
            reasoning = "Weaker INR possible — mixed for IT exporters"
        impacts.append(
            {
                "symbol": h["symbol"],
                "sector": sec,
                "direction": direction,
                "magnitude_pct_estimate": magnitude,
                "reasoning": reasoning,
            }
        )
    note = (
        "Heuristic sector betas only — not predictive. "
        "historical_reaction uses Nifty index path around illustrative windows after past easing cycles; "
        "causal link to RBI cuts is not established."
    )
    out = ok_response(
        {
            "scenario": f"RBI {'cuts' if rbi_rate_change_bps < 0 else 'hikes'} {abs(rbi_rate_change_bps)} bps",
            "holdings_impact": impacts,
            "historical_reaction_nifty": historical_reaction,
            "net_portfolio_impact": "qualitative only",
            "note": note,
            "sources_used": [
                "StockSonar rules",
                "Yahoo Finance (weights + ^NSEI history)",
            ],
        },
        "StockSonar scenario model (not predictive)",
    )
    finish_audit_ok("what_if_analysis")
    return out


async def cross_reference_signals(ctx: Context, symbol: str) -> dict[str, Any]:
    """Analyst: align/disalign price move vs news lexicon vs MF name overlap (explicit confirm/contradict)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="cross_reference_signals")
    sym = symbol.strip().upper()
    try:
        q = await asyncio.to_thread(yfinance_client.get_quote, sym)
    except Exception:
        q = {}
    ch = q.get("change_pct")
    ch_f = float(ch) if ch is not None else None
    try:
        arts, _ = await news_api.company_news(sym, max_results=8)
    except ValueError as e:
        finish_audit_ok("cross_reference_signals")
        return ok_response(
            {"error": True, "message": str(e), "symbol": sym},
            "StockSonar",
        )
    confirmations: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    pos = neg = 0
    for a in arts:
        lab = news_api.score_title_sentiment(a.get("title") or "").get("label") or ""
        if lab in ("positive", "slightly_positive"):
            pos += 1
        if lab in ("negative", "slightly_negative"):
            neg += 1
    if ch_f is not None and ch_f < 0 and pos >= 2:
        contradictions.append(
            {
                "finding": "Price down but multiple positive-tilt headlines",
                "sources": ["Yahoo Finance (quote)", "GNews + StockSonar lexicon"],
            }
        )
    if ch_f is not None and ch_f > 0 and neg >= 2:
        contradictions.append(
            {
                "finding": "Price up but multiple negative-tilt headlines",
                "sources": ["Yahoo Finance (quote)", "GNews + StockSonar lexicon"],
            }
        )
    if ch_f is not None and ch_f > 0 and pos >= 1:
        confirmations.append(
            {
                "finding": "Price up with at least one positive-tilt headline",
                "sources": ["Yahoo Finance (quote)", "GNews + StockSonar lexicon"],
            }
        )
    if ch_f is not None and ch_f < 0 and neg >= 1:
        confirmations.append(
            {
                "finding": "Price down with at least one negative-tilt headline",
                "sources": ["Yahoo Finance (quote)", "GNews + StockSonar lexicon"],
            }
        )
    prefix = sym.replace(".NS", "").replace(".BO", "")[:4]
    schemes = await mfapi.search_schemes(prefix) if prefix else []
    overlap_hits = [s for s in schemes[:40] if prefix and prefix in (s.get("scheme_name") or "").upper()]
    if overlap_hits:
        confirmations.append(
            {
                "finding": "MF scheme names partially overlap ticker prefix (weak heuristic)",
                "sources": ["MFapi.in search", "StockSonar"],
            }
        )
    finish_audit_ok("cross_reference_signals")
    return ok_response(
        {
            "symbol": sym,
            "quote": q,
            "headlines": arts,
            "headline_sentiment_counts": {"positive_tilt": pos, "negative_tilt": neg},
            "mf_scheme_overlap_sample": overlap_hits[:5],
            "confirmations": confirmations,
            "contradictions": contradictions,
            "sources_used": [
                "Yahoo Finance",
                "GNews",
                "MFapi.in",
                "StockSonar lexicon",
            ],
        },
        "Cross-source: Yahoo Finance + GNews + MFapi.in",
    )


def register_cross_source_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("research:generate"))(portfolio_risk_report)
    mcp.tool(auth=require_scopes("research:generate"))(what_if_analysis)
    mcp.tool(auth=require_scopes("research:generate"))(cross_reference_signals)
