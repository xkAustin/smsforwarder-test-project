import json

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]


def test_malformed_json_body(mock_api, mock_reset):
    malformed_json = "{'a': 1,}"  # Invalid JSON (single quotes, trailing comma)

    r = mock_api.request_webhook(
        method="POST",
        data=malformed_json,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200

    events = mock_api.list_events()
    assert events["count"] == 1
    event = events["items"][0]

    assert event["body_json"] is None
    assert event["body_raw"] == malformed_json


def test_large_payload(mock_api, mock_reset):
    large_payload = {"data": "x" * 500 * 1024}

    r = mock_api.request_webhook(
        method="POST",
        data=json.dumps(large_payload),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    assert r.status_code == 200

    events = mock_api.list_events()
    assert events["count"] == 1
    event = events["items"][0]

    assert event["body_json"]["data"] == large_payload["data"]


def test_empty_content_type(mock_api, mock_reset):
    payload = "some raw data"

    r = mock_api.request_webhook(
        method="POST",
        data=payload,
        headers={"Content-Type": ""},
    )
    assert r.status_code == 200

    events = mock_api.list_events()
    assert events["count"] == 1
    event = events["items"][0]

    assert event["body_raw"] == payload
