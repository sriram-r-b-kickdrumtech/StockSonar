from __future__ import annotations

from stocksonar.exceptions import RateLimitToolError, parse_rate_limit_marker
from stocksonar.util.pagination import decode_cursor, encode_cursor, paginate_slice


def test_rate_limit_tool_error_message_and_parse():
    e = RateLimitToolError(42)
    assert e.retry_after == 42
    assert "__STOCKSONAR_RATE_LIMIT__" in str(e)
    assert parse_rate_limit_marker(str(e)) == 42


def test_parse_rate_limit_marker_none():
    assert parse_rate_limit_marker("other error") is None


def test_pagination_roundtrip():
    items = list(range(25))
    p1, n1 = paginate_slice(items, cursor=None, limit=10)
    assert p1 == list(range(10))
    assert n1 is not None
    p2, n2 = paginate_slice(items, cursor=n1, limit=10)
    assert len(p2) == 10
    p3, n3 = paginate_slice(items, cursor=n2, limit=10)
    assert p3 == [20, 21, 22, 23, 24]
    assert n3 is None


def test_encode_decode_cursor():
    c = encode_cursor(100)
    assert decode_cursor(c) == 100
    assert decode_cursor(None) == 0
