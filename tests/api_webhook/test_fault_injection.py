import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]


def test_fault_fail_n_times(mock_api):
    mock_api.reset()
    mock_api.fault_reset()

    mock_api.fault_config(mode="fail", fail_count=2)

    r1 = mock_api.post_webhook(json={"n": 1}, allow_fail=True)
    assert r1.status_code == 500

    r2 = mock_api.post_webhook(json={"n": 2}, allow_fail=True)
    assert r2.status_code == 500

    r3 = mock_api.post_webhook(json={"n": 3})
    assert r3.status_code == 200

    events = mock_api.list_events(limit=10)
    assert events["count"] == 3


def test_fault_delay(mock_api):
    mock_api.reset()
    mock_api.fault_reset()

    mock_api.fault_config(mode="delay", delay_ms=300)

    import time

    t0 = time.time()
    r = mock_api.post_webhook(json={"slow": True})
    dt = (time.time() - t0) * 1000

    assert r.status_code == 200
    assert dt >= 250
