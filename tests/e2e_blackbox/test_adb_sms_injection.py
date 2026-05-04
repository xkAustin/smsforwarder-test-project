import pytest

from tests.utils.http_payload import parse_event_body

pytestmark = pytest.mark.e2e


@pytest.mark.e2e
def test_e2e_sms_to_webhook(event_trigger, mock_reset, mock_api, wait_for_event, get_new_events):
    """
    E2E-001: ADB 注入短信 -> SmsForwarder 命中规则 -> Webhook 转发可观测且内容包含 marker
    """
    # 1) 清空 mock server，获取 before
    before = mock_api.event_count()

    # 2) 注入短信（规则需匹配该 marker）
    marker = "[E2E] case-001"
    result = event_trigger.send_sms("10086", f"{marker} hello from pytest")
    assert result.mode in ("adb", "http", "manual")

    # 3) 等待异步转发发生
    ok = wait_for_event(before_count=before, timeout_s=10)
    assert ok, "timeout waiting for webhook event"

    # 4) 取新事件
    cap = get_new_events(before_count=before)
    new_events = cap()
    assert new_events, "no new events"
    event = new_events[-1]

    # 5) 解码后断言
    body_text, body_json, form = parse_event_body(event)

    assert marker in body_text, f"marker not found. body_text: {body_text!r}, form={form}"

    # 6）契约断言
    if form:
        assert form.get("from") == "10086"
        assert "timestamp" in form
        assert marker in form.get("content", "")
