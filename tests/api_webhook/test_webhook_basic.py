import time
import requests


BASE_URL = "http://127.0.0.1:18080"


def reset_events():
    r = requests.post(f"{BASE_URL}/reset", timeout=3)
    r.raise_for_status()


def get_events(limit=10):
    r = requests.get(f"{BASE_URL}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()


def test_webhook_receive_json_body():
    """
    验证：
    - webhook 能收到 POST 请求
    - JSON body 能被正确解析
    """

    reset_events()

    # 模拟一次“转发请求”
    payload = {"msg": "pytest", "level": "info"}
    r = requests.post(
        f"{BASE_URL}/webhook",
        json=payload,
        timeout=3,
    )
    r.raise_for_status()

    # 给 server 一点处理时间（真实场景是异步）
    time.sleep(0.2)

    data = get_events(limit=5)

    assert data["count"] == 1
    event = data["items"][0]

    assert event["method"] == "POST"
    assert event["path"] == "/webhook"

    # Header 断言
    headers = event["headers"]
    assert headers["content-type"].startswith("application/json")

    # Body 断言
    assert event["body_json"] == payload

