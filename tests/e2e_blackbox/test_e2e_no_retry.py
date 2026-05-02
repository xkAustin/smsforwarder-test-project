import pytest

from tests.utils.http_payload import parse_event_body

pytestmark = pytest.mark.e2e


def test_e2e_no_retry_on_http_500(
    event_trigger, mock_api, mock_reset, get_latest_event, wait_for_event
):
    """
    E2E-010: Webhook returns 500, no retry occurs (observation: event appears only once).
    Prerequisite: SmsForwarder configured with SMS rules matching [E2E] marker,
    forwarding to mock webhook.
    """
    mock_api.fault_config(mode="fail", fail_count=1)

    before = mock_api.event_count()

    marker = "[E2E] no-retry-500"
    result = event_trigger.send_sms("10086", f"{marker} hello", allow_fail=True)

    # Wait for first webhook event (even a 500 is recorded as one event)
    ok = wait_for_event(before_count=before, timeout_s=12)
    assert ok, "timeout waiting first webhook event"

    # Wait for a "retry window" and confirm no additional events arrived
    ok = mock_api.wait_for_count(before + 2, timeout_s=6)
    assert not ok, (
        f"expected no retry on 500 (mode={result.mode}), before={before}, after={mock_api.event_count()}"
    )

    # Black-box assertion: payload must contain marker
    event = get_latest_event()
    body_text, body_json, form = parse_event_body(event)
    assert marker in body_text


def test_e2e_no_retry_on_timeout(
    event_trigger, mock_api, mock_reset, get_latest_event, wait_for_event
):
    """
    E2E-011: Webhook timeout/slow response, no retry occurs (observation: event appears only once).
    Uses mock server delay to simulate.
    """
    # Simulate slow response with 10s delay
    mock_api.fault_config(mode="delay", delay_ms=10000)

    before = mock_api.event_count()

    marker = "[E2E] no-retry-timeout"
    result = event_trigger.send_sms("10086", f"{marker} hello", allow_fail=True)

    # delay=10s, wait longer for events to arrive
    ok = wait_for_event(before_count=before, timeout_s=20)
    assert ok, "timeout waiting first webhook event under delay"

    # Wait for a "retry window" and confirm no additional events arrived
    ok = mock_api.wait_for_count(before + 2, timeout_s=6)
    assert not ok, (
        f"expected no retry on timeout (mode={result.mode}), before={before}, after={mock_api.event_count()}"
    )

    event = get_latest_event()
    body_text, body_json, form = parse_event_body(event)
    assert marker in body_text
