from __future__ import annotations

from datetime import datetime, timezone

from stocksonar.config import get_settings


def ok_response(data: object, source: str) -> dict:
    return {
        "source": source,
        "disclaimer": get_settings().disclaimer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
