"""FastMCP StockSonar server entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from fastmcp import FastMCP

from stocksonar.auth.provider import build_auth_provider
from stocksonar.cache.redis_cache import RedisCache
from stocksonar.config import get_settings
from stocksonar.middleware.http_rate_limit import RateLimitHttpMiddleware
from stocksonar.middleware.rate_limiter import RedisRateLimiter
from stocksonar.services.portfolio import PortfolioStore
from stocksonar.services.watchlist import WatchlistStore
from stocksonar.tools.register import register_all_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as e:
        logger.warning("Redis ping failed: %s — tools may error at runtime", e)
    cache = RedisCache(client, settings)
    rate_limiter = RedisRateLimiter(client, settings)
    portfolio = PortfolioStore(client)
    watchlist = WatchlistStore(client)
    try:
        yield {
            "redis": client,
            "cache": cache,
            "rate_limiter": rate_limiter,
            "portfolio": portfolio,
            "watchlist": watchlist,
            "settings": settings,
        }
    finally:
        await client.aclose()


def create_app() -> FastMCP:
    settings = get_settings()
    auth = build_auth_provider(settings)
    mcp = FastMCP(
        "StockSonar",
        instructions=(
            "Indian financial intelligence MCP: market data, mutual funds, news, "
            "and PS2 portfolio risk tools. All outputs are JSON facts with sources — not advice. "
            "When the user wants to log out or switch Keycloak tier (free/premium/analyst), "
            "call the logout_switch_user tool and follow its steps."
        ),
        auth=auth,
        lifespan=lifespan,
    )
    register_all_tools(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "stocksonar",
                "redis_url_configured": bool(settings.redis_url),
            }
        )

    @mcp.custom_route("/auth/logout", methods=["GET"])
    async def auth_logout_help(request: Request) -> HTMLResponse | RedirectResponse:
        """Browser helper: ?go=1 redirects to Keycloak logout."""
        from stocksonar.tools.auth_tools import _logout_url

        logout = _logout_url()
        if request.query_params.get("go") == "1":
            return RedirectResponse(logout, status_code=302)
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>StockSonar logout</title></head>
<body style="font-family:system-ui;max-width:40rem;margin:2rem auto;padding:0 1rem">
<h1>Switch StockSonar user</h1>
<ol>
<li><a href="{logout}">Log out of Keycloak</a> (or <a href="/auth/logout?go=1">redirect</a>)</li>
<li>On your Mac: <code>rm -rf ~/.mcp-auth</code></li>
<li>Quit Claude (Cmd+Q), reopen → Developer → MCP → toggle <strong>stocksonar</strong></li>
<li>Reconnect and sign in as another user (<code>free</code>, <code>premium</code>, <code>analyst</code>)</li>
</ol>
<p>In Claude chat you can also say: <em>Use StockSonar logout_switch_user</em></p>
</body></html>"""
        return HTMLResponse(html)

    return mcp


mcp = create_app()


def main() -> None:
    import asyncio

    settings = get_settings()
    asyncio.run(
        mcp.run_http_async(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
            path=settings.streamable_http_path,
            json_response=settings.mcp_json_response,
            middleware=[
                Middleware(
                    RateLimitHttpMiddleware,
                    mcp_path=settings.streamable_http_path,
                ),
            ],
        )
    )


if __name__ == "__main__":
    main()
