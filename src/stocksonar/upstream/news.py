"""GNews API."""

from __future__ import annotations

from typing import Any

import httpx

from stocksonar.config import get_settings


async def company_news(
    company: str,
    *,
    max_results: int = 10,
    country: str = "in",
    page: int = 1,
    from_iso: str | None = None,
    to_iso: str | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    """Returns (articles, total_available_from_api_or_none).

    When ``from_iso`` / ``to_iso`` are set, GNews ``from`` / ``to`` filters apply (ISO 8601).
    Articles are still filtered client-side by ``published_at`` when both bounds are set.
    """
    s = get_settings()
    if not s.gnews_api_key:
        raise ValueError(
            "GNEWS_API_KEY is not set. Register at https://gnews.io/ and add to .env"
        )
    params: dict[str, str | int] = {
        "token": s.gnews_api_key,
        "q": company,
        "lang": "en",
        "country": country,
        "max": max_results,
        "page": max(1, page),
    }
    if from_iso:
        params["from"] = from_iso
    if to_iso:
        params["to"] = to_iso
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get("https://gnews.io/api/v4/search", params=params)
        r.raise_for_status()
        data = r.json()
    articles = data.get("articles") or []
    total = data.get("totalArticles")
    out = []
    for a in articles:
        out.append(
            {
                "title": a.get("title"),
                "url": a.get("url"),
                "published_at": a.get("publishedAt"),
                "source": (a.get("source") or {}).get("name"),
            }
        )
    return out, int(total) if total is not None else None


async def market_news(
    *, max_results: int = 10, page: int = 1
) -> tuple[list[dict[str, Any]], int | None]:
    return await company_news(
        "India stock market OR NSE OR BSE", max_results=max_results, page=page
)


def score_title_sentiment(title: str) -> dict[str, Any]:
    """Lightweight lexicon sentiment for Premium (not NLP model)."""
    t = (title or "").lower()
    pos = (
        "gain",
        "up",
        "rise",
        "rally",
        "bull",
        "beat",
        "surge",
        "record",
        "high",
        "growth",
    )
    neg = (
        "loss",
        "down",
        "fall",
        "crash",
        "bear",
        "miss",
        "cut",
        "fraud",
        "probe",
        "selloff",
        "slump",
    )
    p = sum(1 for w in pos if w in t)
    n = sum(1 for w in neg if w in t)
    score = p - n
    label = "neutral"
    if score >= 2:
        label = "positive"
    elif score <= -2:
        label = "negative"
    elif score > 0:
        label = "slightly_positive"
    elif score < 0:
        label = "slightly_negative"
    return {"score": score, "label": label, "method": "lexicon_v1"}
