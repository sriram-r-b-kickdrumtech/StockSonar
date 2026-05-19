"""Session helpers: who am I, logout / switch Keycloak user (Claude Desktop, Gemini)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastmcp import Context
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token

from stocksonar.config import get_settings
from stocksonar.util.response import ok_response


def _logout_url() -> str:
    settings = get_settings()
    realm_base = str(settings.keycloak_authorization_server).rstrip("/")
    redirect = quote(str(settings.mcp_base_url).rstrip("/"), safe="")
    return (
        f"{realm_base}/protocol/openid-connect/logout"
        f"?redirect_uri={redirect}"
    )


def _session_from_token() -> dict[str, Any]:
    token = get_access_token()
    if token is None:
        return {"authenticated": False}
    claims = getattr(token, "claims", None) or {}
    roles: list[str] = []
    realm_access = claims.get("realm_access") if isinstance(claims, dict) else None
    if isinstance(realm_access, dict):
        raw_roles = realm_access.get("roles")
        if isinstance(raw_roles, list):
            roles = [str(r) for r in raw_roles if r]
    return {
        "authenticated": True,
        "subject": getattr(token, "sub", None) or claims.get("sub"),
        "client_id": getattr(token, "client_id", None),
        "preferred_username": claims.get("preferred_username") if isinstance(claims, dict) else None,
        "realm_roles": roles,
        "scopes": sorted(getattr(token, "scopes", []) or []),
    }


async def current_session(_ctx: Context) -> dict[str, Any]:
    """Show the Keycloak user and tier roles for this MCP connection."""
    return ok_response(_session_from_token(), source="stocksonar/auth")


async def logout_switch_user(_ctx: Context) -> dict[str, Any]:
    """End this MCP login so you can sign in as another Keycloak user (free / premium / analyst).

    Use from Claude Desktop or Gemini when the user asks to log out or switch tier.
    """
    session = _session_from_token()
    logout = _logout_url()
    page = f"{get_settings().mcp_base_url.rstrip('/')}/auth/logout"
    return ok_response(
        {
            "current_session": session,
            "keycloak_logout_url": logout,
            "logout_help_page": page,
            "claude_desktop_steps": [
                "Open keycloak_logout_url in your browser (ends Keycloak SSO session).",
                "On Mac, run in Terminal: rm -rf ~/.mcp-auth",
                "Quit Claude completely (Cmd+Q), reopen.",
                "Settings → Developer → MCP → toggle stocksonar off and on.",
                "Log in as the new user when the browser opens (e.g. free/freepass, analyst/analystpass).",
            ],
            "gemini_cli_steps": [
                "Open keycloak_logout_url in your browser.",
                "Run: rm -f ~/.gemini/mcp-oauth-tokens.json",
                "In gemini: /mcp auth stocksonar",
            ],
            "one_click_mac_script": "demo-remote/logout-stocksonar.sh",
        },
        source="stocksonar/auth",
    )


def register_auth_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("market:read"))(current_session)
    mcp.tool(auth=require_scopes("market:read"))(logout_switch_user)
