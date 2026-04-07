import unittest
from unittest.mock import patch
from tools.adb.sms_injector import inject_sms, CmdResult

class TestSMSInjectorMac(unittest.TestCase):
    @patch('tools.adb.sms_injector._run')
    def test_mac_cmd_mode_default(self, mock_run):
        mock_run.return_value = CmdResult(0, "success", "")

        serial = "emulator-5554"
        phone = "123456"
        text = "hello"

        inject_sms(serial, phone, text, mode="mac_cmd")

        expected_cmd = ["mac", "adb", "-s", serial, "emu", "sms", "send", phone, text]
        mock_run.assert_called_once_with(expected_cmd)

    @patch('tools.adb.sms_injector._run')
    def test_mac_cmd_mode_custom(self, mock_run):
        mock_run.return_value = CmdResult(0, "success", "")

        serial = "emulator-5554"
        phone = "123456"
        text = "hello"
        custom_mac = "/usr/local/bin/mac-orb"

        inject_sms(serial, phone, text, mode="mac_cmd", mac_cmd=custom_mac)

        expected_cmd = [custom_mac, "adb", "-s", serial, "emu", "sms", "send", phone, text]
        mock_run.assert_called_once_with(expected_cmd)

if __name__ == "__main__":
    unittest.main()
