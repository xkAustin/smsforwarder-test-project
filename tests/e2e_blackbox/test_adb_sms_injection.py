import time
import requests

from tools.adb.adb_client import AdbClient

import urllib.parse

MOCK_BASE = "http://127.0.0.1:18080"


def reset_mock():
    requests.post(MOCK_BASE + "/reset", timeout=3).raise_for_status()


def get_count():
    r = requests.get(f"{MOCK_BASE}/events", params={"limit": 50}, timeout=3)
    r.raise_for_status()
    return r.json()["count"]


def get_latest_event():
    r = requests.get(f"{MOCK_BASE}/events", params={"limit": 1}, timeout=3)
    r.raise_for_status()
    return r.json()["items"][0]


def pick_emulator_serial(adb: AdbClient) -> str:
    devices = adb.list_devices()
    assert devices.returncode == 0, devices.stderr
    lines = [line.strip() for line in devices.stdout.splitlines() if line.strip()]
    serials = []
    for line in lines[1:]:
        parts = line.split()
        if (
            len(parts) >= 2
            and parts[1] == "device"
            and parts[0].startswith("emulator-")
        ):
            serials.append(parts[0])
    assert (
        serials
    ), f"no emulator devices found. adb output:\n{devices.stdout}\n{devices.stderr}"
    return serials[0]


def dump_recent_events():
    try:
        r = requests.get(f"{MOCK_BASE}/events", params={"limit": 5}, timeout=3)
        print("mock events:", r.text)
    except Exception as e:
        print("failed to read mock events:", e)


def extract_text_from_event(event: dict) -> str:
    """
    从 mock server 捕获的 event 中提取“可读内容”，兼容：
    - JSON body
    - x-www-form-urlencoded
    - 纯文本
    """
    headers = event.get("headers", {})
    ct = (headers.get("content-type") or "").lower()

    # 1) JSON 优先
    if "application/json" in ct and event.get("body_json") is not None:
        # 尽量从常见字段里抽取文本；找不到就把整个 json dump 成字符串
        bj = event["body_json"]
        if isinstance(bj, dict):
            for k in ("content", "text", "message", "body"):
                if k in bj and isinstance(bj[k], str):
                    return bj[k]
        return str(bj)

    raw = event.get("body_raw") or ""

    # 2) 表单编码
    if "application/x-www-form-urlencoded" in ct:
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        # SmsForwarder 里你已经看到 content=... 这个字段
        if "content" in parsed and parsed["content"]:
            return parsed["content"][0]
        # 兜底：把所有字段拼一下
        return "\n".join(f"{k}={v[0] if v else ''}" for k, v in parsed.items())

    # 3) 其他情况：尽量 URL 解码一次再返回
    return urllib.parse.unquote_plus(raw)


def test_adb_can_inject_sms():
    """
    目的：验证测试链路的基础设施
    - pytest 能通过 adb 向 emulator 注入短信
    - （如果 SmsForwarder 已配置好转发）mock server 能观察到请求数增加
    """
    adb = AdbClient(serial=None)  # 如果你的 serial 不同，改这里
    serial = pick_emulator_serial(adb)
    adb = AdbClient(serial=serial)

    # 1) adb 设备可见
    devices = adb.list_devices()
    assert devices.returncode == 0
    assert (
        serial in devices.stdout
    ), f"expected serial {serial} in adb devices output:\n{devices.stdout})"

    # 2) 清空 mock server 记录
    reset_mock()
    before = get_count()

    # 3) 注入短信
    from tools.adb.sms_injector import inject_sms

    res = inject_sms(
        serial=serial,
        phone="10086",
        text="[E2E] case-001 hello from pytest adb",
        mode="mac_cmd",
        mac_cmd="mac",
    )
    assert (
        res.returncode == 0
    ), f"inject failed: rc={res.returncode}, out={res.stdout}, err={res.stderr}"

    # 4) 等待 SmsForwarder 异步转发
    time.sleep(3)

    after = get_count()

    if after < before + 1:
        dump_recent_events()

    # 如果你已经把 SmsForwarder 的短信转发规则配好了，这里应当 +1
    assert (
        after >= before + 1
    ), f"expected at least +1 event, before={before}, after={after}"

    event = get_latest_event()
    text = extract_text_from_event(event)

    assert (
        "[E2E] case-001" in text
    ), f"marker not found, extracted_text={text!r}, raw={event.get('body_raw')!r}"
