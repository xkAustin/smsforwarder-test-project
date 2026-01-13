import time
import requests

BASE_URL = "http://127.0.0.1:18080"


def post(path, **kwargs):
    r = requests.post(f"{BASE_URL}{path}", timeout=3, **kwargs)
    r.raise_for_status()
    return r.json()


def get_events(limit=10):
    r = requests.get(f"{BASE_URL}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()


def test_no_retry_on_http_500():
    """
    验证：Webhook 返回 500 时，SmsForwarder 不进行重试
    （预期：仅收到 1 次请求）
    """

    # 清空状态
    post("/reset")
    post("/fault/reset")

    # 设置：第一次 webhook 返回 500
    post("/fault/config", params={"mode": "fail", "fail_count": 1})

    # ⚠️ 注意：
    # 这里不再用 requests.post 模拟，
    # 而是由真实 SmsForwarder 触发
    # 所以这里只做等待和断言

    time.sleep(5)  # 等待你在手机上触发一次转发

    events = get_events(limit=10)

    assert events["count"] == 1, (
        "Expected no retry on HTTP 500, " f"but got {events['count']} requests"
    )


def test_no_retry_on_timeout():
    """
    验证：Webhook 请求超时时，SmsForwarder 不进行重试
    """

    post("/reset")
    post("/fault/reset")

    # 设置：强制延迟 10s（超过客户端 timeout）
    post("/fault/config", params={"mode": "delay", "delay_ms": 10000})

    time.sleep(5)  # 等待真实触发

    events = get_events(limit=10)

    assert events["count"] == 1, (
        "Expected no retry on timeout, " f"but got {events['count']} requests"
    )
