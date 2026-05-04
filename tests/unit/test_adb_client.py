from unittest.mock import MagicMock, patch

import pytest

from tools.adb.adb_client import AdbClient, AdbDevice, AdbResult

pytestmark = pytest.mark.unit


def _make_client(serial=None):
    return AdbClient(serial=serial)


@patch("subprocess.run")
def test_run_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
    client = _make_client(serial="test-serial")

    result = client.run("shell", "echo", "hello")

    assert result == AdbResult(0, "success", "")
    mock_run.assert_called_once_with(
        ["adb", "-s", "test-serial", "shell", "echo", "hello"],
        capture_output=True,
        text=True,
        timeout=20,
    )


@patch("subprocess.run")
def test_run_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    client = _make_client()

    result = client.run("invalid")

    assert result == AdbResult(1, "", "error")


@patch.object(AdbClient, "run")
def test_list_devices_raw(mock_run):
    mock_run.return_value = AdbResult(0, "List of devices attached", "")
    client = _make_client()

    result = client.list_devices_raw()

    assert result.stdout == "List of devices attached"
    mock_run.assert_called_once_with("devices", "-l", timeout=10)


@patch.object(AdbClient, "list_devices_raw")
def test_get_devices_empty(mock_list_devices_raw):
    mock_list_devices_raw.return_value = AdbResult(0, "List of devices attached\n", "")
    client = _make_client()

    devices = client.get_devices()

    assert devices == []


@patch.object(AdbClient, "list_devices_raw")
def test_list_devices(mock_list_devices_raw):
    mock_list_devices_raw.return_value = AdbResult(0, "raw output", "")
    client = _make_client()

    result = client.list_devices()

    assert result.stdout == "raw output"
    mock_list_devices_raw.assert_called_once()


@patch.object(AdbClient, "list_devices_raw")
def test_get_devices_success(mock_list_devices_raw):
    mock_list_devices_raw.return_value = AdbResult(
        0,
        "List of devices attached\n"
        "emulator-5554          device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emulator64_arm64 transport_id:1\n"
        "192.168.1.100:5555     offline\n",
        "",
    )
    client = _make_client()

    devices = client.get_devices()

    assert len(devices) == 2
    assert devices[0] == AdbDevice(
        serial="emulator-5554",
        state="device",
        desc="product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emulator64_arm64 transport_id:1",
    )
    assert devices[1] == AdbDevice(serial="192.168.1.100:5555", state="offline", desc="")


@patch.object(AdbClient, "list_devices_raw")
def test_get_devices_failure(mock_list_devices_raw):
    mock_list_devices_raw.return_value = AdbResult(1, "", "error message")
    client = _make_client()

    with pytest.raises(RuntimeError) as exc_info:
        client.get_devices()

    assert "adb devices failed: error message" in str(exc_info.value)


@patch.object(AdbClient, "run")
def test_send_sms_emulator(mock_run):
    mock_run.return_value = AdbResult(0, "OK", "")
    client = _make_client(serial="emulator-5554")

    result = client.send_sms_emulator("123456", "hello world")

    assert result.stdout == "OK"
    mock_run.assert_called_once_with("emu", "sms", "send", "123456", "hello world", timeout=10)


@patch.object(AdbClient, "send_sms_emulator")
def test_send_sms(mock_send_sms_emulator):
    mock_send_sms_emulator.return_value = AdbResult(0, "OK", "")
    client = _make_client()

    result = client.send_sms("123456", "hello")

    assert result.stdout == "OK"
    mock_send_sms_emulator.assert_called_once_with("123456", "hello")


@patch("os.getenv")
@patch.object(AdbClient, "get_devices")
def test_choose_serial_prefers_env_var(mock_get_devices, mock_getenv):
    mock_getenv.side_effect = lambda key, default=None: (
        "mock-serial" if key == "ADB_SERIAL" else default
    )

    serial = _make_client().choose_serial()

    assert serial == "mock-serial"
    mock_get_devices.assert_not_called()


@patch("os.getenv")
@patch.object(AdbClient, "get_devices")
def test_choose_serial_no_env_var_prefers_emulator(mock_get_devices, mock_getenv):
    mock_getenv.return_value = ""

    devices = [
        AdbDevice(serial="physical-1", state="device"),
        AdbDevice(serial="emulator-5554", state="device"),
    ]
    mock_get_devices.return_value = devices

    serial = _make_client().choose_serial(prefer_emulator=True)

    assert serial == "emulator-5554"


@patch("os.getenv")
@patch.object(AdbClient, "get_devices")
def test_choose_serial_no_env_var_no_emulator(mock_get_devices, mock_getenv):
    mock_getenv.return_value = ""

    devices = [
        AdbDevice(serial="physical-1", state="device"),
        AdbDevice(serial="physical-2", state="device"),
    ]
    mock_get_devices.return_value = devices

    serial = _make_client().choose_serial()

    assert serial == "physical-1"


@patch("os.getenv")
@patch.object(AdbClient, "get_devices")
@patch.object(AdbClient, "list_devices_raw")
def test_choose_serial_no_devices(mock_list_devices_raw, mock_get_devices, mock_getenv):
    mock_getenv.return_value = ""
    mock_get_devices.return_value = []
    mock_list_devices_raw.return_value = AdbResult(0, "List of devices attached\n", "")

    with pytest.raises(RuntimeError) as exc_info:
        _make_client().choose_serial()

    assert "No adb device in 'device' state" in str(exc_info.value)


def test_is_emulator_serial_true():
    assert AdbClient.is_emulator_serial("emulator-5554")
    assert AdbClient.is_emulator_serial("emulator-5556")
    assert AdbClient.is_emulator_serial("emulator-12345")


def test_is_emulator_serial_false():
    assert not AdbClient.is_emulator_serial("emulator-")
    assert not AdbClient.is_emulator_serial("emulator-abc")
    assert not AdbClient.is_emulator_serial("device-5554")
    assert not AdbClient.is_emulator_serial("127.0.0.1:5555")
    assert not AdbClient.is_emulator_serial("")
