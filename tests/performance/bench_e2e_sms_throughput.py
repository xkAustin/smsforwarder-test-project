from __future__ import annotations

import argparse
import json
import time
from typing import Optional, Dict, Any
import pytest
import requests

from tools.adb.adb_client import AdbClient

pytestmark = [pytest.mark.e2e, pytest.mark.performance]


def reset(mock_base: str, timeout: float) -> None:
    requests.post(f"{mock_base}/reset", timeout=timeout).raise_for_status()
    try:
        requests.post(f"{mock_base}/fault/reset", timeout=timeout).raise_for_status()
    except requests.HTTPError as e:
        # fault/reset might not exist in some versions of mock server; ignore 404/405
        if e.response is not None and e.response.status_code in (404, 405):
            pass
        else:
            raise


def get_count(mock_base: str, timeout: float) -> int:
    r = requests.get(f"{mock_base}/events", params={"limit": 1}, timeout=timeout)
    r.raise_for_status()
    return r.json()["count"]


def wait_until_count(
    mock_base: str, timeout: float, target: int, wait_s: float
) -> bool:
    end = time.time() + wait_s
    while time.time() < end:
        if get_count(mock_base, timeout) >= target:
            return True
        time.sleep(0.2)
    return False


def trigger_http_only(mock_base: str, timeout: float, n: int, marker: str) -> None:
    """
    无设备模式：直接用 HTTP 打 /webhook，作为“环境可跑”的退化链路。
    """
    for i in range(n):
        requests.post(
            f"{mock_base}/webhook",
            json={"marker": marker, "i": i, "ts": time.time()},
            timeout=timeout,
        )


def trigger_adb_sms(serial: str, n: int, marker: str) -> None:
    """
    设备模式：用 ADB 往 emulator 注入短信。
    注意：需要 SmsForwarder 规则配置为命中 marker 并转发到 mock webhook。
    """
    adb = AdbClient(serial=serial)
    for i in range(n):
        msg = f"{marker} #{i} {int(time.time()*1000)}"
        r = adb.send_sms("10086", msg)
        if r.returncode != 0:
            raise RuntimeError(f"adb send_sms failed (serial={serial}): {r.stderr}")


def main():
    ap = argparse.ArgumentParser(
        description="E2E throughput benchmark (device optional)"
    )
    ap.add_argument(
        "--mock-base", default="http://127.0.0.1:18080", help="mock server base url"
    )
    ap.add_argument("--timeout", type=float, default=3.0, help="http timeout seconds")
    ap.add_argument("--n", type=int, default=30, help="number of events to trigger")
    ap.add_argument(
        "--wait", type=float, default=90.0, help="max wait seconds for events to arrive"
    )
    ap.add_argument("--marker", default="[E2E] perf", help="marker in payload/sms text")
    ap.add_argument(
        "--trigger",
        choices=["adb_sms", "http_only"],
        default="adb_sms",
        help="how to trigger events: adb_sms requires Android; http_only requires only mock server",
    )
    ap.add_argument(
        "--adb-serial",
        default="",
        help="adb device serial; if empty, auto-select (prefer emulator-xxxx). Env ADB_SERIAL also works.",
    )
    ap.add_argument("--no-reset", action="store_true", help="do not reset server state")
    args = ap.parse_args()

    if not args.no_reset:
        reset(args.mock_base, args.timeout)

    before = get_count(args.mock_base, args.timeout)

    used_serial: Optional[str] = None

    t0 = time.perf_counter()

    if args.trigger == "http_only":
        trigger_http_only(args.mock_base, args.timeout, args.n, args.marker)
    else:
        # adb_sms: 设备可选（不写死；无设备时优雅跳过）
        if args.adb_serial.strip():
            used_serial = args.adb_serial.strip()
        else:
            try:
                used_serial = AdbClient(serial=None).choose_serial(prefer_emulator=True)
            except RuntimeError:
                adb = AdbClient(serial=None)
                print(
                    json.dumps(
                        {
                            "skipped": True,
                            "reason": "no adb device found in 'device' state",
                            "hint": "start an emulator or use --trigger http_only",
                            "adb_devices_raw": adb.list_devices_raw().stdout,
                        },
                        indent=2,
                    )
                )
                return

        trigger_adb_sms(used_serial, args.n, args.marker)

    target = before + args.n
    ok = wait_until_count(args.mock_base, args.timeout, target, args.wait)

    t1 = time.perf_counter()

    out: Dict[str, Any] = {
        "mock_base": args.mock_base,
        "trigger": args.trigger,
        "adb_serial": used_serial,
        "n": args.n,
        "before": before,
        "target": target,
        "reached_target": ok,
        "duration_s": (t1 - t0),
        "throughput_events_per_s": (args.n / (t1 - t0)) if (t1 - t0) > 0 else 0,
    }

    print(json.dumps(out, indent=2))

    if not ok:
        raise SystemExit(f"timeout: events did not reach {target} within {args.wait}s")


if __name__ == "__main__":
    main()
