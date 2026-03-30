"""Macro time series: illustrative repo/CPI paths anchored to live RBI repo when available."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from stocksonar.upstream import macro as macro_live


def synthetic_repo_series(days: int = 365) -> list[dict[str, Any]]:
    """Deterministic smoothed series; last point aligned to live RBI policy repo when parsed."""
    end = date.today()
    out: list[dict[str, Any]] = []
    snap = macro_live.get_macro_snapshot()
    anchor = snap.get("repo_rate_percent")
    base = float(anchor) if anchor is not None else 6.5
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        val = round(base + 0.15 * ((i % 40) / 40 - 0.5), 3)
        out.append({"date": d.isoformat(), "repo_rate_percent": val, "series": "repo_rate"})
    if out and anchor is not None:
        out[-1]["repo_rate_percent"] = round(float(anchor), 4)
        out[-1]["anchored_to_live_rbi_repo"] = True
    return out


def synthetic_cpi_series(days: int = 365) -> list[dict[str, Any]]:
    end = date.today()
    out = []
    base = 5.2
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        val = round(base + 0.05 * ((i % 60) / 60), 3)
        out.append({"date": d.isoformat(), "cpi_yoy_percent": val, "series": "cpi_yoy"})
    return out


def get_macro_series(series_id: str, days: int = 365) -> list[dict[str, Any]]:
    sid = series_id.lower().strip()
    if sid in ("repo", "repo_rate", "rbi_repo"):
        return synthetic_repo_series(days)
    if sid in ("cpi", "inflation", "cpi_yoy"):
        return synthetic_cpi_series(days)
    return synthetic_repo_series(days)


def series_methodology_note(series_id: str) -> str:
    sid = series_id.lower().strip()
    if sid in ("cpi", "inflation", "cpi_yoy"):
        return (
            "CPI-style series is illustrative (smooth synthetic path), not official CSO/RBI DBIE releases."
        )
    return (
        "Repo series is illustrative except the last point: aligned to the live RBI policy repo "
        "rate from the homepage scrape when parsing succeeds. For official history use RBI DBIE."
    )
