import requests
import pytest

def get_events(base_url: str, limit=10):
    r = requests.get(f"{base_url}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()

def test_malformed_json_body(mock_base, mock_reset):
    """
    Test that the server handles malformed JSON correctly.
    It should return 200 (as per current implementation) but body_json should be None.
    """

    malformed_json = "{'a': 1,}" # Invalid JSON (single quotes, trailing comma)

    r = requests.post(
        f"{mock_base}/webhook",
        data=malformed_json,
        headers={"Content-Type": "application/json"},
        timeout=3,
    )
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    event = events["items"][0]

    assert event["body_json"] is None
    assert event["body_raw"] == malformed_json

def test_large_payload(mock_base, mock_reset):
    """
    Test handling of large payloads.
    """

    # 500KB payload (to avoid potential memory issues in CI, but large enough to test)
    large_payload = {"data": "x" * 500 * 1024}

    r = requests.post(
        f"{mock_base}/webhook",
        json=large_payload,
        timeout=10,
    )
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    event = events["items"][0]

    assert event["body_json"]["data"] == large_payload["data"]

def test_empty_content_type(mock_base, mock_reset):
    """
    Test request with an empty Content-Type header.
    When Content-Type is empty, the server should still capture the raw body correctly.
    """

    payload = "some raw data"

    # requests usually defaults to None for data=string unless configured
    r = requests.post(
        f"{mock_base}/webhook",
        data=payload,
        headers={"Content-Type": ""}, # Explicitly remove it if requests adds it? No, requests shouldn't add it for string.
        # Actually requests adds 'application/x-www-form-urlencoded' for dict, but for string it might not.
        # To be safe, we can manually set it to empty string or check what happens.
        # Let's just pass data and see.
        timeout=3,
    )
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    event = events["items"][0]

    # Check that body is captured correctly even with empty content type
    assert event["body_raw"] == payload
