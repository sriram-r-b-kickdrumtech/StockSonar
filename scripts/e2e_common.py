"""Shared helpers for StockSonar E2E / judge demo scripts (no package import path tricks)."""

from __future__ import annotations

import base64
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO

import httpx
import mcp.types as mcp_types


class Tee(TextIO):
    """Write to multiple text streams (console + log file)."""

    def __init__(self, *streams: TextIO) -> None:
        self._streams = streams

    def write(self, s: str) -> int:
        n = len(s)
        for f in self._streams:
            f.write(s)
            f.flush()
        return n

    def flush(self) -> None:
        for f in self._streams:
            f.flush()

    def isatty(self) -> bool:
        return self._streams[0].isatty() if self._streams else False


@contextmanager
def tee_stdout_stderr(log_path: Path) -> Any:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_obj = log_path.open("w", encoding="utf-8")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = Tee(old_out, file_obj)
    sys.stderr = Tee(old_err, file_obj)
    try:
        yield file_obj
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        file_obj.close()


def decode_jwt_sub(token: str) -> str | None:
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except (IndexError, ValueError, json.JSONDecodeError):
        return None


def fetch_password_token(
    *,
    token_url: str,
    client_id: str,
    username: str,
    password: str,
    timeout: float = 30.0,
) -> str:
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            token_url,
            data={
                "client_id": client_id,
                "username": username,
                "password": password,
                "grant_type": "password",
            },
        )
    if r.status_code != 200:
        raise RuntimeError(f"Token HTTP {r.status_code}: {r.text[:500]}")
    body = r.json()
    at = body.get("access_token")
    if not at:
        raise RuntimeError("No access_token in token response")
    return str(at)


def mcp_url_from_parts(mcp_base: str, mcp_path: str) -> str:
    base = mcp_base.rstrip("/")
    path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
    return f"{base}{path}"


def format_tool_result(result: mcp_types.CallToolResult, max_chars: int = 12000) -> str:
    parts: list[str] = []
    if result.isError:
        parts.append("isError: true")
    for block in result.content:
        if isinstance(block, mcp_types.TextContent):
            text = block.text
            try:
                parsed = json.loads(text)
                s = json.dumps(parsed, indent=2, default=str)
            except json.JSONDecodeError:
                s = text
            if len(s) > max_chars:
                s = s[:max_chars] + "\n… [truncated]"
            parts.append(s)
        else:
            parts.append(repr(block))
    return "\n".join(parts) if parts else "(empty content)"


def env_or(key: str, default: str) -> str:
    return (os.environ.get(key) or default).strip()
