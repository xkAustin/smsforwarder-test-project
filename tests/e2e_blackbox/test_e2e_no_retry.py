import time
import requests
import pytest

from tests.utils.http_payload import parse_event_body

pytestmark = pytest.mark.e2e


def test_e2e_no_retry_on_http_500(
    event_trigger, mock_base, mock_reset, mock_counter, get_latest_event, wait_for_event
):
    """
    E2E-010: Webhook 返回 500 时，不发生重试（观测：事件只出现 1 次）
    前置：SmsForwarder 已配置短信规则，命中包含 [E2E] marker 的短信，并转发到 mock webhook
    """
    # 1) 配置：接下来 1 次请求返回 500
    requests.post(f"{mock_base}/fault/reset", timeout=3).raise_for_status()
    requests.post(
        f"{mock_base}/fault/config", params={"mode": "fail", "fail_count": 1}, timeout=3
    ).raise_for_status()

    before = mock_counter()

    marker = "[E2E] no-retry-500"
    result = event_trigger.send_sms("10086", f"{marker} hello", allow_fail=True)

    # 2) 等到第一次 webhook 到达（哪怕是 500，也会被记录为一次 events）
    ok = wait_for_event(before_count=before, timeout_s=12)
    assert ok, "timeout waiting first webhook event"

    # 3) 再等一段“可能发生重试”的窗口，确认没有新增
    time.sleep(6)
    after = mock_counter()
    assert (
        after == before + 1
    ), f"expected no retry on 500 (mode={result.mode}), before={before}, after={after}"

    # 4) 黑盒断言：payload 必须包含 marker

    event = get_latest_event()
    body_text, body_json, form = parse_event_body(event)
    assert marker in body_text


def test_e2e_no_retry_on_timeout(
    event_trigger, mock_base, mock_reset, mock_counter, get_latest_event, wait_for_event
):
    """
    E2E-011: Webhook 超时/慢响应时，不发生重试（观测：事件只出现 1 次）
    用 mock server delay 模拟。
    """
    requests.post(f"{mock_base}/fault/reset", timeout=3).raise_for_status()
    # 延迟 10s：模拟慢响应（触发方可能会 timeout）
    requests.post(
        f"{mock_base}/fault/config",
        params={"mode": "delay", "delay_ms": 10000},
        timeout=3,
    ).raise_for_status()

    before = mock_counter()

    marker = "[E2E] no-retry-timeout"
    result = event_trigger.send_sms("10086", f"{marker} hello", allow_fail=True)

    # delay=10s，等事件出现要更久一点
    ok = wait_for_event(before_count=before, timeout_s=20)
    assert ok, "timeout waiting first webhook event under delay"

    time.sleep(6)
    after = mock_counter()
    assert (
        after == before + 1
    ), f"expected no retry on timeout (mode={result.mode}), before={before}, after={after}"

    event = get_latest_event()
    body_text, body_json, form = parse_event_body(event)
    assert marker in body_text
