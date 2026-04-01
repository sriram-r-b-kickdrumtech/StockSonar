"""Merge PS2 risk-tool findings into persisted portfolio alerts (Redis)."""

from __future__ import annotations

from typing import Any

from stocksonar.services.portfolio import PortfolioStore

MAX_ALERTS = 30
HEALTH_SOURCE = "portfolio_health_check"


def _alert_key(alert: dict[str, Any]) -> tuple[Any, ...]:
    t = alert.get("type") or alert.get("kind") or ""
    if t == "single_stock":
        return (t, str(alert.get("symbol") or "").upper())
    if t == "sector":
        return (t, str(alert.get("sector") or ""))
    if t == "sentiment_shift":
        return (t, str(alert.get("symbol") or "").upper())
    if t == "mf_overlap":
        return (t,)
    if t == "macro_adverse":
        return (t,)
    return (t, str(alert.get("symbol") or ""))


def _normalize_from_concentration(flag: dict[str, Any]) -> dict[str, Any]:
    kind = flag.get("kind") or ""
    if kind == "single_stock":
        sym = flag.get("symbol") or ""
        ap = float(flag.get("allocation_pct") or 0)
        return {
            "type": "single_stock",
            "symbol": sym,
            "allocation_pct": ap,
            "message": f"{sym} is {ap:.1f}% of portfolio (>20% threshold)",
            "source": "check_concentration_risk",
        }
    if kind == "sector":
        sec = flag.get("sector") or ""
        ap = float(flag.get("allocation_pct") or 0)
        return {
            "type": "sector",
            "sector": sec,
            "allocation_pct": ap,
            "message": f"{sec} sector is {ap:.1f}% (>40% threshold)",
            "source": "check_concentration_risk",
        }
    return {**flag, "type": kind or "unknown", "source": "check_concentration_risk"}


def _normalize_sentiment_shift(item: dict[str, Any]) -> dict[str, Any]:
    sym = item.get("symbol") or ""
    direction = item.get("direction") or "shift"
    mag = item.get("magnitude")
    w7 = item.get("window_7d") or {}
    w30 = item.get("window_30d") or {}
    msg = item.get("note") or (
        f"News/sentiment proxy shift for {sym}: {direction}"
        + (f" (magnitude {mag})" if mag is not None else "")
    )
    return {
        "type": "sentiment_shift",
        "symbol": sym,
        "direction": direction,
        "magnitude": mag,
        "window_7d": w7,
        "window_30d": w30,
        "message": msg,
        "source": "detect_sentiment_shift",
    }


def _normalize_mf_overlap(overlap_score: int) -> dict[str, Any]:
    return {
        "type": "mf_overlap",
        "message": f"MF name overlap heuristic found {overlap_score} scheme rows (review direct MF holdings).",
        "overlap_score": overlap_score,
        "source": "check_mf_overlap",
    }


def _normalize_macro_sensitivity(adverse: bool, reasons: list[str]) -> dict[str, Any]:
    return {
        "type": "macro_adverse",
        "message": "Macro headwinds: " + "; ".join(reasons) if reasons else "Adverse macro flagged",
        "adverse_macro": adverse,
        "macro_reasons": reasons,
        "source": "check_macro_sensitivity",
    }


async def merge_risk_alerts(
    store: PortfolioStore,
    user_id: str,
    new_alerts: list[dict[str, Any]],
) -> None:
    """Merge new alerts; existing rows from portfolio_health_check win on duplicate keys."""
    existing = await store.load_alerts(user_id)
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for a in existing:
        by_key[_alert_key(a)] = dict(a)

    for raw in new_alerts:
        k = _alert_key(raw)
        if not k or k == ("",):
            continue
        cur = by_key.get(k)
        if cur and cur.get("source") == HEALTH_SOURCE:
            continue
        by_key[k] = raw

    merged = list(by_key.values())
    merged.sort(key=lambda x: (x.get("type") or "", x.get("symbol") or ""))
    if len(merged) > MAX_ALERTS:
        merged = merged[:MAX_ALERTS]
    await store.set_alerts(user_id, merged)
