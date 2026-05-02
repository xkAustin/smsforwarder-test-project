import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]


def test_webhook_receive_json_body(mock_api, mock_reset):
    payload = {"msg": "pytest", "level": "info"}
    mock_api.post_webhook(json=payload)

    assert mock_api.wait_for_count(1), "timed out waiting for webhook event"

    data = mock_api.list_events(limit=5)

    assert data["count"] == 1
    event = data["items"][0]

    assert event["method"] == "POST"
    assert event["path"] == "/webhook"

    headers = event["headers"]
    assert headers["content-type"].startswith("application/json")

    assert event["body_json"] == payload
