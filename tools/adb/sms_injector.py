from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str


def _run(cmd: list[str], timeout: int = 20) -> CmdResult:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return CmdResult(p.returncode, p.stdout.strip(), p.stderr.strip())
    except FileNotFoundError:
        return CmdResult(-1, "", f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return CmdResult(-1, "", f"Command timed out: {cmd}")


def inject_sms(
    serial: str,
    phone: str,
    text: str,
    mode: str = "local",
    mac_cmd: str = "mac",
    ssh_host: Optional[str] = None,
) -> CmdResult:
    """
    在隔离环境中注入短信的统一入口

    mode:
      - mac_cmd: 使用 OrbStack 提供的 `mac` 命令在宿主机执行 adb
      - ssh:     使用 ssh 到宿主机执行 adb
      - local:   直接在当前环境执行 adb

    """
    adb_cmd = ["adb", "-s", serial, "emu", "sms", "send", phone, text]

    if mode == "local":
        return _run(adb_cmd)

    if mode == "mac_cmd":
        return _run([mac_cmd, *adb_cmd])

    if mode == "ssh":
        if not ssh_host:
            raise ValueError("ssh_host is required when mode=ssh")
        remote = shlex.join(adb_cmd)
        return _run(["ssh", ssh_host, remote])

    raise ValueError(f"unknown mode: {mode}")
