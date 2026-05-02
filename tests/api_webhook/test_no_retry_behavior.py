import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]


def test_no_retry_on_http_500(mock_api, event_trigger, wait_for_event):
    mock_api.reset()
    mock_api.fault_reset()

    mock_api.fault_config(mode="fail", fail_count=1)

    before = mock_api.event_count()
    marker = "[no-retry] http-500"
    result = event_trigger.send_webhook_form(
        {"from": "10086", "content": f"{marker} hello", "timestamp": "0"},
        allow_fail=True,
    )

    ok = wait_for_event(before_count=before, timeout_s=10)
    assert ok, f"timeout waiting for webhook event (mode={result.mode})"

    count = mock_api.event_count()
    assert count == 1, f"Expected no retry on HTTP 500, but got {count} requests"


def test_no_retry_on_timeout(mock_api, event_trigger, wait_for_event):
    mock_api.reset()
    mock_api.fault_reset()

    mock_api.fault_config(mode="delay", delay_ms=10000)

    before = mock_api.event_count()
    marker = "[no-retry] timeout"
    result = event_trigger.send_webhook_form(
        {"from": "10086", "content": f"{marker} hello", "timestamp": "0"},
        allow_fail=True,
    )

    ok = wait_for_event(before_count=before, timeout_s=15)
    assert ok, f"timeout waiting for webhook event (mode={result.mode})"

    count = mock_api.event_count()
    assert count == 1, f"Expected no retry on timeout, but got {count} requests"
