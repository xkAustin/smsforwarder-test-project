import requests
import pytest

pytestmark = pytest.mark.manual

def post(base_url: str, path: str, **kwargs):
    r = requests.post(f"{base_url}{path}", timeout=3, **kwargs)
    r.raise_for_status()
    return r.json()


def get_events(base_url: str, limit=10):
    r = requests.get(f"{base_url}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()


def test_no_retry_on_http_500(mock_base, event_trigger, mock_counter, wait_for_event):
    """
    验证：Webhook 返回 500 时，SmsForwarder 不进行重试
    （预期：仅收到 1 次请求）
    """

    # 清空状态
    post(mock_base, "/reset")
    post(mock_base, "/fault/reset")

    # 设置：第一次 webhook 返回 500
    post(mock_base, "/fault/config", params={"mode": "fail", "fail_count": 1})

    before = mock_counter()
    marker = "[MANUAL] no-retry-500"
    result = event_trigger.send_webhook_form(
        {"from": "10086", "content": f"{marker} hello", "timestamp": "0"},
        allow_fail=True,
    )

    ok = wait_for_event(before_count=before, timeout_s=10)
    assert ok, f"timeout waiting for webhook event (mode={result.mode})"

    events = get_events(mock_base, limit=10)

    assert events["count"] == 1, (
        "Expected no retry on HTTP 500, " f"but got {events['count']} requests"
    )


def test_no_retry_on_timeout(mock_base, event_trigger, mock_counter, wait_for_event):
    """
    验证：Webhook 请求超时时，SmsForwarder 不进行重试
    """

    post(mock_base, "/reset")
    post(mock_base, "/fault/reset")

    # 设置：强制延迟 10s（超过客户端 timeout）
    post(mock_base, "/fault/config", params={"mode": "delay", "delay_ms": 10000})

    before = mock_counter()
    marker = "[MANUAL] no-retry-timeout"
    result = event_trigger.send_webhook_form(
        {"from": "10086", "content": f"{marker} hello", "timestamp": "0"},
        allow_fail=True,
    )

    ok = wait_for_event(before_count=before, timeout_s=12)
    assert ok, f"timeout waiting for webhook event (mode={result.mode})"

    events = get_events(mock_base, limit=10)

    assert events["count"] == 1, (
        "Expected no retry on timeout, " f"but got {events['count']} requests"
    )
