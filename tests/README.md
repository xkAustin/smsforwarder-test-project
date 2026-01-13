# Tests 目录说明

本目录包含 SmsForwarder 的所有测试相关内容。

## 目录结构

- api_webhook/
  - Webhook 与接口契约测试
- performance/
  - 性能与压力测试
- e2e_blackbox/
  - 黑盒端到端测试
- rules/
  - 规则匹配相关测试（后续）

## 运行方式

默认全量运行：

```
uv run pytest
```

指定 marker：

```
uv run pytest -m e2e
uv run pytest -m "not e2e"
uv run pytest -m manual
uv run pytest -m performance
```

## 触发方式（自动/设备/HTTP）

测试通过 `EventTrigger` 触发短信或 webhook。默认 `TRIGGER_MODE=auto`：

- 默认走 HTTP（稳定、可迁移）。
- 需要走设备时，使用 `TRIGGER_MODE=adb` 或 `TRIGGER_PREFER_ADB=1`。

常用环境变量 / CLI 参数：

- `TRIGGER_MODE` / `--trigger-mode`：`auto|adb|http|manual`
- `TRIGGER_STRICT` / `--trigger-strict`：要求必须走 ADB，否则失败
- `TRIGGER_PREFER_ADB` / `--trigger-prefer-adb`：auto 模式下优先走 ADB
- `ALLOW_DEVICE_SMS` / `--allow-device-sms`：允许对真机做 best-effort 注入
- `SMS_INJECT_MODE` / `--sms-inject-mode`：`local|mac_cmd|ssh`
- `SMS_INJECT_MAC_CMD` / `--sms-inject-mac-cmd`
- `SMS_INJECT_SSH_HOST` / `--sms-inject-ssh-host`

示例：

```
TRIGGER_MODE=http uv run pytest -m e2e
TRIGGER_MODE=adb TRIGGER_STRICT=1 uv run pytest -m e2e
```
