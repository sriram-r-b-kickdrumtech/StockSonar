"""Filings: Finnhub when API key present; stub list for Indian symbols."""

from __future__ import annotations

import base64
import hashlib
from datetime import date, timedelta
from typing import Any

import httpx

from stocksonar.config import get_settings


def _stub_filings(symbol: str) -> list[dict[str, Any]]:
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    today = date.today()
    out = []
    for i in range(12):
        d = today - timedelta(days=30 * i)
        fid = f"stub:{sym}:{d.isoformat()}:annual"
        out.append(
            {
                "filing_id": fid,
                "symbol": sym,
                "form_type": "ANNUAL_REPORT",
                "filed_date": d.isoformat(),
                "title": f"{sym} annual disclosure (sample row {i + 1})",
                "source_url": f"https://www.bseindia.com/stock-share/{sym}/disclosures",
                "exchange": "BSE/NSE (illustrative)",
            }
        )
    return out


async def list_filings(
    symbol: str,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict[str, Any]]:
    s = get_settings()
    sym = symbol.upper().strip()
    if sym.endswith(".NS") or sym.endswith(".BO") or ".NS" in sym or ".BO" in sym:
        return _stub_filings(sym)
    if not s.finnhub_api_key:
        return _stub_filings(sym.replace(".US", ""))
    to_d = to_date or date.today().isoformat()
    fr = from_date or (date.today() - timedelta(days=365)).isoformat()
    url = "https://finnhub.io/api/v1/stock/filings"
    params = {"symbol": sym, "from": fr, "to": to_d, "token": s.finnhub_api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        raw = r.json()
    out = []
    for row in raw if isinstance(raw, list) else []:
        acc = row.get("filingUrl") or row.get("reportUrl") or ""
        fid = f"finnhub:{row.get('symbol')}:{row.get('acceptedDate', '')}:{hashlib.sha256(acc.encode()).hexdigest()[:12]}"
        out.append(
            {
                "filing_id": fid,
                "symbol": row.get("symbol"),
                "form_type": row.get("form"),
                "filed_date": row.get("acceptedDate"),
                "title": row.get("form"),
                "source_url": acc or None,
                "exchange": "SEC (Finnhub)",
            }
        )
    return out


async def fetch_filing_bytes(source_url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(source_url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "application/octet-stream")
        return r.content, ctype


def stub_pdf_placeholder(symbol: str, filing_id: str) -> bytes:
    """Minimal PDF bytes placeholder when no URL fetch (demo only)."""
    text = (
        f"%PDF-1.4\n1 0 obj<<>>endobj\n"
        f"2 0 obj<</Length 50>>stream\nBT /F1 12 Tf 72 720 Td ({symbol} {filing_id}) Tj ET\nendstream endobj\n"
        f"xref\n0 3\ntrailer<<>>\n%%EOF"
    )
    return text.encode("latin-1", errors="ignore")


def bytes_to_b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")
