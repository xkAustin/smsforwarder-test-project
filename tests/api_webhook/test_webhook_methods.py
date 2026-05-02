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

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.regression]

# ── HTTP method variety ──────────────────────────────────────────


def test_webhook_get_with_query_params(mock_api, mock_reset):
    params = {
        "from": "13800138000",
        "content": "test sms body",
        "timestamp": str(int(time.time())),
        "sign": "fake-signature",
    }
    mock_api.get_webhook(params=params)

    events = mock_api.list_events()
    assert events["count"] == 1
    event = events["items"][0]
    assert event["method"] == "GET"
    assert event["query"]["from"] == "13800138000"
    assert event["query"]["content"] == "test sms body"
    assert "sign" in event["query"]


@pytest.mark.parametrize(
    "send, method, payload",
    [
        (
            lambda api: api.put_webhook(json={"msg": "put-test", "level": "warn"}),
            "PUT",
            {"msg": "put-test", "level": "warn"},
        ),
        (
            lambda api: api.patch_webhook(json={"msg": "patch-test"}),
            "PATCH",
            {"msg": "patch-test"},
        ),
        (
            lambda api: api.delete_webhook(),
            "DELETE",
            None,
        ),
    ],
)
def test_webhook_json_methods(mock_api, mock_reset, send, method, payload):
    send(mock_api)

    events = mock_api.list_events()
    assert events["count"] == 1
    event = events["items"][0]
    assert event["method"] == method
    if payload is not None:
        assert event["body_json"] == payload


# ── Form-encoded content ─────────────────────────────────────────


def test_webhook_form_urlencoded(mock_api, mock_reset):
    form = {"from": "10086", "content": "form test message", "timestamp": "0"}
    mock_api.post_webhook(data=form)

    events = mock_api.list_events()
    event = events["items"][0]
    assert event["method"] == "POST"
    assert event["body_form"] is not None
    assert event["body_form"]["from"] == "10086"
    assert event["body_form"]["content"] == "form test message"


# ── Custom headers ───────────────────────────────────────────────


def test_webhook_custom_headers(mock_api, mock_reset):
    custom = {
        "X-Custom-Header": "custom-value",
        "X-Another": "another-value",
    }
    mock_api.post_webhook(json={"test": True}, headers=custom)

    events = mock_api.list_events()
    headers = events["items"][0]["headers"]
    assert headers["x-custom-header"] == "custom-value"
    assert headers["x-another"] == "another-value"


# ── HMAC-SHA256 signature simulation ─────────────────────────────


def test_webhook_with_hmac_signature(mock_api, mock_reset):
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
    mock_api.get_webhook(params=params)

    events = mock_api.list_events()
    event = events["items"][0]
    assert event["query"]["timestamp"] == timestamp
    assert event["query"]["sign"] == sign


# ── Basic Auth simulation ────────────────────────────────────────


def test_webhook_basic_auth_header(mock_api, mock_reset):
    mock_api.post_webhook(
        json={"auth": "test"},
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )

    events = mock_api.list_events()
    headers = events["items"][0]["headers"]
    assert headers["authorization"] == "Basic dXNlcjpwYXNz"


# ── Unicode and encoding ─────────────────────────────────────────


def test_webhook_chinese_content(mock_api, mock_reset):
    payload = {"content": "你好世界 🌍 テスト"}
    mock_api.post_webhook(json=payload)

    events = mock_api.list_events()
    event = events["items"][0]
    assert event["body_json"]["content"] == "你好世界 🌍 テスト"


def test_webhook_empty_body(mock_api, mock_reset):
    mock_api.post_webhook()

    events = mock_api.list_events()
    event = events["items"][0]
    assert event["method"] == "POST"
    assert event["body_raw"] == ""
    assert event["body_json"] is None


# ── Template variable simulation ─────────────────────────────────


def test_webhook_simulated_template_vars(mock_api, mock_reset):
    form = {
        "from": "13900001111",
        "content": "Balance: 123.45 CNY",
        "timestamp": str(int(time.time())),
        "device_mark": "Pixel-7",
        "app_version": "3.3.3",
        "card_slot": "SIM1_ChinaMobile",
    }
    mock_api.post_webhook(data=form)

    events = mock_api.list_events()
    event = events["items"][0]
    assert event["body_form"] is not None
    f = event["body_form"]
    assert f["from"] == "13900001111"
    assert "Balance" in f["content"]
    assert f["device_mark"] == "Pixel-7"
    assert f["app_version"] == "3.3.3"
