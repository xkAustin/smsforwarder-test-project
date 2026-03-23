import requests

def post(base_url: str, path: str, **kwargs):
    r = requests.post(f"{base_url}{path}", timeout=3, **kwargs)
    r.raise_for_status()
    return r.json()

def test_fault_config_bounds(mock_base):
    # 重置故障
    post(mock_base, "/fault/reset")

    # 测试延迟上限 (MAX_DELAY_MS = 60000)
    res_delay = post(mock_base, "/fault/config", params={"mode": "delay", "delay_ms": 100000})
    assert res_delay["delay_ms"] == 60000

    # 测试失败次数上限 (MAX_FAIL_COUNT = 10000)
    res_fail = post(mock_base, "/fault/config", params={"mode": "fail", "fail_count": 20000})
    assert res_fail["fail_count_left"] == 10000

    # 测试负数 (应被 max(0, ...) 处理)
    res_neg = post(mock_base, "/fault/config", params={"mode": "delay", "delay_ms": -100, "fail_count": -5})
    assert res_neg["delay_ms"] == 0
    assert res_neg["fail_count_left"] == 0
