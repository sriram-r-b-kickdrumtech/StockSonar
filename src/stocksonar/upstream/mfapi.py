"""MFapi.in HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

BASE = "https://api.mfapi.in"


async def search_schemes(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{BASE}/mf/search", params={"q": query})
        r.raise_for_status()
        data = r.json()
    return list(data) if isinstance(data, list) else data.get("data", []) or []


async def get_nav(scheme_code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{BASE}/mf/{scheme_code}")
        r.raise_for_status()
        return r.json()
