"""PS2 prompts are registered on the FastMCP app."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from stocksonar.server import create_app


@pytest.mark.asyncio
async def test_ps2_prompts_registered():
    mcp = create_app()
    # HTTP servers filter prompts by token; bypass for registration check only.
    with patch("fastmcp.server.server._get_auth_context", return_value=(True, None)):
        prompts = await mcp.list_prompts()
    names = {p.name for p in prompts}
    assert "morning_risk_brief" in names
    assert "rebalance_suggestions" in names
    assert "earnings_exposure" in names
