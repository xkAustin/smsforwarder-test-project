import time
import requests

BASE_URL = "http://127.0.0.1:18080"


def post(path, **kwargs):
    r = requests.post(f"{BASE_URL}{path}", timeout=3, **kwargs)
    r.raise_for_status()
    return r.json()


def get(path, **kwargs):
    r = requests.get(f"{BASE_URL}{path}", timeout=3, **kwargs)
    r.raise_for_status()
    return r.json()


def test_fault_fail_n_times():
    # 清空事件 + 重置故障
    post("/reset")
    post("/fault/reset")

    # 配置：接下来 2 次 webhook 返回 500
    post("/fault/config", params={"mode": "fail", "fail_count": 2})

    # 第一次：应失败
    r1 = requests.post(f"{BASE_URL}/webhook", json={"n": 1}, timeout=3)
    assert r1.status_code == 500

    # 第二次：应失败
    r2 = requests.post(f"{BASE_URL}/webhook", json={"n": 2}, timeout=3)
    assert r2.status_code == 500

    # 第三次：恢复正常
    r3 = requests.post(f"{BASE_URL}/webhook", json={"n": 3}, timeout=3)
    assert r3.status_code == 200

    # 事件仍应记录 3 条
    events = get("/events", params={"limit": 10})
    assert events["count"] == 3


def test_fault_delay():
    post("/reset")
    post("/fault/reset")

    # 配置：每次延迟 300ms
    post("/fault/config", params={"mode": "delay", "delay_ms": 300})

    t0 = time.time()
    r = requests.post(f"{BASE_URL}/webhook", json={"slow": True}, timeout=3)
    dt = (time.time() - t0) * 1000

    assert r.status_code == 200
    assert dt >= 250  # 给一点误差空间
