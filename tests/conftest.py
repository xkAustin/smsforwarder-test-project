import os
import time
import requests
import pytest

from tools.adb.adb_client import AdbClient


def pick_adb_serial(prefer_emulator: bool = True) -> str:
    """
    自动选择一个可用 adb device（优先 emulator，其次真机）。
    过滤掉 offline/unauthorized 等状态。
    """
    import subprocess

    p = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"adb devices failed: {p.stderr}")

    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    devs = []
    for ln in lines[1:]:
        parts = ln.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state == "device":
            devs.append(serial)

    if not devs:
        raise RuntimeError(
            "no usable adb device found. "
            "Make sure emulator/phone is connected and authorized (state should be 'device')."
        )

    if prefer_emulator:
        for d in devs:
            if d.startswith("emulator-"):
                return d

    return devs[0]


def pytest_addoption(parser):
    parser.addoption(
        "--adb-serial",
        action="store",
        default=os.getenv("ADB_SERIAL", ""),
        help="ADB device serial. If empty, auto-pick from `adb devices`.",
    )
    parser.addoption(
        "--mock-base",
        action="store",
        default=os.getenv("MOCK_BASE", "http://127.0.0.1:18080"),
        help="Mock server base url, e.g. http://127.0.0.1:18080",
    )
    parser.addoption(
        "--e2e-wait",
        action="store",
        type=float,
        default=float(os.getenv("E2E_WAIT", "3")),
        help="Deprecated: prefer wait_for_event; kept for compatibility.",
    )


@pytest.fixture(scope="session")
def adb(request):
    serial = (request.config.getoption("--adb-serial") or "").strip()
    if not serial:
        serial = pick_adb_serial(prefer_emulator=True)

    client = AdbClient(serial=serial)

    # 设备不在线就直接报错
    devices = client.list_devices()
    if devices.returncode != 0:
        raise RuntimeError(f"adb devices failed: {devices.stderr}")

    if serial not in devices.stdout:
        raise RuntimeError(
            f"selected adb serial '{serial}' not found in `adb devices` output:\n{devices.stdout}"
        )

    return client


@pytest.fixture(scope="session")
def mock_base(request):
    return request.config.getoption("--mock-base")


def _post_ok(url: str, *, timeout: float = 3.0) -> None:
    r = requests.post(url, timeout=timeout)
    r.raise_for_status()


def _get_json(url: str, *, params=None, timeout: float = 3.0) -> dict:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


@pytest.fixture()
def mock_reset(mock_base):
    _post_ok(f"{mock_base}/reset", timeout=3)

    try:
        _post_ok(f"{mock_base}/fault/reset", timeout=3)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 405):
            pass
        else:
            raise

    yield


def get_count(mock_base: str) -> int:
    j = _get_json(f"{mock_base}/events", params={"limit": 1}, timeout=3)
    return int(j["count"])


@pytest.fixture()
def mock_counter(mock_base):
    return lambda: get_count(mock_base)


@pytest.fixture()
def get_latest_event(mock_base):
    def _inner():
        j = _get_json(f"{mock_base}/events", params={"limit": 1}, timeout=3)
        items = j.get("items", [])
        if not items:
            raise AssertionError("no events captured yet")
        return items[-1]

    return _inner


@pytest.fixture(scope="session")
def e2e_wait(request):
    return request.config.getoption("--e2e-wait")


def wait_until(predicate, timeout_s=10.0, interval_s=0.2):
    end = time.time() + float(timeout_s)
    while time.time() < end:
        if predicate():
            return True
        time.sleep(float(interval_s))
    return False


@pytest.fixture()
def wait_for_event(mock_base):
    """
    等待 events count 从 before_count 增加到 before_count + expected_delta。
    默认 expected_delta=1。
    """

    def _wait(
        before_count: int, expected_delta: int = 1, timeout_s: float = 10.0
    ) -> bool:
        target = before_count + expected_delta
        return wait_until(lambda: get_count(mock_base) >= target, timeout_s=timeout_s)

    return _wait


@pytest.fixture()
def get_new_events(mock_base):
    """
    给定 before_count，返回一个函数：拉取新增事件列表（从旧 count 之后的新增部分）
    注意：/events?limit=xxx 只返回最近 limit 条，因此 limit 必须 >= 新增数量，否则会截断。
    """

    def _factory(before_count: int):
        def _inner(limit: int = 50):
            j = _get_json(f"{mock_base}/events", params={"limit": limit}, timeout=3)
            total = int(j["count"])
            new_count = total - int(before_count)
            if new_count <= 0:
                return []
            items = j.get("items", [])

            # 如果新增数量超过了 items 数量，说明 limit 不够导致被截断
            if new_count > len(items):
                raise AssertionError(
                    f"new_count={new_count} exceeds fetched items={len(items)}. "
                    f"Increase limit (current limit={limit})."
                )
            return items[-new_count:]

        return _inner

    return _factory
