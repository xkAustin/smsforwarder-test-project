"""Shared HTTP client for the mock webhook server.

All test files use this instead of writing raw requests calls,
eliminating duplicated URL construction and error handling.
"""

from __future__ import annotations

from typing import Any

import requests

from tests.utils.http_payload import parse_event_body


class MockApiClient:
    """Typed wrapper around the mock webhook server's HTTP API."""

    def __init__(self, base_url: str, timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, params: dict | None = None) -> dict:
        r = requests.post(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _request_raw(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        data: str | None = None,
        headers: dict | None = None,
    ) -> requests.Response:
        return requests.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=params,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )

    # ── health / reset ─────────────────────────────────────────────

    def health(self) -> dict:
        return self._get("/health")

    def reset(self) -> dict:
        return self._post("/reset")

    # ── events ─────────────────────────────────────────────────────

    def list_events(self, limit: int = 50) -> dict:
        clamped = max(1, min(limit, 500))
        return self._get("/events", params={"limit": clamped})

    def get_event(self, event_id: str) -> dict:
        return self._get(f"/events/{event_id}")

    def event_count(self) -> int:
        j = self.list_events(limit=1)
        return int(j["count"])

    # ── fault injection ────────────────────────────────────────────

    def fault_reset(self) -> dict:
        return self._post("/fault/reset")

    def fault_config(self, mode: str = "ok", fail_count: int = 0, delay_ms: int = 0) -> dict:
        return self._post(
            "/fault/config",
            params={"mode": mode, "fail_count": fail_count, "delay_ms": delay_ms},
        )

    # ── webhook ────────────────────────────────────────────────────

    def post_webhook(
        self,
        json: dict = None,
        data: dict = None,
        headers: dict = None,
        allow_fail: bool = False,
        timeout: float | None = None,
    ) -> requests.Response:
        r = requests.post(
            f"{self.base_url}/webhook",
            json=json,
            data=data,
            headers=headers,
            timeout=timeout if timeout is not None else self.timeout,
        )
        if not allow_fail:
            r.raise_for_status()
        return r

    def get_webhook(self, params: dict | None = None) -> requests.Response:
        r = requests.get(f"{self.base_url}/webhook", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r

    def put_webhook(self, json: dict | None = None) -> requests.Response:
        r = requests.put(f"{self.base_url}/webhook", json=json, timeout=self.timeout)
        r.raise_for_status()
        return r

    def patch_webhook(self, json: dict | None = None) -> requests.Response:
        r = requests.patch(f"{self.base_url}/webhook", json=json, timeout=self.timeout)
        r.raise_for_status()
        return r

    def delete_webhook(self) -> requests.Response:
        r = requests.delete(f"{self.base_url}/webhook", timeout=self.timeout)
        r.raise_for_status()
        return r

    def request_webhook(
        self,
        method: str,
        data: str | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> requests.Response:
        """Send a raw request to /webhook with arbitrary method/data/headers.

        Used for edge-case tests (malformed JSON, empty Content-Type, etc.)
        that bypass the typed methods above.
        """
        r = requests.request(
            method=method,
            url=f"{self.base_url}/webhook",
            data=data,
            headers=headers,
            timeout=timeout if timeout is not None else self.timeout,
        )
        return r

    # ── convenience ────────────────────────────────────────────────

    def parse_latest_event(self) -> dict[str, Any]:
        """Fetch the latest captured event and parse its body.

        Raises AssertionError if no events are present.
        """
        j = self.list_events(limit=1)
        items = j.get("items", [])
        if not items:
            raise AssertionError("no events captured yet")
        event = items[-1]
        body_text, body_json, form = parse_event_body(event)
        return {
            "event": event,
            "body_raw": event.get("body_raw", ""),
            "body_json": body_json,
            "body_form": form or {},
            "body_text": body_text,
        }

    def wait_for_count(
        self, target_count: int, timeout_s: float = 10.0, interval_s: float = 0.2
    ) -> bool:
        """Poll until event count reaches or exceeds target_count."""
        import time

        end = time.time() + timeout_s
        while time.time() < end:
            if self.event_count() >= target_count:
                return True
            time.sleep(interval_s)
        return False


def full_reset(mock_base: str, timeout: float = 3.0) -> None:
    """Reset both the main event store and fault injection state.

    Swallows 404/405 from fault/reset for backward compatibility
    with servers that do not expose the fault injection endpoints.
    """
    import requests

    requests.post(f"{mock_base}/reset", timeout=timeout).raise_for_status()
    try:
        requests.post(f"{mock_base}/fault/reset", timeout=timeout).raise_for_status()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (404, 405):
            pass
        else:
            raise
