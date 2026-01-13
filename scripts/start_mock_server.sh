#!/usr/bin/env bash
set -euo pipefail

PORT="${MOCK_PORT:-18080}"
HOST="${MOCK_HOST:-0.0.0.0}"

nohup python -m uvicorn tools.mock_server.app:app \
  --host "$HOST" --port "$PORT" \
  >mock_server.log 2>&1 &

python - <<'PY'
import time, requests, os
port = os.getenv("MOCK_PORT","18080")
url = f"http://127.0.0.1:{port}/health"
for _ in range(40):
    try:
        r = requests.get(url, timeout=1)
        if r.status_code == 200:
            print("mock server ok:", url)
            break
    except Exception:
        pass
    time.sleep(0.25)
else:
    raise SystemExit("mock server not ready")
PY
