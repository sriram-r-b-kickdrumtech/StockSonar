#!/usr/bin/env bash
# One-click logout for Claude Desktop + StockSonar (Mac).
# Clears mcp-remote tokens and opens Keycloak logout in the browser.

set -euo pipefail

HOST="${STOCKSONAR_HOST:-https://jarvis-kd.duckdns.org}"

open "${HOST}/auth/logout?go=1" 2>/dev/null || open "${HOST}/auth/logout"
rm -rf ~/.mcp-auth

echo "Cleared ~/.mcp-auth and opened Keycloak logout."
echo "Next: Quit Claude (Cmd+Q), reopen, then Settings → Developer → MCP → toggle stocksonar."
