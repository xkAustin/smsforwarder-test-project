from unittest.mock import patch

import pytest

from tools.adb.sms_injector import CmdResult, inject_sms

pytestmark = pytest.mark.unit


@patch("tools.adb.sms_injector._run")
def test_mac_cmd_mode_default(mock_run):
    mock_run.return_value = CmdResult(0, "success", "")

    inject_sms("emulator-5554", "123456", "hello", mode="mac_cmd")

    expected_cmd = ["mac", "adb", "-s", "emulator-5554", "emu", "sms", "send", "123456", "hello"]
    mock_run.assert_called_once_with(expected_cmd)


@patch("tools.adb.sms_injector._run")
def test_mac_cmd_mode_custom(mock_run):
    mock_run.return_value = CmdResult(0, "success", "")

    custom_mac = "mac-orb"
    inject_sms("emulator-5554", "123456", "hello", mode="mac_cmd", mac_cmd=custom_mac)

    expected_cmd = [
        custom_mac,
        "adb",
        "-s",
        "emulator-5554",
        "emu",
        "sms",
        "send",
        "123456",
        "hello",
    ]
    mock_run.assert_called_once_with(expected_cmd)
