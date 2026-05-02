# SmsForwarder 测试策略

## 测试背景

SmsForwarder 是一款 Android 短信转发工具，支持监听来电、短信、App 通知、定位、电量、网络状态变化，并通过 16 种转发通道（Webhook、DingTalk、Email、Bark、Telegram 等）将信息推送到外部系统。

本测试项目的目标是确保 SmsForwarder 的核心转发功能在不同配置与规则下稳定可靠。

## 测试目标

- 验证消息转发接口（Webhook / HTTP）的字段完整性与契约一致性
- 验证系统在高频消息场景下的稳定性与性能边界
- 构建可自动执行的测试体系，支持持续集成与回归测试
- 为规则匹配逻辑与转发通道提供黑盒/接口级安全保障
- 支持多环境（本地/CIDocker/远程模拟器）统一运行

## 测试对象

[SmsForwarder](https://github.com/pppscn/SmsForwarder) — Android 应用，当前测试基于 v3.3.3 (arm64-v8a release APK)

## 测试范围

### 已覆盖

| 领域 | 覆盖内容 | 测试文件 |
|---|---|---|
| **Webhook 接口契约** | HTTP 方法（GET/POST/PUT/PATCH/DELETE）、JSON/Form body、自定义 Header、HMAC-SHA256 签名、Basic Auth、Unicode | `tests/api_webhook/test_webhook_*.py`（8 个文件） |
| **故障注入** | 可配置失败次数、延迟注入、参数安全上限、无效模式拒绝 | `test_fault_injection.py`、`test_security_bounds.py` |
| **不重试行为** | HTTP 500 不重试、超时不重试 | `test_no_retry_behavior.py` |
| **并发** | 50 线程并发 POST、混合方法并发、事件排序、计数单调性 | `test_webhook_concurrency.py` |
| **Mock server 回归** | `/events/{id}` 端点、Schema 验证、UUID 唯一性、队列边界、limit 钳位 | `test_mock_server_regression.py` |
| **E2E 黑盒** | ADB 注入 → App 转发 → Webhook 接收验证 | `tests/e2e_blackbox/`（2 个文件） |
| **性能** | Webhook 吞吐与延迟基准、E2E 吞吐烟测 | `tests/performance/`（4 个文件） |
| **单元测试** | ADB 设备选择、短信注入安全、mock server 编解码 | `tests/unit/`（4 个文件） |

### 计划中

| 领域 | 说明 |
|---|---|
| **规则匹配单元测试** | SmsForwarder 规则引擎（条件匹配、多条件组合）的白盒测试 |
| **其他转发通道** | 除 Webhook 外的 15 个通道（Email、Bark、Telegram 等）的协议测试 |
| **长稳测试** | 24 小时持续运行下的稳定性验证 |
| **真机兼容性** | 不同 Android 版本/OEM 的短信广播兼容性 |

### 非测试范围

- 适配机型兼容性（由 SmsForwarder 项目自行保证）
- 操作系统级 Bug
- 第三方转发平台（DingTalk、Feishu 等）的 Bug

## 测试环境

| 组件 | 环境 |
|---|---|
| 测试设备 | AVD Medium Phone (Android 16.0) |
| Python | 3.14.2+ |
| pytest | 9.0.2+ |
| Mock Server | FastAPI + uvicorn (本地) |
| CI | GitHub Actions (ubuntu-latest) |
| 包管理 | uv |
| 容器化 | Docker (python:3.12-slim) |

## 自动触发策略

测试通过 `EventTrigger` 统一触发事件。详细配置参考 [README.md](./README.md) 的"触发模式"章节。

核心原则：
- **默认走 HTTP**（稳定、快速、不依赖设备）
- **E2E 走 ADB**（真实短信注入 + SmsForwarder 处理）
- **Strict 模式**防止意外退化（ADB 不可用时直接失败）
- **环境变量控制**一切行为（CI 友好）

## 测试分层

```
Layer 1: 单元测试（15 个）           ← 纯逻辑，无 IO
Layer 2: API 契约测试（43 个）        ← HTTP 通信，mock server
Layer 3: 性能测试（4 个）             ← 吞吐/延迟基准
Layer 4: E2E 测试（3 个）             ← 真机/模拟器全链路
```

总测试数：63 个（不含 manual 标记的 2 个测试）

## 回归测试策略

- **每次 push/PR**：Layer 1 + Layer 2（约 11 秒）
- **每次发版前**：Layer 1 + Layer 2 + Layer 3 + Layer 4（约 2 分钟）
- **每周**：Layer 1 + Layer 2 + Layer 3（CI 自动）
- **人工触发**：E2E 完整套件

## 环境兼容性矩阵

| 环境 | TRIGGER_MODE | ADB | 运行测试 |
|---|---|---|---|
| CI (ubuntu) | `http` | 不可用 | `uv run pytest` |
| macOS 本地 | `auto` | 可用 | `uv run pytest -m e2e` |
| macOS OrbStack | `adb` | mac_cmd | `SMS_INJECT_MODE=mac_cmd uv run pytest -m e2e` |
| 远程模拟器 | `adb` | ssh | `SMS_INJECT_MODE=ssh SMS_INJECT_SSH_HOST=... uv run pytest -m e2e` |
| Docker | `http` | 不可用 | `docker compose up` |
