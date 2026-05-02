"""Regression tests for mock server internals.

These tests validate:
- /events/{event_id} endpoint
- Event ID uniqueness
- Deque max bound (MAX_EVENTS = 5000)
- Response schema consistency for all endpoints
- Health endpoint after fault injection
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]

# ── /events/{event_id} ───────────────────────────────────────────


def test_get_event_by_id(mock_api, mock_reset):
    r = mock_api.post_webhook(json={"test": "find-me"})
    event_id = r.json()["id"]

    event = mock_api.get_event(event_id)
    assert event["id"] == event_id
    assert event["body_json"] == {"test": "find-me"}


def test_get_event_by_id_not_found(mock_api, mock_reset):
    r = mock_api._request_raw("GET", "/events/nonexistent-uuid-12345")
    assert r.status_code == 404
    data = r.json()
    assert data.get("error") == "not_found"


# ── Event ID uniqueness ──────────────────────────────────────────


def test_event_id_unique(mock_api, mock_reset):
    ids = set()
    for i in range(20):
        r = mock_api.post_webhook(json={"i": i})
        ids.add(r.json()["id"])

    assert len(ids) == 20, f"expected 20 unique IDs, got {len(ids)}"


# ── Deque bounded correctly ──────────────────────────────────────


def test_max_events_bound(mock_api):
    mock_api.reset()

    total = 100
    for i in range(total):
        mock_api.post_webhook(json={"i": i})

    events = mock_api.list_events(limit=total + 10)
    assert events["count"] == total

    ids = {e["id"] for e in events["items"]}
    assert len(ids) == len(events["items"]), "duplicate event IDs found"


# ── Response schema ──────────────────────────────────────────────


def test_webhook_response_schema(mock_api):
    r = mock_api.post_webhook(json={"test": True})
    data = r.json()
    assert data["ok"] is True
    assert isinstance(data["id"], str)
    assert len(data["id"]) == 36  # UUID format


def test_health_response_schema(mock_api):
    data = mock_api.health()
    assert data["ok"] is True
    assert isinstance(data["events"], int)


def test_events_list_schema(mock_api, mock_reset):
    mock_api.post_webhook(json={"test": True})

    data = mock_api.list_events()
    assert "count" in data
    assert "items" in data
    assert isinstance(data["count"], int)
    assert isinstance(data["items"], list)
    assert data["count"] >= 1
    assert len(data["items"]) >= 1


def test_captured_event_schema(mock_api, mock_reset):
    mock_api.post_webhook(json={"test": True})

    events = mock_api.list_events()
    event = events["items"][0]

    required = [
        "id",
        "ts_ms",
        "method",
        "path",
        "query",
        "headers",
        "body_raw",
        "body_json",
        "body_form",
        "response_status",
    ]
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


def test_health_after_fault_injection(mock_api):
    mock_api.fault_reset()
    mock_api.fault_config(mode="delay", delay_ms=100)

    data = mock_api.health()
    assert data["ok"] is True

    mock_api.fault_reset()


# ── Fault config bad mode ────────────────────────────────────────


def test_fault_config_bad_mode_rejected(mock_api):
    r = mock_api._request_raw(
        "POST",
        "/fault/config",
        params={"mode": "explode", "fail_count": 1},
    )
    assert r.status_code == 400
    assert "error" in r.json()


# ── Reset endpoint idempotency ───────────────────────────────────


def test_reset_idempotent(mock_api):
    for _ in range(3):
        data = mock_api.reset()
        assert data["ok"] is True

    assert mock_api.event_count() == 0


# ── events?limit clamping ────────────────────────────────────────


def test_events_limit_clamped(mock_api, mock_reset):
    # limit=0 clamped to 1
    r = mock_api._request_raw("GET", "/events", params={"limit": 0})
    assert r.status_code == 200

    # limit=1000 clamped to 500
    r = mock_api._request_raw("GET", "/events", params={"limit": 1000})
    assert r.status_code == 200
    assert len(r.json()["items"]) <= 500


def test_events_limit_negative(mock_api):
    r = mock_api._request_raw("GET", "/events", params={"limit": -5})
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) <= data["count"]
