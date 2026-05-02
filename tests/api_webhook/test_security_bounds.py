import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]


def test_fault_config_bounds(mock_api):
    mock_api.fault_reset()

    # delay_ms clamped to MAX_DELAY_MS (60000)
    res_delay = mock_api.fault_config(mode="delay", delay_ms=100000)
    assert res_delay["delay_ms"] == 60000

    # fail_count clamped to MAX_FAIL_COUNT (10000)
    res_fail = mock_api.fault_config(mode="fail", fail_count=20000)
    assert res_fail["fail_count_left"] == 10000

    # negatives clamped to 0
    res_neg = mock_api.fault_config(mode="delay", delay_ms=-100, fail_count=-5)
    assert res_neg["delay_ms"] == 0
    assert res_neg["fail_count_left"] == 0
