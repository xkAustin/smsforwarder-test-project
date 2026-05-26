import shlex
from unittest.mock import MagicMock, patch

import pytest

from tools.adb.sms_injector import inject_sms

pytestmark = pytest.mark.unit


@patch("subprocess.run")
def test_ssh_injection(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    serial = "emulator-5554"
    phone = "123456"
    text = "hello; touch /tmp/vulnerable"
    ssh_host = "user@remote"

    inject_sms(serial, phone, text, mode="ssh", ssh_host=ssh_host)

    args, _ = mock_run.call_args
    cmd = args[0]

    remote_cmd = cmd[3]
    assert "'hello; touch /tmp/vulnerable'" in remote_cmd, "The payload should be quoted"


@patch("subprocess.run")
def test_ssh_injection_with_quotes(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    serial = "emulator-5554"
    phone = "123456"
    text = "hello'world; touch /tmp/vulnerable"
    ssh_host = "user@remote"

    inject_sms(serial, phone, text, mode="ssh", ssh_host=ssh_host)

    args, _ = mock_run.call_args
    cmd = args[0]

    remote_cmd = cmd[3]
    parts = shlex.split(remote_cmd)
    assert parts[-1] == text


def test_ssh_mode_missing_host():
    with pytest.raises(ValueError) as exc_info:
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host=None)
    assert str(exc_info.value) == "ssh_host is required when mode=ssh"


def test_unknown_mode():
    with pytest.raises(ValueError) as exc_info:
        inject_sms("serial", "123456", "text", mode="invalid")
    assert "unknown mode: invalid" in str(exc_info.value)


def test_ssh_host_validation():
    # Test hyphen prefix
    with pytest.raises(ValueError) as exc_info:
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host="-oProxyCommand=calc")
    assert "invalid ssh_host: -oProxyCommand=calc" in str(exc_info.value)

    # Test spaces
    with pytest.raises(ValueError) as exc_info:
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host="host1 host2")
    assert "invalid ssh_host: host1 host2" in str(exc_info.value)

    # Test semicolon (shell injection)
    with pytest.raises(ValueError) as exc_info:
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host="host;id")
    assert "invalid ssh_host: host;id" in str(exc_info.value)

    # Test valid formats
    with patch("tools.adb.sms_injector._run") as mock_run:
        mock_run.return_value = MagicMock()
        # username@host
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host="user@host-1.local")
        # IPv6
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host="[2001:db8::1]")
        # host:port
        inject_sms("serial", "123456", "text", mode="ssh", ssh_host="localhost:2222")


def test_mac_cmd_validation():
    with pytest.raises(ValueError) as exc_info:
        inject_sms("serial", "123456", "text", mode="mac_cmd", mac_cmd="rm")
    assert "invalid mac_cmd: rm" in str(exc_info.value)


@patch("subprocess.run")
def test_ssh_delimiter(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    inject_sms("serial", "123456", "text", mode="ssh", ssh_host="myhost")
    args, _ = mock_run.call_args
    cmd = args[0]
    assert cmd == ["ssh", "--", "myhost", "adb -s serial emu sms send 123456 text"]

@patch("subprocess.run")
def test_inject_sms_file_not_found(mock_run):
    mock_run.side_effect = FileNotFoundError
    result = inject_sms("serial", "123456", "text")
    assert result.returncode == -1
    assert "Command not found" in result.stderr


@patch("subprocess.run")
def test_inject_sms_timeout(mock_run):
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["adb"], timeout=20)
    result = inject_sms("serial", "123456", "text")
    assert result.returncode == -1
    assert "Command timed out" in result.stderr
