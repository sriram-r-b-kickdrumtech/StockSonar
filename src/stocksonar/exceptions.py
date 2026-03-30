"""Domain errors surfaced to MCP clients."""

from __future__ import annotations

import re

from fastmcp.exceptions import ToolError

_RATE_MARK = "__STOCKSONAR_RATE_LIMIT__"


class RateLimitToolError(ToolError):
    """Raised when per-user tier rate limit is exceeded (HTTP 429 + Retry-After in strict JSON mode)."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, int(retry_after))
        super().__init__(f"{_RATE_MARK} retry_after={self.retry_after}")


def parse_rate_limit_marker(message: str) -> int | None:
    m = re.search(rf"{re.escape(_RATE_MARK)}\s+retry_after=(\d+)", message)
    if not m:
        return None
    return int(m.group(1))
