"""Structured error payloads (tools + HTTP-aligned metadata)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from stocksonar.config import get_settings


def error_payload(
    *,
    code: str,
    message: str,
    http_status: int | None = None,
    retry_after: int | None = None,
    required_scope: str | None = None,
    upstream: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """JSON-serializable error object for tool results and logs."""
    out: dict[str, Any] = {
        "error": True,
        "code": code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": get_settings().disclaimer,
    }
    if http_status is not None:
        out["http_status"] = http_status
    if retry_after is not None:
        out["retry_after"] = retry_after
    if required_scope:
        out["required_scope"] = required_scope
    if upstream:
        out["upstream"] = upstream
    if extra:
        out["detail"] = extra
    return out
