#!/usr/bin/env python3
"""Smoke test: optional Keycloak token + MCP /health.

Connection refused on the Keycloak port (default 8090) means Keycloak is not running. You can either:
  - Start the stack:  docker compose up -d keycloak redis
  - Skip tokens:     python scripts/test_client.py --health-only
  - Skip Keycloak:   use AUTH_MODE=static in .env (see README) and pytest for tools
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def _keycloak_help() -> str:
    return (
        "Keycloak is not reachable (connection refused).\n"
        "  • Start it:    docker compose up -d keycloak\n"
        "  • Or skip OIDC: python scripts/test_client.py --health-only\n"
        "  • Or tests:     PYTHONPATH=src pytest tests/ -q\n"
        "  • Static auth:  set AUTH_MODE=static + STATIC_TOKENS_JSON in .env (README)"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--health-only",
        action="store_true",
        help="Only GET /health on MCP (no Keycloak). Use when Keycloak is not running.",
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
    p.add_argument("--mcp-base", default=os.environ.get("MCP_BASE_URL", "http://localhost:8000"))
    args = p.parse_args()

    base = args.mcp_base.rstrip("/")

    with httpx.Client(timeout=30.0) as client:
        if args.health_only:
            try:
                hr = client.get(f"{base}/health")
            except httpx.ConnectError as e:
                print(f"MCP not reachable at {base}: {e}")
                print("Start the server: PYTHONPATH=src python -m stocksonar.server")
                return 1
            print("health", hr.status_code, hr.text)
            return 0 if hr.status_code == 200 else 1

        try:
            tr = client.post(
                args.token_url,
                data={
                    "client_id": args.client_id,
                    "username": args.username,
                    "password": args.password,
                    "grant_type": "password",
                },
            )
        except httpx.ConnectError:
            print(_keycloak_help())
            return 1

        if tr.status_code != 200:
            print("Token error:", tr.status_code, tr.text)
            if tr.status_code == 400 and "not fully set up" in tr.text:
                print(
                    "\nKeycloak 24+ requires a complete user profile (email, first/last name) for the password grant.\n"
                    "  • Reset Keycloak DB and re-import realm:  docker compose down -v && docker compose up -d keycloak\n"
                    "    (compose uses named volume keycloak_data; -v drops it so import runs again)\n"
                    "  • Or Admin UI: Users → <user> → Email + First/Last name; Required actions → clear all."
                )
            return 1
        token = tr.json().get("access_token")
        if not token:
            print("No access_token in response")
            return 1

        try:
            hr = client.get(f"{base}/health")
        except httpx.ConnectError as e:
            print(f"MCP not reachable at {base}: {e}")
            print("Start the server: PYTHONPATH=src python -m stocksonar.server")
            return 1

        print("health", hr.status_code, hr.text)
        print("access_token (first 32 chars):", token[:32] + "...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
