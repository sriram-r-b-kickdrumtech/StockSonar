from __future__ import annotations

from unittest.mock import patch

import pytest

from stocksonar.upstream import macro as macro_mod
from stocksonar.upstream.macro import (
    build_snapshot_from_rbi_rates,
    get_macro_snapshot,
    parse_percent,
)
from stocksonar.upstream import macro_historical as mh


@pytest.mark.parametrize(
    "text,expected",
    [
        ("6.50%", 6.5),
        ("6.5 %", 6.5),
        ("Policy Repo Rate: 5.25", 5.25),
        (None, None),
        ("", None),
    ],
)
def test_parse_percent(text, expected):
    assert parse_percent(text) == expected


def test_build_snapshot_from_rbi_rates_parses_repo():
    raw = {"Policy Repo Rate": "6.50%", "Marginal Standing Facility Rate": "6.75%"}
    snap = build_snapshot_from_rbi_rates(raw)
    assert snap["repo_rate_percent"] == 6.5
    assert snap["marginal_standing_facility_percent"] == 6.75
    assert "RBI" in snap["source"]
    assert snap["inflation_cpi_percent"] is None


def test_get_macro_snapshot_uses_cache(monkeypatch):
    macro_mod.clear_macro_snapshot_cache()
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return {"Policy Repo Rate": "6.00%"}

    with patch.object(macro_mod, "_fetch_rbi_homepage_rates", fake_fetch):
        a = get_macro_snapshot()
        b = get_macro_snapshot()
    assert calls["n"] == 1
    assert a["repo_rate_percent"] == 6.0
    assert b["repo_rate_percent"] == 6.0
    macro_mod.clear_macro_snapshot_cache()


def test_get_macro_snapshot_degraded_on_fetch_error():
    macro_mod.clear_macro_snapshot_cache()
    with patch.object(
        macro_mod,
        "_fetch_rbi_homepage_rates",
        side_effect=OSError("network"),
    ):
        snap = get_macro_snapshot()
    assert snap.get("degraded") is True
    assert "fetch_error" in snap
    assert snap["repo_rate_percent"] is None
    macro_mod.clear_macro_snapshot_cache()


def test_repo_series_anchors_last_point_when_snapshot_has_repo():
    macro_mod.clear_macro_snapshot_cache()
    with patch.object(
        macro_mod,
        "_fetch_rbi_homepage_rates",
        return_value={"Policy Repo Rate": "6.25%"},
    ):
        series = mh.get_macro_series("repo_rate", days=5)
    assert series[-1]["repo_rate_percent"] == 6.25
    assert series[-1].get("anchored_to_live_rbi_repo") is True
    macro_mod.clear_macro_snapshot_cache()


def test_series_methodology_note():
    assert "DBIE" in mh.series_methodology_note("repo_rate")
    assert "synthetic" in mh.series_methodology_note("cpi").lower() or "illustrative" in mh.series_methodology_note(
        "cpi"
    ).lower()
