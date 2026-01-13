import os
import time
import requests
import pytest

from tools.adb.adb_client import AdbClient


def pytest_addoption(parser):
    parser.addoption(
        "--adb-serial", action="store", default=os.getenv("ADB_SERIAL", "emulator-5554")
    )
    parser.addoption(
        "--mock-base",
        action="store",
        default=os.getenv("MOCK_BASE", "http://127.0.0.1:18080"),
    )
    parser.addoption(
        "--e2e-wait",
        action="store",
        type=float,
        default=float(os.getenv("E2E_WAIT", "3")),
    )


@pytest.fixture(scope="session")
def adb(request):
    serial = request.config.getoption("--adb-serial")
    return AdbClient(serial=serial)


@pytest.fixture(scope="session")
def mock_base(request):
    return request.config.getoption("--mock-base")


@pytest.fixture()
def mock_reset(mock_base):
    requests.post(f"{mock_base}/reset", timeout=3).raise_for_status()
    yield


def get_count(mock_base: str) -> int:
    r = requests.get(f"{mock_base}/events", params={"limit": 50}, timeout=3)
    r.raise_for_status()
    return r.json()["count"]


@pytest.fixture()
def mock_counter(mock_base):
    """
    用法：
      before = mock_counter()
      ...触发...
      after = mock_counter()
    """
    return lambda: get_count(mock_base)


@pytest.fixture()
def get_latest_event(mock_base):
    def _inner():
        r = requests.get(f"{mock_base}/events", params={"limit": 1}, timeout=3)
        r.raise_for_status()
        return r.json()["items"][-1]

    return _inner


@pytest.fixture(scope="session")
def e2e_wait(request):
    return request.config.getoption("--e2e-wait")


def wait_until(predicate, timeout_s=10, interval_s=0.2):
    end = time.time() + timeout_s
    while time.time() < end:
        if predicate():
            return True
        time.sleep(interval_s)
    return False


@pytest.fixture()
def wait_for_event(mock_base):
    """
    等待 events count 增加（解决异步转发不确定性）
    """

    def _wait(before_count: int, timeout_s: float = 10) -> bool:
        return wait_until(
            lambda: get_count(mock_base) >= before_count + 1, timeout_s=timeout_s
        )

    return _wait
