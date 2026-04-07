from __future__ import annotations

from dataclasses import dataclass
import socket
import time
from typing import Optional

import requests

from tools.adb.adb_client import AdbClient, AdbResult
from tools.adb.sms_injector import CmdResult, inject_sms


@dataclass(frozen=True)
class TriggerConfig:
    mode: str
    strict: bool
    prefer_adb: bool
    adb_serial: str
    sms_inject_mode: str
    sms_inject_mac_cmd: str
    sms_inject_ssh_host: str
    allow_device_sms: bool


@dataclass(frozen=True)
class TriggerResult:
    mode: str
    serial: Optional[str]
    used_fallback: bool
    detail: str


def _emulator_port(serial: str) -> Optional[int]:
    if not AdbClient.is_emulator_serial(serial):
        return None
    try:
        return int(serial.split("-", 1)[1])
    except (IndexError, ValueError):
        return None


def _emulator_console_reachable(serial: str) -> bool:
    port = _emulator_port(serial)
    if port is None:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _choose_adb_serial(prefer_emulator: bool = True) -> str:
    return AdbClient(serial=None).choose_serial(prefer_emulator=prefer_emulator)


def _send_sms_emulator(
    serial: str,
    phone: str,
    text: str,
    config: TriggerConfig,
) -> CmdResult:
    return inject_sms(
        serial=serial,
        phone=phone,
        text=text,
        mode=config.sms_inject_mode,
        mac_cmd=config.sms_inject_mac_cmd,
        ssh_host=config.sms_inject_ssh_host or None,
    )


def _send_sms_device_best_effort(serial: str, phone: str, text: str) -> AdbResult:
    client = AdbClient(serial=serial)
    r = client.run("shell", "cmd", "sms", "send", phone, text, timeout=10)
    if r.returncode == 0:
        return r

    # Fallback attempt for older devices (may require privileged permissions).
    return client.run(
        "shell",
        "service",
        "call",
        "isms",
        "7",
        "s16",
        "com.android.mms",
        "s16",
        phone,
        "s16",
        "null",
        "s16",
        text,
        "s16",
        "null",
        "s16",
        "null",
        timeout=10,
    )


class EventTrigger:
    def __init__(self, mock_base: str, config: TriggerConfig):
        self.mock_base = mock_base.rstrip("/")
        self.config = config

    def send_webhook_json(
        self, payload: dict, timeout: float = 3.0, allow_fail: bool = False
    ) -> TriggerResult:
        try:
            r = requests.post(
                f"{self.mock_base}/webhook", json=payload, timeout=timeout
            )
            if not allow_fail:
                r.raise_for_status()
        except requests.RequestException as exc:
            if not allow_fail:
                raise
            return TriggerResult(
                mode="http",
                serial=None,
                used_fallback=False,
                detail=f"json request failed: {exc}",
            )
        return TriggerResult(mode="http", serial=None, used_fallback=False, detail="json")

    def send_webhook_form(
        self, form: dict, timeout: float = 3.0, allow_fail: bool = False
    ) -> TriggerResult:
        try:
            r = requests.post(f"{self.mock_base}/webhook", data=form, timeout=timeout)
            if not allow_fail:
                r.raise_for_status()
        except requests.RequestException as exc:
            if not allow_fail:
                raise
            return TriggerResult(
                mode="http",
                serial=None,
                used_fallback=False,
                detail=f"form request failed: {exc}",
            )
        return TriggerResult(mode="http", serial=None, used_fallback=False, detail="form")

    def send_sms(self, phone: str, text: str, allow_fail: bool = False) -> TriggerResult:
        mode = self.config.mode
        if mode == "http":
            return self._send_http_sms(phone, text, allow_fail=allow_fail)
        if mode == "manual":
            return TriggerResult(
                mode="manual",
                serial=None,
                used_fallback=False,
                detail="manual trigger required",
            )
        if mode == "auto" and not self.config.prefer_adb:
            return self._send_http_sms(phone, text, allow_fail=allow_fail)
        return self._send_adb_or_fallback(
            phone, text, prefer_emulator=True, allow_fail=allow_fail
        )

    def send_sms_batch(
        self, phone: str, texts: list[str], allow_fail: bool = False
    ) -> TriggerResult:
        result = None
        for text in texts:
            result = self.send_sms(phone, text, allow_fail=allow_fail)
        return result or TriggerResult(
            mode=self.config.mode, serial=None, used_fallback=False, detail="no-op"
        )

    def _send_http_sms(
        self, phone: str, text: str, allow_fail: bool = False
    ) -> TriggerResult:
        form = {"from": phone, "content": text, "timestamp": str(int(time.time()))}
        return self.send_webhook_form(form, allow_fail=allow_fail)

    def _send_adb_or_fallback(
        self, phone: str, text: str, prefer_emulator: bool, allow_fail: bool
    ) -> TriggerResult:
        serial = self.config.adb_serial
        if not serial:
            try:
                serial = _choose_adb_serial(prefer_emulator=prefer_emulator)
            except RuntimeError as exc:
                if self.config.mode == "adb" or self.config.strict:
                    raise RuntimeError(f"adb unavailable: {exc}") from exc
                return self._fallback_http(phone, text, "no adb device", allow_fail)

        if AdbClient.is_emulator_serial(serial):
            if not _emulator_console_reachable(serial):
                if self.config.mode == "adb" or self.config.strict:
                    raise RuntimeError(
                        f"emulator console not reachable on serial {serial}"
                    )
                return self._fallback_http(
                    phone, text, "emulator console unreachable", allow_fail
                )
            result = _send_sms_emulator(serial, phone, text, self.config)
            if result.returncode == 0:
                return TriggerResult(
                    mode="adb",
                    serial=serial,
                    used_fallback=False,
                    detail="emulator sms injected",
                )
            if self.config.mode == "adb" or self.config.strict:
                raise RuntimeError(f"adb emulator sms failed: {result.stderr}")
            return self._fallback_http(
                phone, text, result.stderr or "adb emulator failed", allow_fail
            )

        if self.config.allow_device_sms:
            result = _send_sms_device_best_effort(serial, phone, text)
            if result.returncode == 0:
                return TriggerResult(
                    mode="adb",
                    serial=serial,
                    used_fallback=False,
                    detail="device sms injected",
                )
            if self.config.mode == "adb" or self.config.strict:
                raise RuntimeError(f"adb device sms failed: {result.stderr}")
            return self._fallback_http(
                phone, text, result.stderr or "adb device failed", allow_fail
            )

        if self.config.mode == "adb" or self.config.strict:
            raise RuntimeError(
                f"serial {serial} is not emulator and device sms is disabled"
            )
        return self._fallback_http(phone, text, "device sms disabled", allow_fail)

    def _fallback_http(
        self, phone: str, text: str, reason: str, allow_fail: bool
    ) -> TriggerResult:
        self._send_http_sms(phone, text, allow_fail=allow_fail)
        return TriggerResult(
            mode="http",
            serial=None,
            used_fallback=True,
            detail=f"http fallback: {reason}",
        )
