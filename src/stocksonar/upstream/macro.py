"""Macro snapshot: RBI policy rates from the official homepage (jugaad-data scraper)."""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

_REPO_KEYS = (
    "Policy Repo Rate",
    "policy repo rate",
    "Repo Rate",
    "Policy Repo rate",
)
_MSF_KEYS = (
    "Marginal Standing Facility Rate",
    "Marginal Standing Facility",
)
_SDF_KEYS = (
    "Standing Deposit Facility Rate",
    "Standing Deposit Facility",
)


def parse_percent(text: str | None) -> float | None:
    """Extract a percentage number from RBI-style cell text (e.g. '6.50%', '6.5 %')."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)+|\d+)", s)
    if m:
        return float(m.group(1))
    return None


def _pick_rate(raw: dict[str, str], keys: tuple[str, ...]) -> tuple[float | None, str | None]:
    for k in keys:
        if k in raw:
            v = raw.get(k)
            p = parse_percent(v) if v else None
            return p, str(v).strip() if v else None
    lk = {a.lower(): (a, b) for a, b in raw.items()}
    for k in keys:
        pair = lk.get(k.lower())
        if pair:
            _ak, v = pair
            p = parse_percent(v) if v else None
            return p, str(v).strip() if v else None
    return None, None


def _normalize_rates_table(rates: dict[str, str]) -> dict[str, Any]:
    repo, repo_raw = _pick_rate(rates, _REPO_KEYS)
    msf, msf_raw = _pick_rate(rates, _MSF_KEYS)
    sdf, sdf_raw = _pick_rate(rates, _SDF_KEYS)
    return {
        "repo_rate_percent": repo,
        "marginal_standing_facility_percent": msf,
        "standing_deposit_facility_percent": sdf,
        "repo_rate_raw": repo_raw,
        "msf_raw": msf_raw,
        "sdf_raw": sdf_raw,
    }


def _fetch_rbi_homepage_rates() -> dict[str, str]:
    from jugaad_data.rbi import RBI

    return dict(RBI().current_rates())


def build_snapshot_from_rbi_rates(
    rates: dict[str, str], *, degraded: bool = False, error: str | None = None
) -> dict[str, Any]:
    norm = _normalize_rates_table(rates)
    as_of = datetime.now(timezone.utc).isoformat()
    out: dict[str, Any] = {
        "source": "RBI (https://www.rbi.org.in/) policy rate tables (scraped via jugaad-data)",
        "as_of": as_of,
        "inflation_cpi_percent": None,
        "rbi_rates_count": len(rates),
        "rbi_rates_sample": dict(list(rates.items())[:12]),
        **norm,
    }
    if norm["repo_rate_percent"] is None:
        out["note"] = (
            "Policy repo rate not parsed from RBI homepage tables; see rbi_rates_sample for raw keys. "
            "CPI is not on this page — use macro:historical / DBIE for inflation series."
        )
    else:
        out["note"] = (
            "Policy rates from RBI homepage. CPI/WPI headline figures are not scraped here; "
            "use RBI DBIE or data.gov.in for full inflation time series."
        )
    if degraded:
        out["degraded"] = True
    if error:
        out["fetch_error"] = error
    return out


_lock = threading.Lock()
_cache_time: float = 0.0
_cache_payload: dict[str, Any] | None = None


def clear_macro_snapshot_cache() -> None:
    """Clear process-local snapshot cache (for tests)."""
    global _cache_time, _cache_payload
    with _lock:
        _cache_time = 0.0
        _cache_payload = None


def get_macro_snapshot() -> dict[str, Any]:
    """Latest macro snapshot with short process-local TTL (see Settings.ttl_macro_snapshot)."""
    global _cache_time, _cache_payload
    from stocksonar.config import get_settings

    ttl = max(60, int(get_settings().ttl_macro_snapshot))
    now = time.time()
    with _lock:
        if _cache_payload is not None and (now - _cache_time) < ttl:
            return dict(_cache_payload)

    try:
        rates = _fetch_rbi_homepage_rates()
        payload = build_snapshot_from_rbi_rates(rates)
    except Exception as e:  # noqa: BLE001 — upstream HTML/network varies
        return {
            "source": "StockSonar (degraded — RBI fetch failed)",
            "as_of": datetime.now(timezone.utc).isoformat(),
            "repo_rate_percent": None,
            "inflation_cpi_percent": None,
            "marginal_standing_facility_percent": None,
            "standing_deposit_facility_percent": None,
            "note": "Could not load RBI homepage rates; check network or RBI page layout.",
            "degraded": True,
            "fetch_error": str(e),
            "rbi_rates_count": 0,
            "rbi_rates_sample": {},
        }

    with _lock:
        _cache_time = now
        _cache_payload = dict(payload)
    return dict(payload)
