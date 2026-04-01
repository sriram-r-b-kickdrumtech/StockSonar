#!/usr/bin/env python3
"""Call every MCP tool (and portfolio resources) using a Keycloak bearer token.

Requires: MCP server running (e.g. PYTHONPATH=src python -m stocksonar.server), Keycloak
if you fetch a token here. Uses fastmcp Client + streamable-http.

Environment (optional):
  MCP_ACCESS_TOKEN   If set, skip Keycloak and use this bearer token directly.
  MCP_BASE_URL       Default http://localhost:8000
  STREAMABLE_HTTP_PATH  Default /mcp (appended to base)
  TOKEN_URL, KEYCLOAK_CLIENT_ID, KEYCLOAK_USER, KEYCLOAK_PASSWORD — same as test_client.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import mcp.types as mcp_types
from fastmcp import Client

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import e2e_common  # noqa: E402

# Sample arguments per tool name (empty dict = no params or defaults only).
SAMPLE_TOOL_ARGS: dict[str, dict[str, Any]] = {
    "get_stock_quote": {"ticker": "RELIANCE.NS"},
    "get_price_history": {
        "ticker": "RELIANCE.NS",
        "start": "2024-06-01",
        "end": "2024-12-01",
        "interval": "1d",
        "limit": 30,
    },
    "get_index_data": {"index_name": "NIFTY 50"},
    "refresh_market_overview": {},
    "get_top_gainers_losers": {"exchange": "NSE"},
    "search_mutual_funds": {"query": "axis large cap", "limit": 10},
    "get_fund_nav": {"scheme_code": "120503"},
    "compare_mutual_funds": {"scheme_code_a": "120503", "scheme_code_b": "119551"},
    "get_company_news": {"company_name": "Reliance Industries", "max_results": 3, "limit": 5},
    "get_market_news": {"max_results": 3, "limit": 5},
    "analyze_news_sentiment": {"company_name": "Reliance Industries", "max_results": 5},
    "get_rbi_rates": {},
    "get_inflation_data": {},
    "get_news_sentiment": {"company_name": "Reliance Industries", "max_results": 5},
    "get_financial_statements": {"ticker": "RELIANCE.NS", "quarterly": False},
    "get_shareholding_structure": {"ticker": "RELIANCE.NS"},
    "get_corporate_actions": {"ticker": "RELIANCE.NS"},
    "get_earnings_calendar": {"ticker": "RELIANCE.NS"},
    "get_options_chain": {"ticker": "RELIANCE.NS"},
    "get_technical_indicators": {
        "ticker": "RELIANCE.NS",
        "start": "2024-08-01",
        "end": "2024-12-01",
    },
    "get_macro_snapshot_tool": {},
    "get_macro_historical_series": {"series_id": "repo_rate", "days": 90, "limit": 20},
    "list_company_filings": {"symbol": "RELIANCE.NS", "limit": 5},
    "get_filing_document": {"filing_id": "stub:RELIANCE:2025-01-01:annual"},
    "add_watchlist_symbol": {"symbol": "TCS"},
    "remove_watchlist_symbol": {"symbol": "ZZZ"},
    "list_watchlist": {},
    "cross_reference_signals": {"symbol": "RELIANCE.NS"},
    "add_to_portfolio": {
        "symbol": "RELIANCE",
        "quantity": 2.0,
        "avg_buy_price": 2450.0,
    },
    "remove_from_portfolio": {"symbol": "ZZZNOTHELD"},
    "get_portfolio_summary": {},
    "portfolio_health_check": {},
    "check_concentration_risk": {},
    "check_mf_overlap": {},
    "check_macro_sensitivity": {},
    "detect_sentiment_shift": {},
    "portfolio_risk_report": {},
    "what_if_analysis": {"rbi_rate_change_bps": -25},
}

# Call add_to_portfolio before other tools so portfolio-backed tools have data.
_TOOL_ORDER = {n: i for i, n in enumerate(["add_to_portfolio"])}


def _decode_jwt_sub(token: str) -> str | None:
    return e2e_common.decode_jwt_sub(token)


def _format_tool_result(result: mcp_types.CallToolResult) -> str:
    return e2e_common.format_tool_result(result, max_chars=8000)


def _fetch_token(args: argparse.Namespace) -> str:
    token = (os.environ.get("MCP_ACCESS_TOKEN") or "").strip()
    if token:
        return token
    token_url = args.token_url
    client_id = args.client_id
    username = args.username
    password = args.password
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            token_url,
            data={
                "client_id": client_id,
                "username": username,
                "password": password,
                "grant_type": "password",
            },
        )
    if r.status_code != 200:
        print("Token error:", r.status_code, r.text, file=sys.stderr)
        sys.exit(1)
    body = r.json()
    at = body.get("access_token")
    if not at:
        print("No access_token in response", file=sys.stderr)
        sys.exit(1)
    return str(at)


def _mcp_url(args: argparse.Namespace) -> str:
    base = args.mcp_base.rstrip("/")
    path = args.mcp_path if args.mcp_path.startswith("/") else f"/{args.mcp_path}"
    return f"{base}{path}"


async def _run(args: argparse.Namespace) -> int:
    token = _fetch_token(args)
    url = _mcp_url(args)
    sub = _decode_jwt_sub(token)

    print(f"MCP URL: {url}", file=sys.stderr)
    if sub:
        print(f"Token sub (for resources): {sub[:16]}…", file=sys.stderr)
    print(file=sys.stderr)

    async with Client(url, auth=token, timeout=args.timeout) as client:
        tools = await client.list_tools()
        tools_sorted = sorted(
            tools,
            key=lambda t: (_TOOL_ORDER.get(t.name, 99), t.name),
        )

        for tool in tools_sorted:
            sample = dict(SAMPLE_TOOL_ARGS.get(tool.name, {}))
            print(f"=== tool: {tool.name} ===")
            print("args:", json.dumps(sample, default=str))
            try:
                result = await client.call_tool_mcp(tool.name, sample)
            except Exception as e:
                print("exception:", repr(e))
                print()
                continue
            print(_format_tool_result(result))
            print()

        if args.resources:
            uris = ["market://overview", "macro://snapshot"]
            if sub:
                uris.extend(
                    [
                        f"portfolio://{sub}/holdings",
                        f"portfolio://{sub}/alerts",
                        f"portfolio://{sub}/risk_score",
                        f"watchlist://{sub}/tickers",
                    ]
                )
            for uri in uris:
                print(f"=== resource: {uri} ===")
                try:
                    rr = await client.read_resource_mcp(uri)
                except Exception as e:
                    print("exception:", repr(e))
                    print()
                    continue
                for block in rr.contents:
                    if isinstance(block, mcp_types.TextResourceContents):
                        text = block.text
                        try:
                            print(json.dumps(json.loads(text), indent=2, default=str)[:8000])
                        except json.JSONDecodeError:
                            print(text[:8000])
                    else:
                        print(repr(block))
                print()
            if not sub:
                print(
                    "=== note: portfolio/watchlist URIs skipped (could not parse sub from JWT) ===",
                    file=sys.stderr,
                )

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mcp-base",
        default=os.environ.get("MCP_BASE_URL", "http://localhost:8000"),
    )
    p.add_argument(
        "--mcp-path",
        default=os.environ.get("STREAMABLE_HTTP_PATH", "/mcp"),
    )
    p.add_argument(
        "--token-url",
        default=os.environ.get(
            "TOKEN_URL",
            "http://localhost:8090/realms/stocksonar/protocol/openid-connect/token",
        ),
    )
    p.add_argument("--client-id", default=os.environ.get("KEYCLOAK_CLIENT_ID", "stocksonar-mcp"))
    p.add_argument("--username", default=os.environ.get("KEYCLOAK_USER", "analyst"))
    p.add_argument("--password", default=os.environ.get("KEYCLOAK_PASSWORD", "analystpass"))
    p.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("MCP_CLIENT_TIMEOUT", "120")),
        help="Per-request timeout seconds (default 120).",
    )
    p.add_argument(
        "--no-resources",
        action="store_true",
        help="Do not read portfolio://… resources after tools.",
    )
    p.add_argument(
        "--log-file",
        default="",
        help="Mirror stdout/stderr to this file (default: logs/stocksonar_all_tools_<timestamp>.log if set via --save-log)",
    )
    p.add_argument(
        "--save-log",
        action="store_true",
        help="Write to logs/stocksonar_all_tools_<UTC timestamp>.log automatically",
    )
    args = p.parse_args()
    args.resources = not args.no_resources

    repo = Path(__file__).resolve().parent.parent
    log_path: Path | None = None
    if args.log_file:
        log_path = Path(args.log_file).resolve()
    elif args.save_log:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = (repo / "logs" / f"stocksonar_all_tools_{ts}.log").resolve()

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Logging to: {log_path}", file=sys.stderr)
        with e2e_common.tee_stdout_stderr(log_path):
            return asyncio.run(_run(args))
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
