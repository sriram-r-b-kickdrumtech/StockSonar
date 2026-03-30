"""OAuth-style scopes and Keycloak realm role → scope expansion."""

from __future__ import annotations

# Keycloak realm roles (assign one per user)
ROLE_TIER_FREE = "tier-free"
ROLE_TIER_PREMIUM = "tier-premium"
ROLE_TIER_ANALYST = "tier-analyst"

FREE_SCOPES = frozenset(
    {
        "market:read",
        "mf:read",
        "news:read",
        "portfolio:read",
        "portfolio:write",
        "watchlist:read",
        "watchlist:write",
    }
)

PREMIUM_EXTRA = frozenset(
    {
        "fundamentals:read",
        "technicals:read",
        "macro:read",
        "portfolio:risk",
        "news:sentiment",
    }
)

ANALYST_EXTRA = frozenset(
    {
        "filings:read",
        "filings:deep",
        "macro:historical",
        "research:generate",
    }
)

ALL_SCOPES = FREE_SCOPES | PREMIUM_EXTRA | ANALYST_EXTRA

ROLE_TO_SCOPES: dict[str, frozenset[str]] = {
    ROLE_TIER_FREE: FREE_SCOPES,
    ROLE_TIER_PREMIUM: FREE_SCOPES | PREMIUM_EXTRA,
    ROLE_TIER_ANALYST: FREE_SCOPES | PREMIUM_EXTRA | ANALYST_EXTRA,
}


def scopes_for_realm_roles(roles: list[str]) -> list[str]:
    """Union scopes granted by any assigned realm roles."""
    out: set[str] = set()
    for role in roles:
        out |= set(ROLE_TO_SCOPES.get(role, frozenset()))
    return sorted(out)


def tier_from_scopes(scopes: frozenset[str]) -> str:
    """Infer rate-limit tier from effective scopes (most privileged wins)."""
    if "research:generate" in scopes:
        return "analyst"
    if (
        "portfolio:risk" in scopes
        or "fundamentals:read" in scopes
        or "technicals:read" in scopes
        or "news:sentiment" in scopes
        or "macro:read" in scopes
    ):
        return "premium"
    return "free"
