import sys
from unittest.mock import MagicMock

# Mock fastapi and its submodules before importing from tools.mock_server.app
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

import pytest  # noqa: E402

from tools.mock_server.app import _normalize_headers, _safe_decode, _try_parse_json  # noqa: E402

pytestmark = pytest.mark.unit


def test_try_parse_json_valid_object():
    """Test _try_parse_json with a valid JSON object."""
    text = '{"key": "value", "int": 123}'
    assert _try_parse_json(text) == {"key": "value", "int": 123}


def test_try_parse_json_valid_list():
    """Test _try_parse_json with a valid JSON list."""
    text = '[1, "two", 3.0]'
    assert _try_parse_json(text) == [1, "two", 3.0]


def test_try_parse_json_valid_primitive():
    """Test _try_parse_json with valid JSON primitives."""
    assert _try_parse_json('"string"') == "string"
    assert _try_parse_json("123") == 123
    assert _try_parse_json("true") is True
    assert _try_parse_json("null") is None


def test_try_parse_json_invalid_json():
    """Test _try_parse_json with invalid JSON."""
    assert _try_parse_json('{"key": "value"') is None  # missing brace
    assert _try_parse_json("not json") is None
    assert _try_parse_json("") is None


def test_normalize_headers_basic():
    """Test _normalize_headers with basic case normalization."""
    headers = {"Content-Type": "application/json", "X-Custom-Header": "Value"}
    expected = {"content-type": "application/json", "x-custom-header": "value"}
    # Wait, looking at the code:
    # def _normalize_headers(h: dict[str, str]) -> dict[str, str]:
    #     out: dict[str, str] = {}
    #     for k, v in h.items():
    #         out[k.lower()] = v
    #     return out
    # It only lowers the KEY, not the value.
    expected = {"content-type": "application/json", "x-custom-header": "Value"}
    assert _normalize_headers(headers) == expected


def test_normalize_headers_already_lower():
    """Test _normalize_headers with already lowercase keys."""
    headers = {"host": "localhost", "user-agent": "test"}
    assert _normalize_headers(headers) == headers


def test_normalize_headers_empty():
    """Test _normalize_headers with empty dict."""
    assert _normalize_headers({}) == {}


def test_safe_decode_valid_utf8():
    """Test _safe_decode with valid UTF-8 byte sequence."""
    data = b"hello world"
    assert _safe_decode(data) == "hello world"


def test_safe_decode_invalid_utf8():
    """Test _safe_decode with invalid UTF-8 byte sequence."""
    # b"\xff" is invalid UTF-8
    data = b"hello \xff world"
    # By default, errors="replace" uses the Unicode replacement character '\ufffd'
    result = _safe_decode(data)
    assert "\ufffd" in result
    assert result.startswith("hello ")
    assert result.endswith(" world")


def test_safe_decode_mixed_sequences():
    """Test _safe_decode with mixed valid and invalid sequences."""
    data = b"\xe4\xbd\xa0\xe5\xa5\xbd \xff"  # "你好" in UTF-8 + invalid byte
    result = _safe_decode(data)
    assert result.startswith("你好")
    assert result.endswith("\ufffd")


def test_safe_decode_empty_bytes():
    """Test _safe_decode with empty bytes."""
    assert _safe_decode(b"") == ""


def test_normalize_headers_mixed_case():
    """Test _normalize_headers with mixed-case keys."""
    headers = {"Content-Type": "application/json", "X-Request-ID": "123"}
    expected = {"content-type": "application/json", "x-request-id": "123"}
    assert _normalize_headers(headers) == expected


def test_normalize_headers_already_lowercase():
    """Test _normalize_headers with already lowercase keys."""
    headers = {"content-type": "application/json", "accept": "*/*"}
    assert _normalize_headers(headers) == headers


def test_normalize_headers_uppercase():
    """Test _normalize_headers with uppercase keys."""
    headers = {"HOST": "localhost", "USER-AGENT": "test"}
    expected = {"host": "localhost", "user-agent": "test"}
    assert _normalize_headers(headers) == expected


def test_try_parse_json_valid():
    """Test _try_parse_json with valid JSON string."""
    text = '{"a": 1, "b": [1, 2, 3]}'
    assert _try_parse_json(text) == {"a": 1, "b": [1, 2, 3]}


def test_try_parse_json_invalid():
    """Test _try_parse_json with invalid JSON string."""
    assert _try_parse_json('{"a": 1,') is None
    assert _try_parse_json("not json") is None


def test_try_parse_json_empty():
    """Test _try_parse_json with empty string."""
    assert _try_parse_json("") is None
