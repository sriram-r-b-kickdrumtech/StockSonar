"""Structured audit logging for tool invocations."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

audit_logger = logging.getLogger("stocksonar.audit")


def audit_tool_event(
    *,
    tool_name: str,
    user_id: str,
    tier: str,
    success: bool,
    detail: dict[str, Any] | None = None,
) -> None:
    payload = {
        "ts": time.time(),
        "tool_name": tool_name,
        "user_id": user_id,
        "tier": tier,
        "success": success,
        "detail": detail or {},
    }
    audit_logger.info(json.dumps(payload, default=str))
