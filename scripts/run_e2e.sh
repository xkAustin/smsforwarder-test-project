#!/usr/bin/env bash
set -euo pipefail

# 1) 启动 mock server（如果你想外部起，也可以注释掉）
./scripts/start_mock_server.sh

# 2) 预检：adb 设备、mock server、必要环境变量
python - <<'PY'
import os, requests, subprocess, sys
base = os.getenv("MOCK_BASE", "http://127.0.0.1:18080")
try:
    r = requests.get(base + "/health", timeout=2)
    r.raise_for_status()
except Exception as e:
    print("Mock server not reachable:", base, e)
    sys.exit(1)

p = subprocess.run(["adb","devices"], capture_output=True, text=True)
if p.returncode != 0:
    print("adb devices failed:", p.stderr)
    sys.exit(1)
print(p.stdout)
PY

# 3) 跑 e2e
mkdir -p reports
pytest -v -m e2e \
  --junitxml=reports/junit.xml \
  --html=reports/report.html --self-contained-html
