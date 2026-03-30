"""PS2 MCP prompts (AI League base layer): morning_risk_brief, rebalance_suggestions, earnings_exposure."""

from __future__ import annotations

from fastmcp.server.auth import require_scopes
from fastmcp.prompts import PromptResult


def register_ps2_prompts(mcp) -> None:
    """Register tier-gated prompts per PS2 addendum (Premium+ for first two; earnings needs fundamentals)."""

    @mcp.prompt(
        name="morning_risk_brief",
        description=(
            "Daily portfolio risk brief: value, overnight-style news for holdings, macro, optional health flags."
        ),
        auth=require_scopes("portfolio:read", "news:read", "macro:read"),
    )
    def morning_risk_brief() -> PromptResult:
        body = """You are preparing a concise **morning risk brief** for the authenticated user (Indian equities, PS2).

Do **not** invent prices or headlines. Use StockSonar MCP tools and cite each response's `source` / `data` fields.

Suggested order:
1. `get_portfolio_summary` — total value, P&L, allocation.
2. For each holding (or the top 3 by weight), call `get_company_news` with a small `max_results` for recent headlines.
3. `get_macro_snapshot_tool` — policy rates / macro note from RBI homepage scrape.
4. If the user's token includes `portfolio:risk`, optionally add `portfolio_health_check` or `check_concentration_risk`.

Output: short sections — **Portfolio**, **Headlines by ticker**, **Macro**, **Risk flags** (if any). End with the tool disclaimer; this is not financial advice."""
        return PromptResult(body)

    @mcp.prompt(
        name="rebalance_suggestions",
        description=(
            "Structured prompt to turn concentration/sector risk flags into illustrative trim/tilt ideas (not orders)."
        ),
        auth=require_scopes("portfolio:risk"),
    )
    def rebalance_suggestions(
        focus_sector: str | None = None,
    ) -> PromptResult:
        sec = focus_sector or "any overweight sector from risk tools"
        body = f"""You help the user think about **rebalancing** to reduce concentration or sector tilt (PS2).

Use tools; do not fabricate metrics.

1. Run `portfolio_health_check` and `check_concentration_risk`. Summarise flags.
2. Optionally `check_mf_overlap` for unintended duplicate exposure.
3. If relevant, `check_macro_sensitivity` for rate/forex-sensitive names.

Focus sector hint from user argument: **{sec}**.

Output: bullet **observations** (data-backed) then **illustrative** trim/tilt ideas (e.g. reduce single-name above 20%, sector above 40%) — clearly **not** trade instructions or advice. Cite tool sources."""
        return PromptResult(body)

    @mcp.prompt(
        name="earnings_exposure",
        description=(
            "Map portfolio holdings to upcoming earnings-style dates via fundamentals tools; describe timing risk."
        ),
        auth=require_scopes("portfolio:read", "fundamentals:read"),
    )
    def earnings_exposure() -> PromptResult:
        body = """You assess **earnings-season exposure** for the user's current portfolio (PS2).

1. `get_portfolio_summary` or read `portfolio://…/holdings` if available to list tickers (use `.NS` / `.BO` as your tools expect).
2. For each distinct equity symbol, call `get_earnings_calendar` (or the closest available earnings tool) to see near-term result dates.
3. Optionally add `get_company_news` for names with imminent dates.

Output: table-style bullets — **Symbol**, **Next event window** (from tool data only), **Risk note** (volatility/expectations, grounded in headlines if you fetched news). State when a ticker has **no** calendar row. Not financial advice; cite `source` fields."""
        return PromptResult(body)
