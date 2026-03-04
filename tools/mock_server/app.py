from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote_plus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@dataclass
class CapturedEvent:
    id: str
    ts_ms: int
    method: str
    path: str
    query: Dict[str, Any]
    headers: Dict[str, str]
    body_raw: str
    body_json: Optional[Any]
    body_form: Optional[dict]
    response_status: int


MAX_EVENTS = 5000  # 防止内存无限增长
EVENTS: deque[CapturedEvent] = deque(maxlen=MAX_EVENTS)

# ---- Fault Injection (可控故障注入) ----
FAULT_MODE = "ok"  # ok / fail / delay
FAIL_COUNT_LEFT = 0  # 还要失败多少次
DELAY_MS = 0  # 每次延迟多少毫秒


app = FastAPI(title="SmsForwarder Mock Webhook Server", version="0.1.0")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_decode(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("utf-8", errors="replace")


def _try_parse_json(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None


def _normalize_headers(h: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in h.items():
        out[k.lower()] = v
    return out


@app.get("/health")
def health():
    return {"ok": True, "events": len(EVENTS)}


@app.post("/reset")
def reset():
    EVENTS.clear()
    return {"ok": True}


@app.get("/events")
def list_events(limit: int = 50):
    limit = max(1, min(limit, 500))
    items = [asdict(e) for e in list(EVENTS)[-limit:]]
    return {"count": len(EVENTS), "items": items}


@app.get("/events/{event_id}")
def get_event(event_id: str):
    for e in EVENTS:
        if e.id == event_id:
            return asdict(e)
    return JSONResponse({"error": "not_found"}, status_code=404)


@app.post("/fault/reset")
def fault_reset():
    global FAULT_MODE, FAIL_COUNT_LEFT, DELAY_MS
    FAULT_MODE = "ok"
    FAIL_COUNT_LEFT = 0
    DELAY_MS = 0
    return {"ok": True, "mode": FAULT_MODE}


@app.post("/fault/config")
def fault_config(mode: str = "ok", fail_count: int = 0, delay_ms: int = 0):
    """
    mode:
      - ok: 正常
      - fail: 按 fail_count 次数返回 500
      - delay: 每次延迟 delay_ms 毫秒再返回
    """
    global FAULT_MODE, FAIL_COUNT_LEFT, DELAY_MS
    if mode not in ("ok", "fail", "delay"):
        return JSONResponse({"error": "bad_mode"}, status_code=400)

    FAULT_MODE = mode
    FAIL_COUNT_LEFT = max(0, int(fail_count))
    DELAY_MS = max(0, int(delay_ms))
    return {
        "ok": True,
        "mode": FAULT_MODE,
        "fail_count_left": FAIL_COUNT_LEFT,
        "delay_ms": DELAY_MS,
    }


@app.api_route("/webhook", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def webhook(request: Request):
    raw_bytes = await request.body()
    body_raw = _safe_decode(raw_bytes)

    # 尝试按 JSON 解析（如果不是 JSON 就保留 None）
    body_json = _try_parse_json(body_raw)

    # headers 统一小写，方便后续判断 content-type
    headers_norm = _normalize_headers(dict(request.headers))

    # ---- fault behavior ----
    global FAULT_MODE, FAIL_COUNT_LEFT, DELAY_MS

    if FAULT_MODE == "delay" and DELAY_MS > 0:
        import asyncio

        await asyncio.sleep(DELAY_MS / 1000.0)

    should_fail = False
    if FAULT_MODE == "fail" and FAIL_COUNT_LEFT > 0:
        FAIL_COUNT_LEFT -= 1
        should_fail = True

    # ---- parse x-www-form-urlencoded ----
    body_form = None
    ct = headers_norm.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in ct:
        qs = parse_qs(body_raw, keep_blank_values=True)
        body_form = {k: unquote_plus(v[0]) if v else "" for k, v in qs.items()}

    event = CapturedEvent(
        id=str(uuid.uuid4()),
        ts_ms=_now_ms(),
        method=request.method,
        path=str(request.url.path),
        query=dict(request.query_params),
        headers=headers_norm,
        body_raw=body_raw,
        body_json=body_json,
        body_form=body_form,
        response_status=200,
    )

    EVENTS.append(event)

    if should_fail:
        event.response_status = 500
        return JSONResponse(
            {"ok": False, "id": event.id, "error": "injected_fail"}, status_code=500
        )

    return JSONResponse({"ok": True, "id": event.id})
