# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Testing infrastructure for the [SmsForwarder](https://github.com/pppscn/SmsForwarder) Android app (an SMS forwarding tool). This is a Python-based test project, not the app itself — it validates SMS forwarding via black-box, API contract, performance, and unit tests.

## Commands

```bash
# Install dependencies
uv sync --frozen

# Run all tests (skips e2e by default in CI)
uv run pytest

# Run with specific markers
uv run pytest -m e2e                                    # end-to-end (requires Android device/emulator)
uv run pytest -m "not e2e"                              # unit + integration + api tests
uv run pytest -m performance                            # performance/benchmark tests
uv run pytest -m integration                            # integration tests (mock server only)
uv run pytest -m manual                                 # manually-triggered tests

# Run a specific test file or function
uv run pytest tests/api_webhook/test_webhook_basic.py
uv run pytest tests/api_webhook/test_webhook_basic.py::test_webhook_receive_json_body

# Run with HTML report
uv run pytest --html=reports/report.html --self-contained-html

# Docker-based test run
docker compose build
docker compose up --exit-code-from tests
```

## Architecture

### Mock Webhook Server (`tools/mock_server/app.py`)
FastAPI app that captures webhook events into an in-memory deque. Key endpoints:
- `POST /webhook` — capture incoming webhook requests
- `GET /events` — list captured events
- `POST /reset` — clear all events
- `POST /fault/config` — configure fault injection (ok/fail/delay modes)
- `GET /health` — health check

### Test Trigger System (`tests/utils/trigger.py`)
`EventTrigger` class routes event sending through configurable modes:
- **http** — direct POST to mock server (default, most reliable)
- **adb** — inject SMS via Android emulator/device
- **auto** — prefer HTTP, fall back to ADB
- **manual** — require human intervention

Trigger mode is set via `TRIGGER_MODE` env var or `--trigger-mode` CLI flag.

### ADB Tools (`tools/adb/`)
`adb_client.py` wraps ADB device management; `sms_injector.py` handles SMS injection into emulators.

### Test Categories
- `tests/api_webhook/` — Webhook API contract tests: basic JSON/form reception, edge cases (malformed JSON, large payloads, missing content-type), fault injection (server errors, delays), security bounds, retry behavior
- `tests/e2e_blackbox/` — End-to-end tests requiring a running Android device/emulator
- `tests/performance/` — Throughput and latency benchmarks for webhook receiver and e2e SMS flow
- `tests/unit/` — Unit tests for mock server utilities, ADB client, SMS injector

### Test Infrastructure (`tests/conftest.py`)
Session-scoped fixture auto-starts the mock server (uvicorn) unless `NO_AUTO_MOCK_SERVER=1`. Key fixtures: `mock_base`, `mock_reset`, `mock_counter`, `wait_for_event`, `get_new_events`, `event_trigger`, `trigger_config`.

### CI/CD
- `.github/workflows/python-tests.yml` — runs on push/PR: builds, installs deps, runs full suite excluding e2e
- `.github/workflows/e2e.yml` — manual-dispatch workflow for self-hosted runners with ADB access

### Environment Variables / CLI Flags
- `MOCK_BASE` — mock server URL (default: `http://127.0.0.1:18080`)
- `NO_AUTO_MOCK_SERVER=1` — skip auto-starting mock server
- `TRIGGER_MODE` — `auto|adb|http|manual`
- `TRIGGER_STRICT=1` — fail if ADB trigger unavailable
- `TRIGGER_PREFER_ADB=1` — prefer ADB in auto mode
- `ADB_SERIAL` — specific ADB device serial
- `SMS_INJECT_MODE` — `local|mac_cmd|ssh`
