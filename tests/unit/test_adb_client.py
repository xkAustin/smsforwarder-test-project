from unittest.mock import patch

import pytest

from tools.adb.adb_client import AdbClient, AdbDevice, AdbResult

pytestmark = pytest.mark.unit


def _make_client():
    return AdbClient()


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

    import pytest

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
