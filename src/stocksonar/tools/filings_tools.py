"""Filings list + document retrieval — Analyst scopes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastmcp import Context
from fastmcp.server.auth import require_scopes

from stocksonar.middleware.tool_guard import enforce_tool_policies, finish_audit_ok
from stocksonar.upstream import filings_upstream as fu
from stocksonar.util.pagination import paginate_slice, pagination_meta
from stocksonar.util.response import ok_response

if TYPE_CHECKING:
    from stocksonar.cache.redis_cache import RedisCache
    from stocksonar.middleware.rate_limiter import RedisRateLimiter


def _rl(ctx: Context):
    return ctx.lifespan_context.get("rate_limiter")


def _cache(ctx: Context) -> RedisCache | None:
    return ctx.lifespan_context.get("cache")


async def list_company_filings(
    ctx: Context,
    symbol: str,
    cursor: str | None = None,
    limit: int = 20,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """Paginated regulatory / exchange filings list (Finnhub when applicable, else BSE-style stub)."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="list_company_filings")
    cache = _cache(ctx)
    ck = f"{symbol.upper()}:{from_date}:{to_date}"
    if cache:
        hit = await cache.get_json("filings_list", ck)
        if hit is not None:
            items = hit.get("filings") or []
            page, next_c = paginate_slice(items, cursor=cursor, limit=limit)
            finish_audit_ok("list_company_filings")
            return ok_response(
                {
                    "filings": page,
                    "pagination": pagination_meta(
                        total=len(items),
                        limit=limit,
                        cursor_in=cursor,
                        next_cursor=next_c,
                    ),
                },
                hit.get("source", "StockSonar"),
            )
    rows = await fu.list_filings(symbol, from_date=from_date, to_date=to_date)
    source = (
        "Finnhub SEC"
        if rows and rows[0].get("exchange") == "SEC (Finnhub)"
        else "BSE/NSE illustrative + Finnhub"
    )
    if cache:
        from stocksonar.config import get_settings

        await cache.set_json(
            "filings_list",
            ck,
            {"filings": rows, "source": source},
            get_settings().ttl_filings_meta,
        )
        for row in rows:
            fid = row.get("filing_id")
            if fid:
                await cache.set_json("filing_meta", str(fid), row, get_settings().ttl_filings_meta)
    page, next_c = paginate_slice(list(rows), cursor=cursor, limit=limit)
    finish_audit_ok("list_company_filings")
    return ok_response(
        {
            "filings": page,
            "pagination": pagination_meta(
                total=len(rows),
                limit=limit,
                cursor_in=cursor,
                next_cursor=next_c,
            ),
        },
        source,
    )


async def get_filing_document(ctx: Context, filing_id: str) -> dict[str, Any]:
    """Retrieve filing body as base64 (cached permanently). PDF or placeholder."""
    await enforce_tool_policies(rate_limiter=_rl(ctx), tool_name="get_filing_document")
    cache = _cache(ctx)
    fk = filing_id.strip()
    if cache:
        hit = await cache.get_json("filing_doc", fk)
        if hit is not None:
            finish_audit_ok("get_filing_document")
            return hit
    meta = None
    if cache:
        meta = await cache.get_json("filing_meta", fk)
    raw: bytes
    mime = "application/pdf"
    if meta and meta.get("source_url"):
        try:
            raw, mime = await fu.fetch_filing_bytes(meta["source_url"])
        except Exception as e:
            return ok_response(
                {
                    "error": True,
                    "code": "upstream_fetch_failed",
                    "message": str(e),
                    "filing_id": fk,
                },
                "StockSonar",
            )
    elif fk.startswith("stub:"):
        sym = fk.split(":")[1] if ":" in fk else "UNK"
        raw = await asyncio.to_thread(fu.stub_pdf_placeholder, sym, fk)
        mime = "application/pdf"
    else:
        raw = await asyncio.to_thread(fu.stub_pdf_placeholder, "UNK", fk)
        mime = "application/pdf"
    b64 = fu.bytes_to_b64(raw)
    src = "StockSonar"
    if isinstance(meta, dict):
        src = str(meta.get("exchange") or meta.get("source") or "StockSonar")
    out = ok_response(
        {
            "filing_id": fk,
            "content_base64": b64,
            "mime_type": mime,
            "note": "Verify against official exchange PDFs; stub used when URL missing.",
        },
        src,
    )
    if cache:
        await cache.set_json_forever("filing_doc", fk, out)
    finish_audit_ok("get_filing_document")
    return out


def register_filings_tools(mcp) -> None:
    mcp.tool(auth=require_scopes("filings:read"))(list_company_filings)
    mcp.tool(auth=require_scopes("filings:deep"))(get_filing_document)
