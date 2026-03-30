"""ASGI middleware: tier rate limits → HTTP 429 + Retry-After (Streamable HTTP JSON mode)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from stocksonar.exceptions import parse_rate_limit_marker

logger = logging.getLogger(__name__)


def _extract_tool_error_text(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if not result.get("isError"):
        return None
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text") or ""
    return None


def _find_rate_limit_in_json(obj: Any) -> int | None:
    if isinstance(obj, dict):
        t = _extract_tool_error_text(obj)
        if t:
            ra = parse_rate_limit_marker(t)
            if ra is not None:
                return ra
        for v in obj.values():
            found = _find_rate_limit_in_json(v)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_rate_limit_in_json(v)
            if found is not None:
                return found
    return None


class RateLimitHttpMiddleware:
    """If JSON-RPC response body contains a tier rate-limit marker, rewrite to HTTP 429."""

    def __init__(self, app: Any, mcp_path: str) -> None:
        self.app = app
        self.mcp_path = mcp_path.rstrip("/") or "/mcp"

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path.rstrip("/") != self.mcp_path.rstrip("/"):
            await self.app(scope, receive, send)
            return

        start_msg: dict | None = None
        body_chunks: list[bytes] = []

        async def send_wrapper(message: dict) -> None:
            nonlocal start_msg
            if message["type"] == "http.response.start":
                start_msg = message
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body") or b"")
                if message.get("more_body", False):
                    return
                if start_msg is None:
                    await send(message)
                    return
                status = start_msg.get("status", 200)
                headers = list(start_msg.get("headers") or [])
                body = b"".join(body_chunks)
                if status == 200 and body:
                    try:
                        text = body.decode("utf-8")
                    except UnicodeDecodeError:
                        await send(start_msg)
                        await send(
                            {"type": "http.response.body", "body": body, "more_body": False}
                        )
                        return
                    rid = None
                    payload: dict | None = None
                    try:
                        payload = json.loads(text)
                        rid = payload.get("id")
                    except json.JSONDecodeError:
                        pass
                    ra = None
                    if "__STOCKSONAR_RATE_LIMIT__" in text:
                        m = re.search(
                            r"__STOCKSONAR_RATE_LIMIT__\s+retry_after=(\d+)", text
                        )
                        if m:
                            ra = int(m.group(1))
                    if ra is None and payload is not None:
                        ra = _find_rate_limit_in_json(payload)
                    if ra is not None:
                        err_body = {
                            "jsonrpc": "2.0",
                            "id": rid,
                            "error": {
                                "code": -32029,
                                "message": "Rate limit exceeded",
                                "data": {
                                    "error": "rate_limit_exceeded",
                                    "retry_after": ra,
                                },
                            },
                        }
                        new_raw = json.dumps(err_body).encode("utf-8")
                        hdrs = [
                            (k, v)
                            for k, v in headers
                            if k.lower() not in (b"content-length", b"retry-after")
                        ]
                        hdrs.append((b"content-length", str(len(new_raw)).encode()))
                        hdrs.append((b"retry-after", str(ra).encode()))
                        await send(
                            {
                                "type": "http.response.start",
                                "status": 429,
                                "headers": hdrs,
                                "trailers": None,
                            }
                        )
                        await send(
                            {"type": "http.response.body", "body": new_raw, "more_body": False}
                        )
                        return
                await send(start_msg)
                await send({"type": "http.response.body", "body": body, "more_body": False})
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)
