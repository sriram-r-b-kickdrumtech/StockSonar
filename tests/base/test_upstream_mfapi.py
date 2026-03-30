from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stocksonar.upstream import mfapi


@pytest.mark.asyncio
@patch("stocksonar.upstream.mfapi.httpx.AsyncClient")
async def test_search_mutual_funds(mock_client_cls):
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(
        return_value=[{"scheme_code": "1", "scheme_name": "HDFC Top 100"}]
    )
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client_cls.return_value = mock_client
    rows = await mfapi.search_schemes("HDFC")
    assert rows[0]["scheme_code"] == "1"
