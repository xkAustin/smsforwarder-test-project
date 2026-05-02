# Changelog

本文件记录 SmsForwarder 测试项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

### 新增
- **HTTP 方法覆盖测试** (`test_webhook_methods.py`)：GET/POST/PUT/PATCH/DELETE 方法、HMAC-SHA256 签名、Basic Auth、自定义 Header、Form-encoded、Unicode
- **并发与一致性测试** (`test_webhook_concurrency.py`)：50 线程并发 POST、混合方法并发、事件排序、reset 负载测试、计数单调性
- **Mock server 回归测试** (`test_mock_server_regression.py`)：`/events/{id}` 端点、UUID 唯一性、Schema 验证、deque 边界、reset 幂等性、limit 钳位

### 修复
- 修复 `tools/adb/__init.py` → `__init__.py` 文件名拼写错误
- 删除 `test_webhook_edge_cases.py` 中冗余的 reset 调用
- 重命名 `test_missing_content_type` → `test_empty_content_type` 以准确描述行为

### 重构
- 删除 `tests/conftest.py` 中的 `pick_adb_serial()`，统一到 `AdbClient.choose_serial()`
- Mock server 启动：`subprocess.PIPE` → `subprocess.DEVNULL` 消除管道缓冲区溢出风险

### 文档
- 重写 `README.md`：完整架构图、快速开始、配置参考、Mock server API 参考
- 重写 `tests/README.md`：更新目录结构、触发模式详解、核心 fixture 说明、E2E 前提
- 新增 `CONTRIBUTING.md`：开发环境、代码风格、测试规范、Commit/Pull Request 指南
- 重写 `SECURITY.md`：安全边界、SSH 注入防护、CI 安全、安全检查清单

## [0.1.0] - 2025-01

### 新增
- Mock Webhook Server（FastAPI）：事件捕获、故障注入、限界队列
- ADB 客户端与短信注入器（local/mac_cmd/ssh 三种模式）
- Webhook API 契约测试（基础 JSON、畸形 JSON、大载荷、故障注入、安全上限）
- E2E 测试（ADB 注入 → 转发 → Webhook 验证、不重试验证）
- 性能基准（Webhook 吞吐、E2E 吞吐）
- 单元测试（`_safe_decode`、`choose_serial`、`inject_sms`、`_emulator_port`）
- CI/CD：GitHub Actions（python-tests push/PR 自动运行、e2e 手动触发）
- Docker 容器化支持
- EventTrigger 事件触发系统（HTTP/ADB/Auto/Manual 模式）

### 安全
- Mock server 故障注入参数安全上限（`MAX_DELAY_MS=60000`、`MAX_FAIL_COUNT=10000`）
- SSH 短信注入使用 `shlex.join()` 防命令注入
- GitHub Actions 配置最小权限（`contents: read`）
- 修复 Broad Exception 处理（mock server `/reset` 端点）
