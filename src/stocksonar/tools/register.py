"""Register all MCP tools, resources, and PS2 prompts."""

from __future__ import annotations

from stocksonar.tools.cross_source import register_cross_source_tools
from stocksonar.tools.prompts_ps2 import register_ps2_prompts
from stocksonar.tools.filings_tools import register_filings_tools
from stocksonar.tools.fundamentals_tools import register_fundamentals_tools
from stocksonar.tools.macro_tools import register_macro_tools
from stocksonar.tools.market import register_market_tools
from stocksonar.tools.mutual_funds import register_mf_tools
from stocksonar.tools.news_tools import register_news_tools
from stocksonar.tools.portfolio import register_portfolio_tools
from stocksonar.tools.resources_market_macro import register_market_macro_resources
from stocksonar.tools.resources_portfolio import register_portfolio_resources
from stocksonar.tools.resources_watchlist import register_watchlist_resources
from stocksonar.tools.risk import register_risk_tools
from stocksonar.tools.technicals_tools import register_technicals_tools
from stocksonar.tools.watchlist_tools import register_watchlist_tools
from stocksonar.tools.aliases_ps2 import register_ps2_alias_tools


def register_all_tools(mcp) -> None:
    register_market_tools(mcp)
    register_fundamentals_tools(mcp)
    register_technicals_tools(mcp)
    register_mf_tools(mcp)
    register_news_tools(mcp)
    register_macro_tools(mcp)
    register_filings_tools(mcp)
    register_portfolio_tools(mcp)
    register_watchlist_tools(mcp)
    register_risk_tools(mcp)
    register_cross_source_tools(mcp)
    register_portfolio_resources(mcp)
    register_market_macro_resources(mcp)
    register_watchlist_resources(mcp)
    register_ps2_alias_tools(mcp)
    register_ps2_prompts(mcp)
