import pytest
from tests.utils.http_payload import parse_event_body

pytestmark = pytest.mark.manual


@pytest.mark.e2e
def test_e2e_sms_to_webhook(
    adb, mock_reset, mock_counter, wait_for_event, get_new_events
):
    """
    E2E-001: ADB 注入短信 -> SmsForwarder 命中规则 -> Webhook 转发可观测且内容包含 marker
    """
    # 1) adb 设备可见
    devices = adb.list_devices()
    assert devices.returncode == 0
    assert adb.serial in devices.stdout

    # 2) 清空 mock server，获取 before
    before = mock_counter()

    # 3) 注入短信（规则需匹配该 marker）
    marker = "[E2E] case-001"
    r = adb.send_sms("10086", f"{marker} hello from pytest adb")
    assert r.returncode == 0, r.stderr

    # 4) 等待异步转发发生
    ok = wait_for_event(before_count=before, timeout_s=10)
    assert ok, "timeout waiting for webhook event"

    # 5) 取新事件
    cap = get_new_events(before_count=before)
    new_events = cap()
    assert new_events, "no new events"
    event = new_events[-1]

    # 6) 解码后断言
    body_text, body_json, form = parse_event_body(event)

    assert (
        marker in body_text
    ), f"marker not found. body_text: {body_text!r}, form={form}"

    # 7）契约断言
    if form:
        assert form.get("from") == "10086"
        assert "timestamp" in form
        assert marker in form.get("content", "")
