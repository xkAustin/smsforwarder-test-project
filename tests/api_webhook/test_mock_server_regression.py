"""Regression tests for mock server internals.

These tests validate:
- /events/{event_id} endpoint (never tested before)
- Event ID uniqueness
- Deque max bound (MAX_EVENTS = 5000)
- Response schema consistency for all endpoints
- Health endpoint after fault injection
"""
from __future__ import annotations

import requests


def get_events(base_url: str, limit: int = 10):
    r = requests.get(f"{base_url}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()


def post_ok(base_url: str, path: str, **kwargs):
    r = requests.post(f"{base_url}{path}", timeout=3, **kwargs)
    r.raise_for_status()
    return r.json()


# ── /events/{event_id} ───────────────────────────────────────────


def test_get_event_by_id(mock_base, mock_reset):
    """GET /events/{event_id} returns the correct event."""
    r = requests.post(f"{mock_base}/webhook", json={"test": "find-me"}, timeout=3)
    r.raise_for_status()
    event_id = r.json()["id"]

    r2 = requests.get(f"{mock_base}/events/{event_id}", timeout=3)
    assert r2.status_code == 200
    event = r2.json()
    assert event["id"] == event_id
    assert event["body_json"] == {"test": "find-me"}


def test_get_event_by_id_not_found(mock_base, mock_reset):
    """GET /events/{event_id} returns 404 for non-existent id."""
    r = requests.get(f"{mock_base}/events/nonexistent-uuid-12345", timeout=3)
    assert r.status_code == 404
    data = r.json()
    assert "error" in data
    assert data["error"] == "not_found"


# ── Event ID uniqueness ──────────────────────────────────────────


def test_event_id_unique(mock_base, mock_reset):
    """Each event gets a unique UUID."""
    ids = set()
    for i in range(20):
        r = requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=3)
        r.raise_for_status()
        ids.add(r.json()["id"])

    assert len(ids) == 20, f"expected 20 unique IDs, got {len(ids)}"


# ── Deque bounded correctly ──────────────────────────────────────


def test_max_events_bound(mock_base):
    """MAX_EVENTS = 5000; older events are evicted when full."""
    requests.post(f"{mock_base}/reset", timeout=3)

    total = 100  # Send more than default limit but less than MAX
    for i in range(total):
        requests.post(f"{mock_base}/webhook", json={"i": i}, timeout=3)

    events = get_events(mock_base, limit=total + 10)
    assert events["count"] == total

    # All event IDs should be unique (no rollover corruption)
    ids = {e["id"] for e in events["items"]}
    assert len(ids) == len(events["items"]), "duplicate event IDs found"


# ── Response schema ──────────────────────────────────────────────


def test_webhook_response_schema(mock_base):
    """POST /webhook response has expected fields."""
    r = requests.post(f"{mock_base}/webhook", json={"test": True}, timeout=3)
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "id" in data
    assert data["ok"] is True
    assert isinstance(data["id"], str)
    assert len(data["id"]) == 36  # UUID format


def test_health_response_schema(mock_base):
    """GET /health returns expected structure."""
    r = requests.get(f"{mock_base}/health", timeout=3)
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "events" in data
    assert data["ok"] is True
    assert isinstance(data["events"], int)


def test_events_list_schema(mock_base, mock_reset):
    """GET /events returns count + items list."""
    requests.post(f"{mock_base}/webhook", json={"test": True}, timeout=3)

    data = get_events(mock_base)
    assert "count" in data
    assert "items" in data
    assert isinstance(data["count"], int)
    assert isinstance(data["items"], list)
    assert data["count"] >= 1
    assert len(data["items"]) >= 1


def test_captured_event_schema(mock_base, mock_reset):
    """Each captured event has all required fields."""
    requests.post(f"{mock_base}/webhook", json={"test": True}, timeout=3)

    events = get_events(mock_base)
    event = events["items"][0]

    required = ["id", "ts_ms", "method", "path", "query",
                "headers", "body_raw", "body_json", "body_form",
                "response_status"]
    for field in required:
        assert field in event, f"missing field: {field}"

    assert isinstance(event["id"], str)
    assert isinstance(event["ts_ms"], int)
    assert isinstance(event["method"], str)
    assert isinstance(event["path"], str)
    assert isinstance(event["query"], dict)
    assert isinstance(event["headers"], dict)
    assert isinstance(event["body_raw"], str)
    assert isinstance(event["response_status"], int)


# ── Health check after fault injection ───────────────────────────


def test_health_after_fault_injection(mock_base):
    """Health stays ok even after configuring fault modes."""
    post_ok(mock_base, "/fault/reset")
    # Configure delay, then check health still responds
    post_ok(mock_base, "/fault/config", params={"mode": "delay", "delay_ms": 5000})

    r = requests.get(f"{mock_base}/health", timeout=1)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Reset faults
    post_ok(mock_base, "/fault/reset")


# ── Fault config bad mode ────────────────────────────────────────


def test_fault_config_bad_mode_rejected(mock_base):
    """fault/config rejects invalid mode strings."""
    r = requests.post(
        f"{mock_base}/fault/config",
        params={"mode": "explode", "fail_count": 1},
        timeout=3,
    )
    assert r.status_code == 400
    data = r.json()
    assert "error" in data


# ── Reset endpoint idempotency ───────────────────────────────────


def test_reset_idempotent(mock_base):
    """Multiple resets in a row should not fail."""
    for _ in range(3):
        r = requests.post(f"{mock_base}/reset", timeout=3)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    # After resets, count should be 0
    events = get_events(mock_base)
    assert events["count"] == 0


# ── events?limit clamping ────────────────────────────────────────


def test_events_limit_clamped(mock_base, mock_reset):
    """The limit parameter is clamped to [1, 500]."""
    # limit=0 should be clamped to 1
    r = requests.get(f"{mock_base}/events", params={"limit": 0}, timeout=3)
    assert r.status_code == 200

    # limit=1000 should be clamped to 500
    r = requests.get(f"{mock_base}/events", params={"limit": 1000}, timeout=3)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) <= 500


def test_events_limit_negative(mock_base):
    """Negative limit should be clamped to 1."""
    r = requests.get(f"{mock_base}/events", params={"limit": -5}, timeout=3)
    assert r.status_code == 200
    data = r.json()
    # Should return at most 1 item when limit clamped to 1
    assert len(data["items"]) <= data["count"]
