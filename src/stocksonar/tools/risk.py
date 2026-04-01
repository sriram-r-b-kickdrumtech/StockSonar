"""PS2 risk detection tools."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.services.portfolio import PortfolioStore, sector_for
from stocksonar.services.portfolio_alerts import (
    _normalize_from_concentration,
    _normalize_macro_sensitivity,
    _normalize_mf_overlap,
    _normalize_sentiment_shift,
    merge_risk_alerts,
)
from stocksonar.tools.portfolio import _rl, _user_id
from stocksonar.upstream import mfapi, macro as macro_api, news as news_api
from stocksonar.util.notifications import notify_portfolio_resources_updated
from stocksonar.util.response import ok_response


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _macro_adverse_assessment(macro: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if macro.get("degraded"):
        reasons.append("Macro snapshot marked degraded")
    fe = macro.get("fetch_error")
    if fe:
        reasons.append(f"RBI fetch error: {fe}")
    repo = macro.get("repo_rate_percent")
    if repo is not None and float(repo) >= 7.0:
        reasons.append(f"Policy repo at {repo}% (illustrative tight-policy threshold)")
    return bool(reasons), reasons


def _window_stats(articles: list[dict[str, Any]]) -> dict[str, Any]:
    scores: list[int] = []
    for a in articles:
        sc = int(news_api.score_title_sentiment(a.get("title") or "")["score"])
        scores.append(sc)
    n = len(scores)
    return {
        "article_count": n,
        "aggregate_lexicon_score": sum(scores),
        "avg_lexicon_score": round(sum(scores) / n, 4) if n else 0.0,
    }


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
    if flags:
        merged_alerts = [_normalize_from_concentration(f) for f in flags]
        await merge_risk_alerts(store, uid, merged_alerts)
        await notify_portfolio_resources_updated(ctx, uid)
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
    overlap_score = len(overlapping_schemes)
    if overlap_score >= 5 and holdings:
        await merge_risk_alerts(
            store, uid, [_normalize_mf_overlap(overlap_score)]
        )
        await notify_portfolio_resources_updated(ctx, uid)
    out = ok_response(
        {
            "overlapping_schemes": overlapping_schemes[:25],
            "overlap_score": overlap_score,
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
    adverse, macro_reasons = _macro_adverse_assessment(macro)
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
    if adverse and await store.load(uid):
        await merge_risk_alerts(
            store, uid, [_normalize_macro_sensitivity(adverse, macro_reasons)]
        )
        await notify_portfolio_resources_updated(ctx, uid)
    out = ok_response(
        {
            "macro": macro,
            "adverse_macro": adverse,
            "macro_reasons": macro_reasons,
            "sensitive_holdings": sensitive,
        },
        f"StockSonar rules + {macro_src}",
    )
    finish_audit_ok("check_macro_sensitivity")
    return out


async def detect_sentiment_shift(ctx: Context) -> dict[str, Any]:
    """Compare 7-day vs prior-window news using GNews date filters + lexicon scores."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="detect_sentiment_shift")
    uid = _user_id()
    store: PortfolioStore = ctx.lifespan_context["portfolio"]
    now = datetime.now(timezone.utc)
    from_7 = _iso_z(now - timedelta(days=7))
    to_now = _iso_z(now)
    from_30 = _iso_z(now - timedelta(days=30))
    to_prior_end = _iso_z(now - timedelta(days=7))
    shifts: list[dict[str, Any]] = []
    merge_items: list[dict[str, Any]] = []
    for h in await store.load(uid):
        sym = h["symbol"]
        try:
            art7, _ = await news_api.company_news(
                sym, max_results=20, from_iso=from_7, to_iso=to_now
            )
            art_prev, _ = await news_api.company_news(
                sym, max_results=20, from_iso=from_30, to_iso=to_prior_end
            )
        except ValueError as e:
            shifts.append({"symbol": sym, "error": str(e)})
            continue
        w7 = _window_stats(art7)
        w30 = _window_stats(art_prev)
        avg_diff = w7["avg_lexicon_score"] - w30["avg_lexicon_score"]
        count_spike = w7["article_count"] >= w30["article_count"] + 3
        tone_neg = avg_diff <= -0.4
        tone_pos = avg_diff >= 0.4
        if tone_neg:
            direction = "negative_tone"
        elif tone_pos:
            direction = "positive_tone"
        elif count_spike:
            direction = "elevated_activity"
        else:
            direction = "stable"
        shift_detected = tone_neg or tone_pos or count_spike
        row: dict[str, Any] = {
            "symbol": sym,
            "direction": direction,
            "shift_detected": shift_detected,
            "avg_lexicon_diff_7d_vs_prior": round(avg_diff, 4),
            "window_7d": w7,
            "window_30d": w30,
            "note": "window_30d = days 8–30 before now vs last 7d; lexicon only — not NLP.",
        }
        if shift_detected:
            row["magnitude"] = round(abs(avg_diff), 4)
            merge_items.append(
                _normalize_sentiment_shift(
                    {
                        "symbol": sym,
                        "direction": direction,
                        "magnitude": row["magnitude"],
                        "window_7d": w7,
                        "window_30d": w30,
                        "note": row["note"],
                    }
                )
            )
        shifts.append(row)
    if merge_items:
        await merge_risk_alerts(store, uid, merge_items)
        await notify_portfolio_resources_updated(ctx, uid)
    out = ok_response({"shifts": shifts}, "GNews + StockSonar lexicon (dated windows)")
    finish_audit_ok("detect_sentiment_shift")
    return out


def register_risk_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("portfolio:risk"))(check_concentration_risk)
    mcp.tool(auth=require_scopes("portfolio:risk"))(check_mf_overlap)
    mcp.tool(auth=require_scopes("portfolio:risk"))(check_macro_sensitivity)
    mcp.tool(auth=require_scopes("portfolio:risk"))(detect_sentiment_shift)
