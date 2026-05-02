# Repository Guidelines

## Project Structure & Module Organization
Core Python code lives in `tools/`: `tools/adb/` contains ADB and SMS injection helpers, and `tools/mock_server/` hosts the FastAPI webhook capture server. Tests are under `tests/`, grouped by scope: `unit/`, `api_webhook/`, `e2e_blackbox/`, `performance/`, and shared helpers in `tests/utils/`. Runtime assets live in `app/`, including the test APK at `app/apk/`. Entry files include `main.py`, `docker-compose.yml`, and automation scripts in `scripts/`.

## Build, Test, and Development Commands
Use `uv` for local Python execution and Docker for containerized runs.

- `uv run pytest`: run the full test suite locally.
- `uv run pytest -m "not e2e and not performance and not manual"`: run the fast default subset for development.
- `uv run pytest -m e2e`: run end-to-end tests that require emulator or trigger setup.
- `make build`: build the Docker test environment with `docker compose`.
- `make test`: run tests in Docker and return the test container exit code.
- `scripts/start_mock_server.sh`: start the local webhook mock server used by API and e2e flows.

## Coding Style & Naming Conventions
Target Python `>=3.12`. Follow the existing style: 4-space indentation, type hints on public APIs, `snake_case` for functions and modules, `PascalCase` for classes, and small dataclasses for structured results. Keep new code close to the current layout instead of adding new top-level packages. There is no dedicated formatter configured in `pyproject.toml`, so match surrounding code and keep imports and function bodies tidy.

## Testing Guidelines
Pytest is the test runner and is configured in `pyproject.toml` with `tests/` as the test root. Name files `test_*.py` and keep test names descriptive, for example `test_no_retry_behavior.py`. Use markers intentionally: `e2e`, `integration`, `performance`, and `manual`. Add unit coverage for new helper logic and API-level coverage for webhook behavior changes.

## Commit & Pull Request Guidelines
Recent history uses short imperative subjects, often with prefixes such as `docs:`, `refactor:`, `test:`, or `[code health]`. Keep commit messages focused on one change, for example `test: cover adb serial selection`. Pull requests should describe the behavior change, list validation commands run, link related issues, and include screenshots or sample payloads when webhook responses or test reports change.

## Security & Configuration Tips
Review `SECURITY.md` before changing webhook handling or device-trigger flows. Prefer environment variables for trigger configuration such as `TRIGGER_MODE`, `TRIGGER_STRICT`, and `ADB_SERIAL`; do not hardcode device-specific values in tests.
