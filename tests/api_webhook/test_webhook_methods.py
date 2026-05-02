"""Tests for HTTP method variety and protocol features.

SmsForwarder webhook supports GET (query params), POST/PUT/PATCH (JSON/form),
custom headers, HMAC-SHA256 signing, and Basic Auth. These tests validate
the mock server correctly captures all these protocol variations.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse

import requests


def get_events(base_url: str, limit: int = 10):
    r = requests.get(f"{base_url}/events", params={"limit": limit}, timeout=3)
    r.raise_for_status()
    return r.json()


# ── HTTP method variety ──────────────────────────────────────────


def test_webhook_get_with_query_params(mock_base, mock_reset):
    """GET /webhook?from=13800138000&content=test&timestamp=123&sign=abc"""
    params = {
        "from": "13800138000",
        "content": "test sms body",
        "timestamp": str(int(time.time())),
        "sign": "fake-signature",
    }
    r = requests.get(f"{mock_base}/webhook", params=params, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    event = events["items"][0]
    assert event["method"] == "GET"
    assert event["query"]["from"] == "13800138000"
    assert event["query"]["content"] == "test sms body"
    assert "sign" in event["query"]


def test_webhook_put_json(mock_base, mock_reset):
    """PUT /webhook with JSON body."""
    payload = {"msg": "put-test", "level": "warn"}
    r = requests.put(f"{mock_base}/webhook", json=payload, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    event = events["items"][0]
    assert event["method"] == "PUT"
    assert event["body_json"] == payload


def test_webhook_patch_json(mock_base, mock_reset):
    """PATCH /webhook with JSON body."""
    payload = {"msg": "patch-test"}
    r = requests.patch(f"{mock_base}/webhook", json=payload, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    event = events["items"][0]
    assert event["method"] == "PATCH"
    assert event["body_json"] == payload


def test_webhook_delete(mock_base, mock_reset):
    """DELETE /webhook — should be captured like any other method."""
    r = requests.delete(f"{mock_base}/webhook", timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    assert events["count"] == 1
    assert events["items"][0]["method"] == "DELETE"


# ── Form-encoded content ─────────────────────────────────────────


def test_webhook_form_urlencoded(mock_base, mock_reset):
    """SmsForwarder default: x-www-form-urlencoded with from/content/timestamp."""
    form = {"from": "10086", "content": "form test message", "timestamp": "0"}
    r = requests.post(f"{mock_base}/webhook", data=form, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    event = events["items"][0]
    assert event["method"] == "POST"
    assert event["body_form"] is not None
    assert event["body_form"]["from"] == "10086"
    assert event["body_form"]["content"] == "form test message"


# ── Custom headers ───────────────────────────────────────────────


def test_webhook_custom_headers(mock_base, mock_reset):
    """SmsForwarder allows custom headers; verify they are captured."""
    custom = {
        "X-Custom-Header": "custom-value",
        "X-Another": "another-value",
    }
    r = requests.post(
        f"{mock_base}/webhook",
        json={"test": True},
        headers=custom,
        timeout=3,
    )
    assert r.status_code == 200

    events = get_events(mock_base)
    headers = events["items"][0]["headers"]
    assert headers["x-custom-header"] == "custom-value"
    assert headers["x-another"] == "another-value"


# ── HMAC-SHA256 signature simulation ─────────────────────────────


def test_webhook_with_hmac_signature(mock_base, mock_reset):
    """Simulate what SmsForwarder sends: timestamp + HMAC-SHA256 sign in URL."""
    secret = b"test-secret-key"
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret.decode()}"
    mac = hmac.new(secret, string_to_sign.encode(), hashlib.sha256)
    sign_bytes = base64.b64encode(mac.digest()).rstrip(b"\n")
    sign = urllib.parse.quote(sign_bytes.decode())

    params = {
        "from": "13800138000",
        "content": "signed message",
        "timestamp": timestamp,
        "sign": sign,
    }
    r = requests.get(f"{mock_base}/webhook", params=params, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    event = events["items"][0]
    assert event["query"]["timestamp"] == timestamp
    assert event["query"]["sign"] == sign


# ── Basic Auth simulation ────────────────────────────────────────


def test_webhook_basic_auth_header(mock_base, mock_reset):
    """SmsForwarder supports Basic Auth; verify Authorization header captured."""
    r = requests.post(
        f"{mock_base}/webhook",
        json={"auth": "test"},
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
        timeout=3,
    )
    assert r.status_code == 200

    events = get_events(mock_base)
    headers = events["items"][0]["headers"]
    assert headers["authorization"] == "Basic dXNlcjpwYXNz"


# ── Unicode and encoding ─────────────────────────────────────────


def test_webhook_chinese_content(mock_base, mock_reset):
    """SmsForwarder handles Chinese SMS; verify UTF-8 content captured correctly."""
    payload = {"content": "你好世界 🌍 テスト"}
    r = requests.post(f"{mock_base}/webhook", json=payload, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    event = events["items"][0]
    # Raw body has JSON-escaped unicode (ensure_ascii default); check parsed JSON
    assert event["body_json"]["content"] == "你好世界 🌍 テスト"


def test_webhook_empty_body(mock_base, mock_reset):
    """POST with no body at all."""
    r = requests.post(f"{mock_base}/webhook", timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    event = events["items"][0]
    assert event["method"] == "POST"
    assert event["body_raw"] == ""
    assert event["body_json"] is None


# ── Template variable simulation ─────────────────────────────────


def test_webhook_simulated_template_vars(mock_base, mock_reset):
    """Simulate SmsForwarder template substitution: [from], [content], etc.

    When smsTemplate is configured, SmsForwarder replaces tags like
    [from], [content], [receive_time], [device_mark], [app_version],
    [card_slot], [org_content] in the webhook params.
    """
    form = {
        "from": "13900001111",
        "content": "Balance: 123.45 CNY",
        "timestamp": str(int(time.time())),
        "device_mark": "Pixel-7",
        "app_version": "3.3.3",
        "card_slot": "SIM1_ChinaMobile",
    }
    r = requests.post(f"{mock_base}/webhook", data=form, timeout=3)
    assert r.status_code == 200

    events = get_events(mock_base)
    event = events["items"][0]
    assert event["body_form"] is not None
    f = event["body_form"]
    assert f["from"] == "13900001111"
    assert "Balance" in f["content"]
    assert f["device_mark"] == "Pixel-7"
    assert f["app_version"] == "3.3.3"
