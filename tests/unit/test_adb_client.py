import unittest
from unittest.mock import patch, MagicMock
from tools.adb.adb_client import AdbClient, AdbDevice, AdbResult

class TestAdbClient(unittest.TestCase):
    def setUp(self):
        self.client = AdbClient()

    @patch('os.getenv')
    @patch.object(AdbClient, 'get_devices')
    def test_choose_serial_prefers_env_var(self, mock_get_devices, mock_getenv):
        # Setup mock for os.getenv
        mock_getenv.side_effect = lambda key, default=None: "mock-serial" if key == "ADB_SERIAL" else default

        # Call choose_serial
        serial = self.client.choose_serial()

        # Assertions
        self.assertEqual(serial, "mock-serial")
        mock_get_devices.assert_not_called()

    @patch('os.getenv')
    @patch.object(AdbClient, 'get_devices')
    def test_choose_serial_no_env_var_prefers_emulator(self, mock_get_devices, mock_getenv):
        # Setup mock for os.getenv to return None for ADB_SERIAL
        mock_getenv.return_value = ""

        # Setup mock devices
        devices = [
            AdbDevice(serial="physical-1", state="device"),
            AdbDevice(serial="emulator-5554", state="device"),
        ]
        mock_get_devices.return_value = devices

        # Call choose_serial
        serial = self.client.choose_serial(prefer_emulator=True)

        # Assertions
        self.assertEqual(serial, "emulator-5554")

    @patch('os.getenv')
    @patch.object(AdbClient, 'get_devices')
    def test_choose_serial_no_env_var_no_emulator(self, mock_get_devices, mock_getenv):
        # Setup mock for os.getenv to return None for ADB_SERIAL
        mock_getenv.return_value = ""

        # Setup mock devices (no emulator)
        devices = [
            AdbDevice(serial="physical-1", state="device"),
            AdbDevice(serial="physical-2", state="device"),
        ]
        mock_get_devices.return_value = devices

        # Call choose_serial
        serial = self.client.choose_serial()

        # Assertions
        self.assertEqual(serial, "physical-1")

    @patch('os.getenv')
    @patch.object(AdbClient, 'get_devices')
    @patch.object(AdbClient, 'list_devices')
    def test_choose_serial_no_devices(self, mock_list_devices, mock_get_devices, mock_getenv):
        # Setup mock for os.getenv to return None for ADB_SERIAL
        mock_getenv.return_value = ""

        # Setup mock for get_devices to return an empty list
        mock_get_devices.return_value = []

        # Setup mock for list_devices
        mock_list_devices.return_value = AdbResult(0, "List of devices attached\n", "")

        # Assertions
        with self.assertRaises(RuntimeError) as cm:
            self.client.choose_serial()

        self.assertIn("No adb device in 'device' state", str(cm.exception))

    @patch.object(AdbClient, 'run')
    def test_send_sms(self, mock_run):
        mock_run.return_value = AdbResult(0, "OK", "")
        res = self.client.send_sms("123456", "hello")

        self.assertEqual(res.stdout, "OK")
        mock_run.assert_called_with("emu", "sms", "send", "123456", "hello", timeout=10)

    @patch.object(AdbClient, 'run')
    def test_list_devices(self, mock_run):
        mock_run.return_value = AdbResult(0, "List of devices attached\n", "")
        res = self.client.list_devices()

        self.assertEqual(res.returncode, 0)
        mock_run.assert_called_with("devices", "-l", timeout=10)

if __name__ == "__main__":
    unittest.main()
