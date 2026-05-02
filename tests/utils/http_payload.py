from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs


def parse_event_body(
    event: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, str]]:
    """
    返回:
      - body_text: 方便直接包含断言的“文本视图”
      - body_json: 如果能解析为 JSON，则返回 dict，否则 None
      - form: 如果是 x-www-form-urlencoded，则返回扁平 dict，否则 {}
    """
    headers = event.get("headers", {}) or {}
    ctype = (headers.get("content-type") or headers.get("content_type") or "").lower()
    raw = event.get("body_raw") or ""

    # 1) JSON
    if "application/json" in ctype:
        try:
            return raw, json.loads(raw), {}
        except Exception:
            return raw, None, {}

    # 2) Form
    if "application/x-www-form-urlencoded" in ctype:
        qs = parse_qs(raw, keep_blank_values=True)
        form = {k: (v[-1] if isinstance(v, list) and v else "") for k, v in qs.items()}

        # SmsForwarder 的短信转发里你已经看到有 from/content/timestamp 等字段
        # 我们把 content 作为主要文本视图（如果没有，就回退 raw）
        body_text = form.get("content") or raw
        return body_text, None, form

    # 3) 其他：直接返回 raw
    return raw, None, {}
