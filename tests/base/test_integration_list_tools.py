from __future__ import annotations

import pytest

from fastmcp.server.context import reset_transport, set_transport

from stocksonar.testing_factory import create_test_mcp


@pytest.mark.asyncio
async def test_mcp_lists_all_tools_with_stdio_transport():
    m = create_test_mcp()
    tok = set_transport("stdio")
    try:
        async with m._lifespan_manager():
            tools = await m.list_tools()
            names = sorted(t.name for t in tools)
            assert "get_stock_quote" in names
            assert "portfolio_risk_report" in names
    finally:
        reset_transport(tok)


@pytest.mark.asyncio
async def test_health_route_registered():
    from stocksonar.server import create_app

    m = create_app()
    routes = m._additional_http_routes
    paths = [getattr(r, "path", "") for r in routes]
    assert "/health" in paths
