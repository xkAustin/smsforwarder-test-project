import sys
from unittest.mock import MagicMock

# Mock fastapi and its submodules before importing from tools.mock_server.app
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

from tools.mock_server.app import _safe_decode

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
    data = b"\xe4\xbd\xa0\xe5\xa5\xbd \xff" # "你好" in UTF-8 + invalid byte
    result = _safe_decode(data)
    assert result.startswith("你好")
    assert result.endswith("\ufffd")

def test_safe_decode_empty_bytes():
    """Test _safe_decode with empty bytes."""
    assert _safe_decode(b"") == ""
