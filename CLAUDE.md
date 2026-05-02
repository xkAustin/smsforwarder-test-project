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
FastAPI app that captures webhook events into an in-memory deque (max 5000). Key endpoints:
- `* /webhook` — capture incoming webhook requests (all HTTP methods)
- `GET /events` — list captured events (`?limit=N`, clamped to 1–500)
- `GET /events/{event_id}` — fetch single event by UUID
- `POST /reset` — clear all events
- `POST /fault/reset` — reset fault injection state
- `POST /fault/config` — configure fault injection (mode=ok|fail|delay, fail_count, delay_ms)
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
- `tests/api_webhook/` — Webhook API contract tests (8 files, 43 tests): HTTP methods (GET/POST/PUT/PATCH/DELETE), JSON/form/empty body, custom headers, HMAC-SHA256 signing, Basic Auth, Unicode, fault injection, security bounds, concurrency (50 threads), event ordering, retry behavior, mock server regression (schema, /events/{id}, deque bounds, idempotency)
- `tests/e2e_blackbox/` — End-to-end tests (2 files, 3 tests): ADB injection → SmsForwarder → webhook verification
- `tests/performance/` — Throughput and latency benchmarks (2 CLI tools + 2 smoke tests) for webhook receiver and e2e SMS flow
- `tests/unit/` — Unit tests (4 files, 15 tests): ADB device selection, SMS injector security, mac_cmd mode, mock server _safe_decode

### Test Infrastructure (`tests/conftest.py`)
Session-scoped fixture auto-starts the mock server (uvicorn) unless `NO_AUTO_MOCK_SERVER=1`. Key fixtures: `mock_base`, `mock_reset`, `mock_counter`, `wait_for_event`, `get_new_events`, `event_trigger`, `trigger_config`.

### CI/CD
- `.github/workflows/python-tests.yml` — runs on push/PR: builds, installs deps, runs full suite excluding e2e
- `.github/workflows/e2e.yml` — manual-dispatch workflow for self-hosted runners with ADB access

### Environment Variables / CLI Flags
- `MOCK_BASE` / `--mock-base` — mock server URL (default: `http://127.0.0.1:18080`)
- `MOCK_HOST` / `MOCK_PORT` — server bind host/port
- `NO_AUTO_MOCK_SERVER=1` — skip auto-starting mock server
- `TRIGGER_MODE` / `--trigger-mode` — `auto|adb|http|manual`
- `TRIGGER_STRICT=1` / `--trigger-strict` — fail if ADB trigger unavailable
- `TRIGGER_PREFER_ADB=1` / `--trigger-prefer-adb` — prefer ADB in auto mode
- `ADB_SERIAL` / `--adb-serial` — specific ADB device serial
- `SMS_INJECT_MODE` / `--sms-inject-mode` — `local|mac_cmd|ssh`
- `SMS_INJECT_MAC_CMD` / `--sms-inject-mac-cmd` — custom mac command name
- `SMS_INJECT_SSH_HOST` / `--sms-inject-ssh-host` — SSH remote host
- `ALLOW_DEVICE_SMS` / `--allow-device-sms` — enable best-effort device SMS injection

### Documentation
- `README.md` — project overview, architecture diagram, quick start, full config reference, mock server API
- `CONTRIBUTING.md` — development setup, code style, test naming conventions, commit/PR guidelines
- `SECURITY.md` — security boundaries, SSH injection safety, CI security, checklist for changes
- `docs/ARCHITECTURE.md` — detailed system design, data flow, key file walkthrough, extension points
- `TEST_STRATEGY.md` — test objectives, coverage matrix, environment compatibility, regression strategy
- `tests/README.md` — directory structure, fixture reference, trigger mode guide, E2E prerequisites
