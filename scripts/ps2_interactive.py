#!/usr/bin/env python3
"""Interactive PS2 MCP shell: menu-driven tools + resources, full JSON visibility.

Requires Docker stack: Keycloak + MCP + Redis (``docker compose up -d``).

Example::

    python scripts/ps2_interactive.py
    python scripts/ps2_interactive.py --log-file logs/ps2_session.log
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import mcp.types as mcp_types
from fastmcp import Client
from mcp.types import TextResourceContents

import e2e_common

# Keycloak demo users — see keycloak/stocksonar-realm.json
KNOWN_USERS: dict[str, str] = {
    "free": "freepass",
    "premium": "premiumpass",
    "analyst": "analystpass",
}


@dataclass
class Config:
    mcp_url: str
    token_url: str
    client_id: str
    username: str
    password: str
    timeout: float


async def _ainput(prompt: str = "") -> str:
    """Async-safe stdin read — avoids input() which breaks in Python 3.14 executor threads."""
    loop = asyncio.get_event_loop()

    def _read() -> str:
        if prompt:
            sys.stdout.write(prompt)
            sys.stdout.flush()
        line = sys.stdin.readline()
        return line.rstrip("\n")

    return await loop.run_in_executor(None, _read)


async def _aprompt_float(
    label: str, default: float | None = None, positive_only: bool = False
) -> float:
    hint = f" [{default}]" if default is not None else ""
    while True:
        s = (await _ainput(f"{label}{hint}: ")).strip()
        if not s and default is not None:
            v = float(default)
        else:
            try:
                v = float(s)
            except ValueError:
                print("  Please enter a number.")
                continue
        if positive_only and v <= 0:
            print("  Must be greater than 0.")
            continue
        return v


async def _aprompt_str(label: str, default: str = "") -> str:
    s = (await _ainput(f"{label}" + (f" [{default}]" if default else "") + ": ")).strip()
    return s if s else default


def _tier(username: str) -> str:
    if username in ("analyst",):
        return "analyst"
    if username in ("premium",):
        return "premium"
    return "free"


def _print_menu(cfg: Config, sub: str | None) -> None:
    tier = _tier(cfg.username)
    analyst = tier == "analyst"
    premium = tier in ("premium", "analyst")
    print()
    print("=" * 60)
    print(f"StockSonar PS2  |  user={cfg.username} [{tier}]  sub={sub or '?'}")
    print("=" * 60)
    print(" 1) Switch user (free / premium / analyst) — new MCP session")
    print("--- Portfolio (all tiers) ---")
    print(" 2) add_to_portfolio  (add one or many stocks)")
    print(" 3) remove_from_portfolio")
    print(" 4) get_portfolio_summary")
    if premium:
        print("--- PS2 risk [premium+] ---")
    else:
        print("--- PS2 risk [NEED premium — switch user first] ---")
    print(" 5) portfolio_health_check")
    print(" 6) check_concentration_risk")
    print(" 7) check_mf_overlap")
    print(" 8) check_macro_sensitivity")
    print(" 9) detect_sentiment_shift")
    if analyst:
        print("--- Cross-source [analyst] ---")
    else:
        print("--- Cross-source [NEED analyst — switch to analyst first] ---")
    print("10) portfolio_risk_report")
    print("11) what_if_analysis")
    print("--- Resources ---")
    print("12) read market://overview       [premium+]")
    print("13) read macro://snapshot        [premium+]")
    print("14) read portfolio://…/holdings  [premium+]")
    print("15) read portfolio://…/alerts    [premium+]")
    print("16) read portfolio://…/risk_score[premium+]")
    print("--- Utilities ---")
    print("17) refresh_market_overview")
    print("18) list_tools (names)")
    print("19) list_prompts (names)")
    print(" 0) Quit")
    print("=" * 60)


def _format_tool_body(result: mcp_types.CallToolResult) -> str:
    return e2e_common.format_tool_result(result, max_chars=500_000)


def _format_resource(rr: Any) -> str:
    parts: list[str] = []
    for block in rr.contents:
        if isinstance(block, TextResourceContents):
            t = block.text
            try:
                parts.append(json.dumps(json.loads(t), indent=2, default=str))
            except json.JSONDecodeError:
                parts.append(t)
        else:
            parts.append(repr(block))
    return "\n".join(parts) if parts else "(empty)"


async def _call_tool(client: Client, name: str, args: dict) -> None:
    t0 = time.perf_counter()
    try:
        result = await client.call_tool_mcp(name, args)
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        print(f"\n[EXCEPTION after {dt:.1f} ms] {e!r}")
        traceback.print_exc()
        return
    dt = (time.perf_counter() - t0) * 1000
    flag = "ERROR" if result.isError else "OK"
    print(f"\n--- {name} -> {flag} ({dt:.1f} ms) ---")
    print(_format_tool_body(result))


async def _read_resource(client: Client, uri: str) -> None:
    t0 = time.perf_counter()
    try:
        rr = await client.read_resource_mcp(uri)
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        print(f"\n[EXCEPTION after {dt:.1f} ms] {e!r}")
        traceback.print_exc()
        return
    dt = (time.perf_counter() - t0) * 1000
    print(f"\n--- resource {uri} ({dt:.1f} ms) ---")
    print(_format_resource(rr))


async def _list_tools(client: Client) -> None:
    t0 = time.perf_counter()
    tools = await client.list_tools()
    dt = (time.perf_counter() - t0) * 1000
    names = sorted(t.name for t in tools)
    print(f"\n--- list_tools ({dt:.1f} ms) — {len(names)} tools ---")
    for n in names:
        print(f"  {n}")


async def _list_prompts(client: Client) -> None:
    t0 = time.perf_counter()
    prompts = await client.list_prompts()
    dt = (time.perf_counter() - t0) * 1000
    names = sorted(p.name for p in prompts)
    print(f"\n--- list_prompts ({dt:.1f} ms) — {len(names)} prompts ---")
    for n in names:
        print(f"  {n}")


async def menu_loop(client: Client, cfg: Config, token: str) -> str | None:
    """Return new access token to reconnect, or None to exit program."""
    while True:
        sub = e2e_common.decode_jwt_sub(token)
        _print_menu(cfg, sub)
        raw = (await _ainput("ps2> ")).strip()
        if not raw:
            continue
        choice = raw.lower()
        if choice in ("0", "q", "quit", "exit"):
            print("Goodbye.")
            return None

        if choice == "1":
            u = (await _aprompt_str("Tier username", "analyst")).lower()
            if u not in KNOWN_USERS:
                print("Unknown user. Use: free | premium | analyst")
                continue
            try:
                new_t = e2e_common.fetch_password_token(
                    token_url=cfg.token_url,
                    client_id=cfg.client_id,
                    username=u,
                    password=KNOWN_USERS[u],
                )
            except Exception as e:
                print(f"Token fetch failed: {e!r}")
                traceback.print_exc()
                continue
            print(f"Switched to {u}; reconnecting MCP session…")
            cfg.username = u
            cfg.password = KNOWN_USERS[u]
            return new_t

        if choice == "2":
            # Loop: add as many stocks as needed, blank symbol = done
            print("Add stocks — leave symbol blank and press Enter when done.")
            added = 0
            while True:
                raw_sym = (await _ainput("  Symbol (blank=done): ")).strip().upper()
                raw_sym = raw_sym.replace(".NS", "").replace(".BO", "")
                if not raw_sym:
                    break
                qty = await _aprompt_float(f"  Quantity for {raw_sym}", positive_only=True)
                avg = await _aprompt_float(f"  Avg buy price for {raw_sym}", positive_only=True)
                await _call_tool(
                    client,
                    "add_to_portfolio",
                    {"symbol": raw_sym, "quantity": qty, "avg_buy_price": avg},
                )
                added += 1
            if added:
                print(f"\n  {added} holding(s) added. Run option 4 to review.")
        elif choice == "3":
            print("Remove stocks — leave symbol blank and press Enter when done.")
            while True:
                raw_sym = (await _ainput("  Symbol to remove (blank=done): ")).strip().upper()
                raw_sym = raw_sym.replace(".NS", "").replace(".BO", "")
                if not raw_sym:
                    break
                await _call_tool(client, "remove_from_portfolio", {"symbol": raw_sym})
        elif choice == "4":
            await _call_tool(client, "get_portfolio_summary", {})
        elif choice == "5":
            if _tier(cfg.username) not in ("premium", "analyst"):
                print("  ⚠  portfolio_health_check requires Premium or Analyst tier. Use option 1 to switch.")
            else:
                await _call_tool(client, "portfolio_health_check", {})
        elif choice == "6":
            if _tier(cfg.username) not in ("premium", "analyst"):
                print("  Requires Premium or Analyst tier (option 1 to switch).")
            else:
                await _call_tool(client, "check_concentration_risk", {})
        elif choice == "7":
            if _tier(cfg.username) not in ("premium", "analyst"):
                print("  Requires Premium or Analyst tier (option 1 to switch).")
            else:
                await _call_tool(client, "check_mf_overlap", {})
        elif choice == "8":
            if _tier(cfg.username) not in ("premium", "analyst"):
                print("  Requires Premium or Analyst tier (option 1 to switch).")
            else:
                await _call_tool(client, "check_macro_sensitivity", {})
        elif choice == "9":
            if _tier(cfg.username) not in ("premium", "analyst"):
                print("  Requires Premium or Analyst tier (option 1 to switch).")
            else:
                await _call_tool(client, "detect_sentiment_shift", {})
        elif choice == "10":
            if _tier(cfg.username) != "analyst":
                print("  portfolio_risk_report requires Analyst tier. Use option 1 to switch to 'analyst'.")
            else:
                await _call_tool(client, "portfolio_risk_report", {})
        elif choice == "11":
            if _tier(cfg.username) != "analyst":
                print("  what_if_analysis requires Analyst tier. Use option 1 to switch to 'analyst'.")
            else:
                bps = int(await _aprompt_float("RBI rate change (basis points, e.g. -25)", -25))
                await _call_tool(client, "what_if_analysis", {"rbi_rate_change_bps": bps})
        elif choice == "12":
            await _read_resource(client, "market://overview")
        elif choice == "13":
            await _read_resource(client, "macro://snapshot")
        elif choice in ("14", "15", "16"):
            if not sub:
                print("Cannot resolve portfolio URI: JWT has no sub.")
                continue
            path = {"14": "holdings", "15": "alerts", "16": "risk_score"}[choice]
            await _read_resource(client, f"portfolio://{sub}/{path}")
        elif choice == "17":
            await _call_tool(client, "refresh_market_overview", {})
        elif choice == "18":
            await _list_tools(client)
        elif choice == "19":
            await _list_prompts(client)
        else:
            print("Unknown choice. Enter a number from the menu.")


async def async_main(cfg: Config) -> None:
    try:
        token = e2e_common.fetch_password_token(
            token_url=cfg.token_url,
            client_id=cfg.client_id,
            username=cfg.username,
            password=cfg.password,
        )
    except Exception as e:
        print(f"Initial token failed: {e!r}")
        traceback.print_exc()
        raise SystemExit(1) from e

    while token is not None:
        print(f"\nConnecting MCP: {cfg.mcp_url}")
        async with Client(cfg.mcp_url, auth=token, timeout=cfg.timeout) as client:
            nxt = await menu_loop(client, cfg, token)
        if nxt is None:
            break
        token = nxt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mcp-base", default=e2e_common.env_or("MCP_BASE_URL", "http://localhost:8000"))
    p.add_argument("--mcp-path", default=e2e_common.env_or("STREAMABLE_HTTP_PATH", "/mcp"))
    p.add_argument(
        "--token-url",
        default=e2e_common.env_or(
            "TOKEN_URL",
            "http://localhost:8090/realms/stocksonar/protocol/openid-connect/token",
        ),
    )
    p.add_argument("--client-id", default=e2e_common.env_or("KEYCLOAK_CLIENT_ID", "stocksonar-mcp"))
    p.add_argument("--username", default=e2e_common.env_or("KEYCLOAK_USER", "analyst"))
    p.add_argument("--password", default=e2e_common.env_or("KEYCLOAK_PASSWORD", ""))
    p.add_argument("--timeout", type=float, default=float(e2e_common.env_or("MCP_CLIENT_TIMEOUT", "180")))
    p.add_argument("--log-file", default="", help="Mirror stdout/stderr to this file (tee)")
    args = p.parse_args()

    pwd = (args.password or "").strip()
    uname = args.username.strip().lower()
    if not pwd and uname in KNOWN_USERS:
        pwd = KNOWN_USERS[uname]
    if not pwd:
        print(
            "Set KEYCLOAK_PASSWORD in the environment or pass --username free|premium|analyst (known passwords).",
            file=sys.stderr,
        )
        return 1

    cfg = Config(
        mcp_url=e2e_common.mcp_url_from_parts(args.mcp_base, args.mcp_path),
        token_url=args.token_url,
        client_id=args.client_id,
        username=uname,
        password=pwd,
        timeout=args.timeout,
    )

    if args.log_file:
        log_path = Path(args.log_file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Logging session to: {log_path}", file=sys.stderr)
        with e2e_common.tee_stdout_stderr(log_path):
            asyncio.run(async_main(cfg))
    else:
        asyncio.run(async_main(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
