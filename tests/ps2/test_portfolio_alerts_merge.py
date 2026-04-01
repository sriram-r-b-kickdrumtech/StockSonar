from __future__ import annotations

import pytest

from stocksonar.services.portfolio_alerts import (
    HEALTH_SOURCE,
    _normalize_from_concentration,
    merge_risk_alerts,
)


@pytest.mark.asyncio
async def test_merge_skips_when_health_check_owns_key(tool_context):
    store = tool_context.lifespan_context["portfolio"]
    uid = "u1"
    await store.set_alerts(
        uid,
        [
            {
                "type": "sector",
                "sector": "IT",
                "allocation_pct": 45.0,
                "message": "from health",
                "source": HEALTH_SOURCE,
            }
        ],
    )
    incoming = [
        _normalize_from_concentration(
            {"kind": "sector", "sector": "IT", "allocation_pct": 50.0}
        )
    ]
    await merge_risk_alerts(store, uid, incoming)
    alerts = await store.load_alerts(uid)
    assert len(alerts) == 1
    assert alerts[0].get("source") == HEALTH_SOURCE


@pytest.mark.asyncio
async def test_merge_adds_concentration_alerts(tool_context):
    store = tool_context.lifespan_context["portfolio"]
    uid = "u2"
    await store.set_alerts(uid, [])
    incoming = [
        _normalize_from_concentration(
            {"kind": "single_stock", "symbol": "TCS", "allocation_pct": 25.0}
        )
    ]
    await merge_risk_alerts(store, uid, incoming)
    alerts = await store.load_alerts(uid)
    assert any(a.get("symbol") == "TCS" for a in alerts)
