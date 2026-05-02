import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.performance]


def test_e2e_throughput_smoke(event_trigger, mock_reset, mock_api, wait_for_event):
    before = mock_api.event_count()
    marker = "[E2E] perf-smoke"
    payloads = [f"{marker} #{i}" for i in range(3)]

    result = event_trigger.send_sms_batch("10086", payloads)

    ok = wait_for_event(before_count=before, expected_delta=len(payloads), timeout_s=15)
    assert ok, f"timeout waiting for throughput events (mode={result.mode})"
