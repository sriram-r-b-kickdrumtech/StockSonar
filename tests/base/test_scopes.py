from __future__ import annotations

from stocksonar.auth.scopes import (
    ROLE_TIER_ANALYST,
    ROLE_TIER_FREE,
    ROLE_TIER_PREMIUM,
    scopes_for_realm_roles,
    tier_from_scopes,
)


def test_scopes_for_tier_free():
    s = set(scopes_for_realm_roles([ROLE_TIER_FREE]))
    assert "market:read" in s
    assert "portfolio:write" in s
    assert "watchlist:read" in s
    assert "watchlist:write" in s
    assert "research:generate" not in s
    assert "news:sentiment" not in s


def test_scopes_for_tier_analyst():
    s = set(scopes_for_realm_roles([ROLE_TIER_ANALYST]))
    assert "research:generate" in s
    assert "portfolio:risk" in s


def test_tier_from_scopes():
    assert tier_from_scopes(frozenset(["market:read"])) == "free"
    assert tier_from_scopes(frozenset(["market:read", "fundamentals:read"])) == "premium"
    assert tier_from_scopes(frozenset(["research:generate"])) == "analyst"


def test_premium_roles():
    s = set(scopes_for_realm_roles([ROLE_TIER_PREMIUM]))
    assert "portfolio:risk" in s
    assert "news:sentiment" in s
    assert "research:generate" not in s


def test_tier_from_scopes_news_sentiment_premium():
    assert tier_from_scopes(frozenset(["news:sentiment", "news:read"])) == "premium"
