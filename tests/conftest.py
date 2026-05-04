import logging
import os
import signal
import socket
import subprocess
import time

import pytest
import requests

from tests.utils.api_client import MockApiClient
from tests.utils.trigger import EventTrigger, TriggerConfig
from tools.adb.adb_client import AdbClient

test_logger = logging.getLogger("test")


@pytest.fixture(scope="session", autouse=True)
def _ensure_no_proxy_fixture():
    targets = ["127.0.0.1", "localhost"]
    for key in ("NO_PROXY", "no_proxy"):
        current = os.getenv(key, "")
        parts = [p.strip() for p in current.split(",") if p.strip()] if current else []
        for host in targets:
            if host not in parts:
                parts.append(host)
        os.environ[key] = ",".join(parts)
    yield


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
def mock_webhook_server(_ensure_no_proxy_fixture):
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        env={**os.environ},
    )

    try:
        _wait_port(host, port, timeout=12.0)

        if proc.poll() is not None:
            raise RuntimeError(
                "mock server exited early — "
                "run 'uv run python -m uvicorn tools.mock_server.app:app' manually to see startup errors"
            )

        _wait_health(f"http://{host}:{port}/health", timeout=12.0)

        yield
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


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


def _failure_msg(report):
    if report.longrepr is None:
        return "unknown"
    if hasattr(report.longrepr, "reprcrash") and report.longrepr.reprcrash is not None:
        return report.longrepr.reprcrash.message
    return str(report.longrepr).split("\n")[0][:120]


def pytest_runtest_logstart(nodeid, location):
    test_logger.info("START  %s", nodeid)


def pytest_runtest_logreport(report):
    if report.when == "setup" and report.failed:
        test_logger.error(
            "FAIL   %s | setup | duration=%.3fs | %s",
            report.nodeid,
            report.duration,
            _failure_msg(report),
        )
    elif report.when == "call":
        if report.failed:
            test_logger.error(
                "FAIL   %s | duration=%.3fs | %s",
                report.nodeid,
                report.duration,
                _failure_msg(report),
            )
        elif report.passed:
            test_logger.info("PASS   %s | duration=%.3fs", report.nodeid, report.duration)


@pytest.fixture(scope="session")
def adb(request):
    serial = (request.config.getoption("--adb-serial") or "").strip()
    if not serial:
        serial = AdbClient().choose_serial(prefer_emulator=True)

    client = AdbClient(serial=serial)

    # 设备不在线就直接报错
    devices = client.list_devices_raw()
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
def mock_api(mock_base) -> MockApiClient:
    return MockApiClient(base_url=mock_base)


@pytest.fixture()
def event_trigger(mock_base, trigger_config, mock_api):
    return EventTrigger(mock_base=mock_base, config=trigger_config, api_client=mock_api)


@pytest.fixture()
def mock_reset(mock_base):
    from tests.utils.api_client import full_reset

    full_reset(mock_base)
    yield


@pytest.fixture()
def get_latest_event(mock_base):
    client = MockApiClient(base_url=mock_base)

    def _inner():
        j = client.list_events(limit=1)
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
    client = MockApiClient(base_url=mock_base)

    def _wait(before_count: int, expected_delta: int = 1, timeout_s: float = 10.0) -> bool:
        target = before_count + expected_delta
        return wait_until(lambda: client.event_count() >= target, timeout_s=timeout_s)

    return _wait


@pytest.fixture()
def get_new_events(mock_base):
    client = MockApiClient(base_url=mock_base)

    def _factory(before_count: int):
        def _inner(limit: int = 50):
            j = client.list_events(limit=limit)
            total = int(j["count"])
            new_count = total - int(before_count)
            if new_count <= 0:
                return []
            items = j.get("items", [])

            if new_count > len(items):
                raise AssertionError(
                    f"new_count={new_count} exceeds fetched items={len(items)}. "
                    f"Increase limit (current limit={limit})."
                )
            return items[-new_count:]

        return _inner

    return _factory
