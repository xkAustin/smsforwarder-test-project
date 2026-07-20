
import pytest

from tests.utils.http_payload import parse_event_body

pytestmark = pytest.mark.unit

def test_parse_event_body_json_success():
    event = {
        "headers": {"content-type": "application/json"},
        "body_raw": '{"key": "value", "number": 123}'
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_text == event["body_raw"]
    assert body_json == {"key": "value", "number": 123}
    assert form == {}

def test_parse_event_body_json_case_insensitive():
    event = {
        "headers": {"Content-Type": "APPLICATION/JSON; charset=utf-8"},
        "body_raw": '{"key": "value"}'
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_json == {"key": "value"}

def test_parse_event_body_json_failure():
    event = {
        "headers": {"content-type": "application/json"},
        "body_raw": '{"invalid": json'
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_text == event["body_raw"]
    assert body_json is None
    assert form == {}

def test_parse_event_body_form_success():
    event = {
        "headers": {"content-type": "application/x-www-form-urlencoded"},
        "body_raw": "key1=value1&key2=value2"
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_text == event["body_raw"]
    assert body_json is None
    assert form == {"key1": "value1", "key2": "value2"}

def test_parse_event_body_form_with_content():
    event = {
        "headers": {"content-type": "application/x-www-form-urlencoded"},
        "body_raw": "from=10086&content=Hello+World&timestamp=123456789"
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_text == "Hello World"
    assert body_json is None
    assert form == {"from": "10086", "content": "Hello World", "timestamp": "123456789"}

def test_parse_event_body_form_multiple_values():
    event = {
        "headers": {"content-type": "application/x-www-form-urlencoded"},
        "body_raw": "key=val1&key=val2"
    }
    body_text, body_json, form = parse_event_body(event)
    assert form == {"key": "val2"}

def test_parse_event_body_fallback():
    event = {
        "headers": {"content-type": "text/plain"},
        "body_raw": "just some text"
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_text == "just some text"
    assert body_json is None
    assert form == {}

def test_parse_event_body_missing_headers():
    event = {
        "body_raw": "no headers"
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_text == "no headers"
    assert body_json is None
    assert form == {}

def test_parse_event_body_content_type_underscore():
    event = {
        "headers": {"content_type": "application/json"},
        "body_raw": '{"a": 1}'
    }
    body_text, body_json, form = parse_event_body(event)
    assert body_json == {"a": 1}

def test_parse_event_body_empty():
    event = {}
    body_text, body_json, form = parse_event_body(event)
    assert body_text == ""
    assert body_json is None
    assert form == {}
