"""Tests for concurrent webhook requests and event ordering.

SmsForwarder may receive multiple SMS simultaneously (e.g. batch send,
rapid incoming messages). The mock server must handle concurrent requests
correctly -- no dropped events, no corrupted state.
"""

from __future__ import annotations

import concurrent.futures

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]

# ── Concurrency ──────────────────────────────────────────────────


def test_concurrent_webhook_posts(mock_api, mock_reset):
    """50 concurrent POSTs -- all must be captured, count must match."""

    def post_one(i: int):
        return mock_api.post_webhook(json={"i": i}).json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(post_one, i) for i in range(50)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    assert len(results) == 50
    assert all(r["ok"] for r in results)

    after = mock_api.event_count()
    assert after == 50, f"expected 50 events, got {after}"


def test_concurrent_mixed_methods(mock_api, mock_reset):
    """Concurrent GET + POST + PUT -- all captured, methods correct."""
    expected = 30

    def send_one(i: int):
        if i % 3 == 0:
            return mock_api.get_webhook(params={"i": str(i)}).json()
        elif i % 3 == 1:
            return mock_api.post_webhook(json={"i": i}).json()
        else:
            return mock_api.put_webhook(json={"i": i}).json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(send_one, i) for i in range(expected)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    after = mock_api.event_count()
    assert after == expected, f"expected {expected} events, got {after}"

    events = mock_api.list_events(limit=expected)
    methods = {e["method"] for e in events["items"]}
    assert "GET" in methods
    assert "POST" in methods
    assert "PUT" in methods


# ── Event ordering ───────────────────────────────────────────────


def test_webhook_event_ordering(mock_api, mock_reset):
    """Sequential requests are captured in order (by ts_ms)."""
    for i in range(5):
        mock_api.post_webhook(json={"seq": i})

    events = mock_api.list_events(limit=10)
    items = events["items"]
    assert len(items) >= 5

    seqs = [e["body_json"]["seq"] for e in items if e["body_json"]]
    assert seqs == list(range(5)), f"expected ordered [0,1,2,3,4], got {seqs}"


# ── Reset during load ────────────────────────────────────────────


def test_reset_during_load(mock_api):
    """Reset clears events even while requests are arriving."""
    for i in range(10):
        mock_api.post_webhook(json={"i": i})

    assert mock_api.event_count() >= 10

    mock_api.reset()
    assert mock_api.event_count() == 0

    for i in range(3):
        mock_api.post_webhook(json={"i": i})

    assert mock_api.event_count() == 3


# ── Counter stability ────────────────────────────────────────────


def test_event_count_monotonic(mock_api, mock_reset):
    """Event count increases monotonically under sequential writes."""
    before = mock_api.event_count()
    counts = []
    for i in range(5):
        mock_api.post_webhook(json={"i": i})
        counts.append(mock_api.event_count())

    for i, c in enumerate(counts):
        assert c == before + i + 1, f"count at step {i}: expected {before + i + 1}, got {c}"
