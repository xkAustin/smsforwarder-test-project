import unittest
from unittest.mock import patch, MagicMock
from tools.adb.sms_injector import inject_sms
import shlex

class TestSMSInjectorSecurity(unittest.TestCase):
    @patch('subprocess.run')
    def test_ssh_injection(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        serial = "emulator-5554"
        phone = "123456"
        text = "hello; touch /tmp/vulnerable"
        ssh_host = "user@remote"

        inject_sms(serial, phone, text, mode="ssh", ssh_host=ssh_host)

        # Check what was passed to subprocess.run
        args, _ = mock_run.call_args
        cmd = args[0]

        remote_cmd = cmd[2]
        self.assertIn("'hello; touch /tmp/vulnerable'", remote_cmd, "The payload should be quoted")

    @patch('subprocess.run')
    def test_ssh_injection_with_quotes(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        serial = "emulator-5554"
        phone = "123456"
        text = "hello'world; touch /tmp/vulnerable"
        ssh_host = "user@remote"

        inject_sms(serial, phone, text, mode="ssh", ssh_host=ssh_host)

        # Check what was passed to subprocess.run
        args, _ = mock_run.call_args
        cmd = args[0]

        remote_cmd = cmd[2]

        # shlex.join should handle single quotes correctly
        # If we split it back with shlex, we should get the original adb_cmd.

        parts = shlex.split(remote_cmd)
        self.assertEqual(parts[-1], text)

    def test_ssh_mode_missing_host(self):
        with self.assertRaises(ValueError) as cm:
            inject_sms("serial", "123456", "text", mode="ssh", ssh_host=None)
        self.assertEqual(str(cm.exception), "ssh_host is required when mode=ssh")

    def test_unknown_mode(self):
        with self.assertRaises(ValueError) as cm:
            inject_sms("serial", "123456", "text", mode="invalid")
        self.assertIn("unknown mode: invalid", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
