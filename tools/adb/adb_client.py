from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass
class AdbResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str
    desc: str = ""


class AdbClient:
    """
    ADB 客户端封装（面向测试工程）：
    - 支持解析设备列表
    - 自动选择 serial（优先 emulator-<port> 格式的模拟器）
    - 兼容接口：list_devices() / send_sms()
    """

    def __init__(self, serial: str | None = None):
        self.serial = serial

    def _cmd(self, *args: str) -> list[str]:
        base = ["adb"]
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

    # ---- device listing / parsing ----

    def list_devices_raw(self) -> AdbResult:
        return self.run("devices", "-l", timeout=10)

    def list_devices(self) -> AdbResult:
        """
        兼容旧接口：返回 adb devices -l 的原始结果（AdbResult）
        """
        return self.list_devices_raw()

    def get_devices(self) -> list[AdbDevice]:
        r = self.list_devices_raw()
        if r.returncode != 0:
            raise RuntimeError(f"adb devices failed: {r.stderr}")

        lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        out: list[AdbDevice] = []
        for ln in lines[1:]:
            parts = ln.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            desc = " ".join(parts[2:]) if len(parts) > 2 else ""
            out.append(AdbDevice(serial=serial, state=state, desc=desc))
        return out

    @staticmethod
    def is_emulator_serial(serial: str) -> bool:
        """
        判断 serial 是否符合标准的模拟器命名逻辑 (emulator-<port>)。
        """
        return bool(re.fullmatch(r"emulator-\d+", serial))

    def choose_serial(self, prefer_emulator: bool = True) -> str:
        """
        自动选择一个可用设备：
        - 环境变量 ADB_SERIAL 优先（如果设置了）
        - 如果 prefer_emulator=True，优先选择符合 emulator-<port> 格式的设备
        - 否则选择第一个 state='device' 的设备
        """
        env_serial = os.getenv("ADB_SERIAL", "").strip()
        if env_serial:
            return env_serial

        all_devs = self.get_devices()
        devices = [d for d in all_devs if d.state == "device"]
        if not devices:
            raise RuntimeError(
                "No adb device in 'device' state.\n"
                f"adb output:\n{self.list_devices_raw().stdout}\n"
                f"parsed={all_devs}"
            )

        if prefer_emulator:
            emus = [d for d in devices if self.is_emulator_serial(d.serial)]
            if emus:
                return emus[0].serial

        return devices[0].serial

    # ---- actions ----

    def send_sms_emulator(self, phone: str, text: str) -> AdbResult:
        """
        emulator 专用：模拟收到短信
        """
        return self.run("emu", "sms", "send", phone, text, timeout=10)

    def send_sms(self, phone: str, text: str) -> AdbResult:
        """
        兼容旧接口：
        目前等同 send_sms_emulator（仅对 emulator 生效）。
        后续如需支持真机，可在这里扩展策略。
        """
        return self.send_sms_emulator(phone, text)
