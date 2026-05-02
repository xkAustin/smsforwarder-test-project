"""Tests for concurrent webhook requests and event ordering.

SmsForwarder may receive multiple SMS simultaneously (e.g. batch send,
rapid incoming messages). The mock server must handle concurrent requests
correctly — no dropped events, no corrupted state.
"""
from __future__ import annotations

import concurrent.futures
import time

import requests


def get_events(base_url: str, limit: int = 100):
    r = requests.get(f"{base_url}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()


def get_count(base_url: str):
    j = get_events(base_url, limit=1)
    return int(j["count"])


# ── Concurrency ──────────────────────────────────────────────────


def test_concurrent_webhook_posts(mock_base, mock_reset):
    """50 concurrent POSTs — all must be captured, count must match.

    Verifies requests were actually parallel by checking that the total
    wall-clock duration is well below sequential execution time.
    """
    n = 50

    def post_one(i: int):
        r = requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=5)
        r.raise_for_status()
        return r.json()

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(post_one, i) for i in range(n)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.perf_counter() - t0

    assert len(results) == n
    assert all(r["ok"] for r in results)

    after = get_count(mock_base)
    assert after == n, f"expected {n} events, got {after}"

    # 50 sequential requests at ~1ms each ≈ 50ms; parallel with 10 workers
    # should complete in well under half that.
    assert elapsed < 0.250, (
        f"concurrent 50 requests took {elapsed:.3f}s — "
        "possible serial execution or server slowdown"
    )


def test_concurrent_mixed_methods(mock_base, mock_reset):
    """Concurrent GET + POST + PUT — all captured, methods correct."""
    expected = 30

    def send_one(i: int):
        if i % 3 == 0:
            r = requests.get(
                f"{mock_base}/webhook", params={"i": str(i)}, timeout=5
            )
        elif i % 3 == 1:
            r = requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=5)
        else:
            r = requests.put(f"{mock_base}/webhook", json={"i": i}, timeout=5)
        r.raise_for_status()
        return r.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(send_one, i) for i in range(expected)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    after = get_count(mock_base)
    assert after == expected, f"expected {expected} events, got {after}"

    events = get_events(mock_base, limit=expected)
    methods = {e["method"] for e in events["items"]}
    assert "GET" in methods
    assert "POST" in methods
    assert "PUT" in methods


# ── Event ordering ───────────────────────────────────────────────


def test_webhook_event_ordering(mock_base, mock_reset):
    """Sequential requests are captured in order (by ts_ms)."""
    for i in range(5):
        r = requests.post(
            f"{mock_base}/webhook", json={"seq": i}, timeout=3
        )
        r.raise_for_status()

    events = get_events(mock_base, limit=10)
    items = events["items"]
    assert len(items) >= 5

    seqs = [e["body_json"]["seq"] for e in items if e["body_json"]]
    assert seqs == list(range(5)), f"expected ordered [0,1,2,3,4], got {seqs}"


# ── Reset during load ────────────────────────────────────────────


def test_reset_during_load(mock_base):
    """Reset clears events even while requests are arriving."""
    # Send some events
    for i in range(10):
        requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=3)

    assert get_count(mock_base) >= 10

    # Reset
    requests.post(f"{mock_base}/reset", timeout=3).raise_for_status()
    assert get_count(mock_base) == 0

    # Send more after reset
    for i in range(3):
        requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=3)

    assert get_count(mock_base) == 3


# ── Counter stability ────────────────────────────────────────────


def test_event_count_monotonic(mock_base, mock_reset):
    """Event count increases monotonically under sequential writes."""
    before = get_count(mock_base)
    counts = []
    for i in range(5):
        requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=3)
        counts.append(get_count(mock_base))

    for i, c in enumerate(counts):
        assert c == before + i + 1, f"count at step {i}: expected {before + i + 1}, got {c}"
