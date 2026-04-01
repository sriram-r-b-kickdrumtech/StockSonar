#!/usr/bin/env python3
"""Probe Keycloak + StockSonar MCP /health (for demos and CI smoke).

Exit 0 if all probes pass, 1 otherwise. Use with judge demo or before call_all_mcp_tools.

Environment (optional):
  STOCKSONAR_KEYCLOAK_BASE  default http://localhost:8090
  STOCKSONAR_MCP_BASE       default http://localhost:8000
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def probe(
    keycloak_base: str,
    mcp_base: str,
    *,
    timeout: float,
    retries: int,
    pause: float,
) -> tuple[bool, list[str]]:
    kc = keycloak_base.rstrip("/")
    mb = mcp_base.rstrip("/")
    openid = f"{kc}/realms/stocksonar/.well-known/openid-configuration"
    health = f"{mb}/health"
    log: list[str] = []

    for attempt in range(1, retries + 1):
        log.append(f"--- attempt {attempt}/{retries} ---")
        try:
            r1 = httpx.get(openid, timeout=timeout, follow_redirects=True)
            r1.raise_for_status()
            body = r1.json()
            if not isinstance(body, dict) or "issuer" not in body:
                raise ValueError("openid-configuration missing issuer")
            log.append(f"OK Keycloak OIDC: {openid}")

            r2 = httpx.get(health, timeout=timeout, follow_redirects=True)
            r2.raise_for_status()
            log.append(f"OK MCP health: {health} -> {r2.json()}")
            return True, log
        except Exception as e:
            log.append(f"FAIL: {e!r}")
            if attempt < retries:
                time.sleep(pause)

    return False, log


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--keycloak-base",
        default=os.environ.get("STOCKSONAR_KEYCLOAK_BASE", "http://localhost:8090"),
    )
    p.add_argument(
        "--mcp-base",
        default=os.environ.get("STOCKSONAR_MCP_BASE", "http://localhost:8000"),
    )
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--retries", type=int, default=5)
    p.add_argument("--pause", type=float, default=2.0)
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Only print final PASS/FAIL line",
    )
    args = p.parse_args()

    ok, lines = probe(
        args.keycloak_base,
        args.mcp_base,
        timeout=args.timeout,
        retries=args.retries,
        pause=args.pause,
    )
    if not args.quiet:
        for line in lines:
            print(line)
    print("PASS" if ok else "FAIL", file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
