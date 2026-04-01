#!/usr/bin/env python3
"""Judge-ready E2E demo: stack check, OAuth tier boundaries, PS2 story, resources, prompts.

Logs to ``logs/stocksonar_judge_demo_<timestamp>.log`` by default (tee to console).

Prerequisite: ``docker compose up -d``

CLI examples::

    python scripts/run_judge_demo.py
    python scripts/run_judge_demo.py --log-file logs/my_demo.log

Environment matches ``call_all_mcp_tools.py`` (e.g. KEYCLOAK_USER, KEYCLOAK_PASSWORD).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import httpx
from fastmcp import Client
from mcp.types import TextResourceContents

import e2e_common as _e2e

decode_jwt_sub = _e2e.decode_jwt_sub
env_or = _e2e.env_or
fetch_password_token = _e2e.fetch_password_token
format_tool_result = _e2e.format_tool_result
mcp_url_from_parts = _e2e.mcp_url_from_parts
tee_stdout_stderr = _e2e.tee_stdout_stderr


def _log(msg: str = "") -> None:
    print(msg, flush=True)


async def _call_tool(client: Client, name: str, args: dict) -> tuple[bool, str]:
    try:
        result = await client.call_tool_mcp(name, args)
    except Exception as e:
        return False, f"EXCEPTION: {e!r}"
    body = format_tool_result(result)
    if result.isError:
        return False, f"TOOL_ERROR:\n{body}"
    return True, body


async def run_stack_quick_check(mcp_base: str, keycloak_base: str) -> bool:
    _log("### Stack quick check (HTTP)")
    try:
        r = httpx.get(
            f"{keycloak_base.rstrip('/')}/realms/stocksonar/.well-known/openid-configuration",
            timeout=15.0,
            follow_redirects=True,
        )
        r.raise_for_status()
        _log(f"Keycloak OIDC OK ({r.status_code})")
        h = httpx.get(f"{mcp_base.rstrip('/')}/health", timeout=15.0, follow_redirects=True)
        h.raise_for_status()
        _log(f"MCP /health OK: {h.json()}")
        return True
    except Exception as e:
        _log(f"Stack check FAILED: {e!r}")
        return False


async def run_tier_boundaries(
    url: str,
    token_url: str,
    client_id: str,
) -> None:
    _log("\n### Tier / auth boundaries (password grant)")
    matrix = [
        ("free", "free", "freepass", "get_portfolio_summary", {}),
        ("free", "free", "freepass", "portfolio_health_check", {}),
        ("free", "free", "freepass", "portfolio_risk_report", {}),
        ("premium", "premium", "premiumpass", "portfolio_health_check", {}),
        ("premium", "premium", "premiumpass", "portfolio_risk_report", {}),
        ("premium", "premium", "premiumpass", "what_if_analysis", {"rbi_rate_change_bps": -25}),
        ("analyst", "analyst", "analystpass", "portfolio_risk_report", {}),
        ("analyst", "analyst", "analystpass", "what_if_analysis", {"rbi_rate_change_bps": -25}),
    ]
    for label, user, pw, tool, args in matrix:
        try:
            tok = fetch_password_token(
                token_url=token_url,
                client_id=client_id,
                username=user,
                password=pw,
            )
        except Exception as e:
            _log(f"[{label}] token failed ({user}): {e}")
            continue
        async with Client(url, auth=tok, timeout=120.0) as client:
            ok, msg = await _call_tool(client, tool, args)
            status = "ALLOW" if ok else "DENY/FAIL"
            _log(f"[{label}] {user} -> {tool} => {status}")
            if len(msg) > 1500:
                _log(msg[:1500] + "\n… [truncated for log]\n")
            else:
                _log(msg)
            _log("-" * 60)


async def run_ps2_analyst_story(
    url: str,
    token_url: str,
    client_id: str,
    username: str,
    password: str,
) -> None:
    _log("\n### PS2 analyst scenario (sequential tools + resources)")
    tok = fetch_password_token(
        token_url=token_url,
        client_id=client_id,
        username=username,
        password=password,
    )
    sub = decode_jwt_sub(tok)
    _log(f"Token sub: {sub!r}")

    async with Client(url, auth=tok, timeout=180.0) as client:
        steps: list[tuple[str, dict]] = [
            ("remove_from_portfolio", {"symbol": "TCS"}),
            ("remove_from_portfolio", {"symbol": "RELIANCE"}),
            ("remove_from_portfolio", {"symbol": "HDFCBANK"}),
            ("add_to_portfolio", {"symbol": "TCS", "quantity": 40.0, "avg_buy_price": 3500.0}),
            ("add_to_portfolio", {"symbol": "INFY", "quantity": 30.0, "avg_buy_price": 1450.0}),
            ("add_to_portfolio", {"symbol": "RELIANCE", "quantity": 5.0, "avg_buy_price": 2800.0}),
            ("get_portfolio_summary", {}),
            ("portfolio_health_check", {}),
            ("check_concentration_risk", {}),
            ("check_mf_overlap", {}),
            ("check_macro_sensitivity", {}),
            ("get_rbi_rates", {}),
            ("get_macro_snapshot_tool", {}),
            ("detect_sentiment_shift", {}),
            ("portfolio_risk_report", {}),
            ("what_if_analysis", {"rbi_rate_change_bps": -25}),
            ("refresh_market_overview", {}),
        ]
        for tool, args in steps:
            ok, msg = await _call_tool(client, tool, args)
            _log(f"\n>>> {tool}({args}) -> {'OK' if ok else 'FAIL'}")
            _log(msg[:8000] + ("\n…" if len(msg) > 8000 else ""))

        _log("\n### MCP resources")
        uris = ["market://overview", "macro://snapshot"]
        if sub:
            uris += [
                f"portfolio://{sub}/holdings",
                f"portfolio://{sub}/alerts",
                f"portfolio://{sub}/risk_score",
            ]
        for uri in uris:
            _log(f"\n>>> read_resource {uri}")
            try:
                rr = await client.read_resource_mcp(uri)
            except Exception as e:
                _log(f"EXCEPTION: {e!r}")
                continue
            for block in rr.contents:
                if isinstance(block, TextResourceContents):
                    t = block.text
                    _log(t[:6000] + ("…" if len(t) > 6000 else ""))
                else:
                    _log(repr(block))

        _log("\n### PS2 prompts (names only)")
        try:
            prompts = await client.list_prompts()
            for p in sorted(prompts, key=lambda x: x.name):
                _log(f"  - {p.name}")
        except Exception as e:
            _log(f"list_prompts failed: {e!r}")


async def async_main(args: argparse.Namespace) -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _log(f"StockSonar judge demo started UTC {started}")
    _log(f"MCP URL: {args.mcp_url}")

    if not args.skip_stack_check:
        if not await run_stack_quick_check(args.mcp_base, args.keycloak_base):
            _log("Aborting — fix docker compose / wait for Keycloak + MCP.")
            return 1

    if not args.skip_tiers:
        await run_tier_boundaries(
            args.mcp_url,
            args.token_url,
            args.client_id,
        )

    await run_ps2_analyst_story(
        args.mcp_url,
        args.token_url,
        args.client_id,
        args.analyst_user,
        args.analyst_password,
    )

    _log("\n### Done")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--log-file",
        default="",
        help="Write console copy to this file. Default: logs/stocksonar_judge_demo_<timestamp>.log",
    )
    p.add_argument("--no-log-file", action="store_true", help="Console only")
    p.add_argument("--mcp-base", default=env_or("MCP_BASE_URL", "http://localhost:8000"))
    p.add_argument("--mcp-path", default=env_or("STREAMABLE_HTTP_PATH", "/mcp"))
    p.add_argument(
        "--keycloak-base",
        default=env_or("STOCKSONAR_KEYCLOAK_BASE", "http://localhost:8090"),
    )
    p.add_argument(
        "--token-url",
        default=env_or(
            "TOKEN_URL",
            "http://localhost:8090/realms/stocksonar/protocol/openid-connect/token",
        ),
    )
    p.add_argument("--client-id", default=env_or("KEYCLOAK_CLIENT_ID", "stocksonar-mcp"))
    p.add_argument(
        "--analyst-user",
        default=env_or("KEYCLOAK_USER", "analyst"),
    )
    p.add_argument(
        "--analyst-password",
        default=env_or("KEYCLOAK_PASSWORD", "analystpass"),
    )
    p.add_argument("--skip-stack-check", action="store_true")
    p.add_argument("--skip-tiers", action="store_true", help="Only run analyst PS2 story")
    args = p.parse_args()
    args.mcp_url = mcp_url_from_parts(args.mcp_base, args.mcp_path)

    if args.no_log_file:
        return asyncio.run(async_main(args))

    log_path = Path(args.log_file) if args.log_file else None
    if log_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = REPO_ROOT / "logs" / f"stocksonar_judge_demo_{ts}.log"

    log_path = log_path.resolve()
    print(f"Logging to: {log_path}", file=sys.stderr)
    with tee_stdout_stderr(log_path):
        return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
