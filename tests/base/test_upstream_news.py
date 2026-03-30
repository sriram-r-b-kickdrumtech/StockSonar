from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stocksonar.upstream import news as news_mod


@pytest.mark.asyncio
@patch("stocksonar.upstream.news.get_settings")
@patch("stocksonar.upstream.news.httpx.AsyncClient")
async def test_get_company_news(mock_client_cls, mock_settings):
    mock_settings.return_value.gnews_api_key = "k"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "articles": [
            {
                "title": "T",
                "url": "http://x",
                "publishedAt": "2026-01-01",
                "source": {"name": "S"},
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client_cls.return_value = mock_client
    arts, _total = await news_mod.company_news("Reliance")
    assert arts[0]["title"] == "T"


@pytest.mark.asyncio
@patch("stocksonar.upstream.news.get_settings")
async def test_news_api_key_missing(mock_settings):
    mock_settings.return_value.gnews_api_key = ""
    with pytest.raises(ValueError, match="GNEWS_API_KEY"):
        await news_mod.company_news("X")
