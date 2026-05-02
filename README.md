# SmsForwarder 测试项目

[![CI](https://github.com/xkAustin/smsforwarder-test-project/actions/workflows/python-tests.yml/badge.svg)](https://github.com/xkAustin/smsforwarder-test-project/actions/workflows/python-tests.yml)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

针对开源 Android 应用 [SmsForwarder](https://github.com/pppscn/SmsForwarder) 构建的工程级测试基础设施。覆盖 API 契约、黑盒端到端、性能基准和单元测试，支持本地开发与 CI 无缝运行。

## 架构概览

```
                         ┌──────────────────────┐
                         │   SmsForwarder App   │  ← 被测试目标（Android）
                         │  (app/src/SmsForwarder) │
                         └──────────┬───────────┘
                                    │ SMS / 通知 / 来电 / 定位 / 电量 / 网络
                                    ▼
┌───────────────────────────────────────────────────────────────┐
│                    测试触发层 (EventTrigger)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │   HTTP   │  │   ADB    │  │   Auto   │  │   Manual     │ │
│  │ 直发POST │  │ 短信注入  │  │ 智能选择  │  │  人工触发    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
└───────┼──────────────┼─────────────┼───────────────┼─────────┘
        │              │             │               │
        ▼              ▼             ▼               ▼
┌───────────────────────────────────────────────────────────────┐
│              Mock Webhook Server (FastAPI)                     │
│  POST /webhook  ← 捕获事件    GET /events  ← 查询事件          │
│  POST /reset    ← 清空数据    POST /fault/config ← 故障注入    │
│  GET /health    ← 健康检查    GET /events/{id} ← 按ID查询      │
└───────────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置条件

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器
- （可选）Docker 用于容器化运行
- （E2E 测试需要）Android 模拟器/设备 + ADB

### 安装与运行

```bash
# 克隆仓库
git clone https://github.com/xkAustin/smsforwarder-test-project.git
cd smsforwarder-test-project

# 安装依赖
uv sync --frozen

# 运行全量测试（跳过 e2e）
uv run pytest

# 运行指定标记的测试
uv run pytest -m "not e2e"                         # 跳过 e2e
uv run pytest -m e2e                                # 仅 e2e
uv run pytest -m performance                        # 仅性能测试
uv run pytest -m manual                             # 仅人工触发测试
uv run pytest -m "not e2e and not performance"      # 快速子集（开发用）

# 运行单个测试文件
uv run pytest tests/api_webhook/test_webhook_basic.py

# 运行单个测试函数
uv run pytest tests/api_webhook/test_webhook_basic.py::test_webhook_receive_json_body

# 生成 HTML 报告
uv run pytest --html=reports/report.html --self-contained-html
```

### Docker 运行

```bash
# 构建并运行
make build && make test

# 或直接使用 docker compose
docker compose build
docker compose up --exit-code-from tests
```

## 测试分类

| 标记 | 目录 | 说明 |
|---|---|---|
| （无标记） | `tests/api_webhook/`、`tests/unit/` | 接口契约 + 单元测试，CI 默认运行 |
| `e2e` | `tests/e2e_blackbox/` | 端到端测试，需要 Android 设备/模拟器 |
| `performance` | `tests/performance/` | 吞吐与延迟基准测试 |
| `manual` | `tests/api_webhook/test_no_retry_behavior.py` 等 | 需要人工触发或验证的测试 |

## 触发模式

测试通过 `EventTrigger` 统一发送事件。触发模式通过 `TRIGGER_MODE` 环境变量或 `--trigger-mode` CLI 参数控制：

| 模式 | 行为 | 适用场景 |
|---|---|---|
| `auto` | 优先 HTTP，可降级 ADB（默认） | 通用 |
| `http` | 直接 POST 到 mock server | CI、无设备环境 |
| `adb` | 通过 ADB 注入真实短信 | E2E、模拟器 |
| `manual` | 返回占位结果，等待人工操作 | 真机验证 |

## 配置参考

### 环境变量 / CLI 参数完整列表

| 环境变量 | CLI 参数 | 默认值 | 说明 |
|---|---|---|---|
| `TRIGGER_MODE` | `--trigger-mode` | `auto` | 触发模式：`auto`/`adb`/`http`/`manual` |
| `TRIGGER_STRICT` | `--trigger-strict` | `0` | 为 `1` 时 ADB 不可用则直接失败 |
| `TRIGGER_PREFER_ADB` | `--trigger-prefer-adb` | `0` | auto 模式下优先走 ADB |
| `MOCK_BASE` | `--mock-base` | `http://127.0.0.1:18080` | Mock server 地址 |
| `MOCK_HOST` | — | `127.0.0.1` | Mock server 绑定地址 |
| `MOCK_PORT` | — | `18080` | Mock server 监听端口 |
| `NO_AUTO_MOCK_SERVER` | — | `0` | 为 `1` 时跳过自动启动 server |
| `ADB_SERIAL` | `--adb-serial` | (自动检测) | ADB 设备序列号 |
| `SMS_INJECT_MODE` | `--sms-inject-mode` | `local` | 短信注入方式：`local`/`mac_cmd`/`ssh` |
| `SMS_INJECT_MAC_CMD` | `--sms-inject-mac-cmd` | `mac` | OrbStack `mac` 命令名 |
| `SMS_INJECT_SSH_HOST` | `--sms-inject-ssh-host` | — | SSH 宿主机地址 |
| `ALLOW_DEVICE_SMS` | `--allow-device-sms` | `0` | 允许对真机进行 best-effort 短信注入 |
| `E2E_WAIT` | `--e2e-wait` | `3` | E2E 等待秒数（已弃用，优先使用 `wait_for_event`） |

### 运行示例

```bash
# HTTP 模式运行全部 api 测试
TRIGGER_MODE=http uv run pytest tests/api_webhook/ -v

# ADB 严格模式运行 e2e
TRIGGER_MODE=adb TRIGGER_STRICT=1 uv run pytest -m e2e -v

# macOS OrbStack 模拟器环境
SMS_INJECT_MODE=mac_cmd ADB_SERIAL=emulator-5554 uv run pytest -m e2e

# 无设备快速开发
NO_AUTO_MOCK_SERVER=1 TRIGGER_MODE=http uv run pytest -m "not e2e"
```

## 项目结构

```
.
├── tools/                          # 测试基础设施
│   ├── mock_server/                # Mock Webhook Server（FastAPI）
│   │   └── app.py                  #   - 事件捕获与查询 API
│   │                               #   - 故障注入（ok/fail/delay）
│   │                               #   - 限界队列（MAX_EVENTS=5000）
│   └── adb/                        # ADB 工具
│       ├── adb_client.py           #   - 设备管理、序列号选择
│       └── sms_injector.py         #   - 短信注入（local/mac_cmd/ssh）
│
├── tests/                          # 测试套件
│   ├── conftest.py                 #   - Pytest 配置与 fixture
│   ├── utils/                      #   - 测试工具
│   │   ├── trigger.py              #     EventTrigger 触发系统
│   │   ├── http_payload.py         #     事件体解析工具
│   │   └── test_trigger_unit.py    #     触发逻辑单元测试
│   ├── unit/                       #   单元测试（3 个文件，15 个测试）
│   ├── api_webhook/                #   API 契约测试（8 个文件，43 个测试）
│   ├── e2e_blackbox/               #   端到端测试（2 个文件，3 个测试）
│   └── performance/                #   性能基准（2 个独立工具，2 个烟测）
│
├── scripts/                        # 辅助脚本
│   ├── start_mock_server.sh        #   独立启动 mock server
│   └── run_e2e.sh                  #   E2E 一键运行脚本
│
├── app/                            # 被测试目标（不参与测试执行）
│   ├── src/SmsForwarder/           #   SmsForwarder 源码
│   └── apk/SmsF_3.3.3.*.apk       #   测试用 APK
│
├── .github/workflows/              # CI/CD
│   ├── python-tests.yml            #   push/PR 自动运行（ubuntu）
│   └── e2e.yml                     #   手动触发 E2E（self-hosted）
│
├── Dockerfile                      # 容器镜像
├── docker-compose.yml              # 双服务编排（tests + mock_server）
├── Makefile                        # build / test / clean
└── pyproject.toml                  # 项目配置与 pytest 设置
```

## Mock Server API 参考

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查，返回 `{"ok": true, "events": <count>}` |
| `GET` | `/events` | 列出事件，`?limit=N`（默认 50，最大 500） |
| `GET` | `/events/{id}` | 按 UUID 查询单个事件，404 表示不存在 |
| `POST` | `/reset` | 清空所有事件 |
| `*` | `/webhook` | 捕获事件（支持所有 HTTP 方法） |
| `POST` | `/fault/reset` | 重置故障注入状态 |
| `POST` | `/fault/config` | 配置故障注入：`mode=ok\|fail\|delay`、`fail_count`、`delay_ms` |

### 故障注入模式

```bash
# 接下来 2 次请求返回 500
curl -X POST http://127.0.0.1:18080/fault/config -d 'mode=fail&fail_count=2'

# 每次请求延迟 500ms
curl -X POST http://127.0.0.1:18080/fault/config -d 'mode=delay&delay_ms=500'

# 恢复正常
curl -X POST http://127.0.0.1:18080/fault/reset
```

## CI/CD

### 自动运行（push/PR）

`.github/workflows/python-tests.yml` 在每次 push 和 PR 时触发：
- Ubuntu 最新版，Python 3.12
- 运行除 `e2e` 外的全部测试
- 生成 JUnit XML + HTML 报告并上传为 artifact

### 手动触发（E2E）

`.github/workflows/e2e.yml` 通过 `workflow_dispatch` 手动触发：
- 运行于 self-hosted runner（需要 ADB 和模拟器）
- 可配置参数：`adb_serial`、`mock_port`、`mock_host`、`e2e_wait`

## 技术栈

| 组件 | 版本 | 用途 |
|---|---|---|
| Python | ≥3.12 | 运行环境 |
| pytest | ≥9.0 | 测试框架 |
| FastAPI + uvicorn | — | Mock server |
| requests | ≥2.33 | HTTP 客户端 |
| pydantic | — | 数据校验 |
| uv | — | 包管理器 |
| Docker | — | 容器化运行 |

## 贡献指南

详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 安全策略

详见 [SECURITY.md](./SECURITY.md)。
