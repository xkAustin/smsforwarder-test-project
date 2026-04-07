import os
import time
import socket
import subprocess
import signal
import requests
import pytest

from tools.adb.adb_client import AdbClient
from tests.utils.trigger import EventTrigger, TriggerConfig


def _ensure_no_proxy(hosts: str) -> None:
    targets = [h.strip() for h in hosts.split(",") if h.strip()]
    for key in ("NO_PROXY", "no_proxy"):
        current = os.getenv(key, "")
        parts = [p.strip() for p in current.split(",") if p.strip()] if current else []
        for host in targets:
            if host not in parts:
                parts.append(host)
        os.environ[key] = ",".join(parts)


_ensure_no_proxy("127.0.0.1,localhost")


def _wait_port(host: str, port: int, timeout: float = 10.0) -> None:
    """Wait until TCP port is accepting connections."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Server not ready on {host}:{port} after {timeout}s")


def _wait_health(url: str, timeout: float = 10.0) -> None:
    end = time.time() + timeout
    last_error = None
    while time.time() < end:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return
            last_error = f"status={r.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise RuntimeError(f"Health check failed for {url}: {last_error}")


@pytest.fixture(scope="session", autouse=True)
def mock_webhook_server():
    """
    CI / local unit tests: ensure mock webhook server is running.
    如果你本地已经手动启动了server，也可以用环境变量关掉自动启动。
    """
    # 允许本地手动运行时跳过自动启动
    if os.getenv("NO_AUTO_MOCK_SERVER") == "1":
        yield
        return

    host = os.getenv("MOCK_HOST", "127.0.0.1")
    port = int(os.getenv("MOCK_PORT", "18080"))

    app_path = os.getenv("MOCK_APP", "tools.mock_server.app:app")

    cmd = [
        "python",
        "-m",
        "uvicorn",
        app_path,
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "info",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ},
    )

    try:
        _wait_port(host, port, timeout=12.0)

        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"mock server exited early:\n{output}")

        _wait_health(f"http://{host}:{port}/health", timeout=12.0)

        yield
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


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
            if AdbClient.is_emulator_serial(d):
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
    parser.addoption(
        "--trigger-mode",
        action="store",
        default=os.getenv("TRIGGER_MODE", "auto"),
        choices=["auto", "adb", "http", "manual"],
        help="How to trigger events: auto/adb/http/manual.",
    )
    parser.addoption(
        "--trigger-strict",
        action="store_true",
        default=os.getenv("TRIGGER_STRICT", "0") == "1",
        help="Fail if adb trigger is requested but cannot be performed.",
    )
    parser.addoption(
        "--trigger-prefer-adb",
        action="store_true",
        default=os.getenv("TRIGGER_PREFER_ADB", "0") == "1",
        help="In auto mode, prefer adb when a device is available.",
    )
    parser.addoption(
        "--sms-inject-mode",
        action="store",
        default=os.getenv("SMS_INJECT_MODE", "local"),
        choices=["local", "mac_cmd", "ssh"],
        help="How to run adb sms injection for emulator (local/mac_cmd/ssh).",
    )
    parser.addoption(
        "--sms-inject-mac-cmd",
        action="store",
        default=os.getenv("SMS_INJECT_MAC_CMD", "mac"),
        help="Command used by sms injector when mode=mac_cmd.",
    )
    parser.addoption(
        "--sms-inject-ssh-host",
        action="store",
        default=os.getenv("SMS_INJECT_SSH_HOST", ""),
        help="SSH host used by sms injector when mode=ssh.",
    )
    parser.addoption(
        "--allow-device-sms",
        action="store_true",
        default=os.getenv("ALLOW_DEVICE_SMS", "0") == "1",
        help="Allow best-effort sms injection on real devices via adb shell.",
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


@pytest.fixture(scope="session")
def trigger_config(request):
    return TriggerConfig(
        mode=request.config.getoption("--trigger-mode"),
        strict=request.config.getoption("--trigger-strict"),
        prefer_adb=request.config.getoption("--trigger-prefer-adb"),
        adb_serial=(request.config.getoption("--adb-serial") or "").strip(),
        sms_inject_mode=request.config.getoption("--sms-inject-mode"),
        sms_inject_mac_cmd=request.config.getoption("--sms-inject-mac-cmd"),
        sms_inject_ssh_host=request.config.getoption("--sms-inject-ssh-host"),
        allow_device_sms=request.config.getoption("--allow-device-sms"),
    )


@pytest.fixture()
def event_trigger(mock_base, trigger_config):
    return EventTrigger(mock_base=mock_base, config=trigger_config)


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
