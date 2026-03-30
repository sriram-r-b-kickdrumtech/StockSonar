"""Cursor-based pagination helpers for MCP tool responses."""

from __future__ import annotations

import base64
import json
from typing import Any, TypeVar

T = TypeVar("T")


def encode_cursor(offset: int) -> str:
    raw = json.dumps({"o": offset}).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor or not str(cursor).strip():
        return 0
    pad = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(str(cursor) + pad)
        data = json.loads(raw.decode("ascii"))
        return max(0, int(data.get("o", 0)))
    except (ValueError, json.JSONDecodeError, KeyError):
        return 0


def paginate_slice(
    items: list[T],
    *,
    cursor: str | None,
    limit: int,
) -> tuple[list[T], str | None]:
    """Return page of items and next_cursor, or None if no further pages."""
    lim = max(1, min(int(limit), 500))
    start = decode_cursor(cursor)
    page = items[start : start + lim]
    next_start = start + len(page)
    next_cursor = encode_cursor(next_start) if next_start < len(items) else None
    return page, next_cursor


def pagination_meta(
    *,
    total: int | None,
    limit: int,
    cursor_in: str | None,
    next_cursor: str | None,
) -> dict[str, Any]:
    return {
        "total": total,
        "limit": limit,
        "cursor": cursor_in,
        "next_cursor": next_cursor,
    }
