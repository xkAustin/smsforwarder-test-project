from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class AdbResult:
    returncode: int
    stdout: str
    stderr: str


class AdbClient:
    def __init__(self, serial: Optional[str] = None, adb_bin: Optional[str] = None):
        self.serial = serial
        self.adb_bin = adb_bin or os.environ.get("ADB_BIN") or "adb"

    def _cmd(self, *args: str) -> list[str]:
        base = shlex.split(self.adb_bin)
        if self.serial:
            base += ["-s", self.serial]
        base += list(args)
        return base

    def run(self, *args: str, timeout: int = 20) -> AdbResult:
        p = subprocess.run(
            self._cmd(*args),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return AdbResult(p.returncode, p.stdout.strip(), p.stderr.strip())

    def list_devices(self) -> AdbResult:
        return self.run("devices", timeout=10)

    def send_sms(self, phone: str, text: str) -> AdbResult:
        return self.run("emu", "sms", "send", phone, text, timeout=10)
