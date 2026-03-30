from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from stocksonar.middleware.http_rate_limit import RateLimitHttpMiddleware


@pytest.mark.asyncio
async def test_middleware_rewrites_429_with_retry_after():
    body = {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "__STOCKSONAR_RATE_LIMIT__ retry_after=33",
                }
            ],
        },
    }
    raw = json.dumps(body).encode()

    async def inner_app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(raw)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": raw, "more_body": False})

    collected: list[dict] = []

    async def capture_send(message):
        collected.append(message)

    mw = RateLimitHttpMiddleware(inner_app, "/mcp")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [],
    }
    await mw(scope, AsyncMock(), capture_send)

    assert len(collected) == 2
    assert collected[0]["status"] == 429
    hdrs = {k.decode(): v.decode() for k, v in collected[0]["headers"]}
    assert hdrs.get("retry-after") == "33"
    err = json.loads(collected[1]["body"].decode())
    assert err["error"]["data"]["retry_after"] == 33
    assert err["id"] == 7


@pytest.mark.asyncio
async def test_middleware_passes_through_without_marker():
    raw = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode()

    async def inner_app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": raw, "more_body": False})

    collected: list[dict] = []

    async def capture_send(message):
        collected.append(message)

    mw = RateLimitHttpMiddleware(inner_app, "/mcp")
    await mw({"type": "http", "method": "POST", "path": "/mcp", "headers": []}, AsyncMock(), capture_send)

    assert collected[0]["status"] == 200
    assert collected[1]["body"] == raw
