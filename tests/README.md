# Tests 目录参考

## 目录结构

```
tests/
├── conftest.py                  # Pytest 全局配置与 fixture
├── utils/                       # 测试工具库
│   ├── trigger.py               #   EventTrigger 事件触发系统
│   ├── http_payload.py          #   事件体解析（JSON/form/raw）
│   └── test_trigger_unit.py     #   触发逻辑单元测试
├── unit/                        # 单元测试（15 个）
│   ├── test_adb_client.py       #   ADB 客户端：设备选择逻辑
│   ├── test_sms_injector.py     #   短信注入器：SSH 安全校验
│   ├── test_sms_injector_mac.py #   短信注入器：mac_cmd 模式
│   └── test_mock_server_utils.py #  Mock server：_safe_decode 编解码
├── api_webhook/                 # Webhook API 契约测试（43 个）
│   ├── test_webhook_basic.py        #   JSON 请求体接收
│   ├── test_webhook_edge_cases.py   #   畸形 JSON、大载荷、空 Content-Type
│   ├── test_webhook_methods.py      #   GET/POST/PUT/PATCH/DELETE 方法
│   ├── test_webhook_concurrency.py  #   并发请求、事件顺序、计数单调性
│   ├── test_fault_injection.py      #   故障注入：失败 N 次 + 延迟
│   ├── test_security_bounds.py      #   故障参数安全上限
│   ├── test_no_retry_behavior.py    #   验证 500/超时不重试（manual 标记）
│   └── test_mock_server_regression.py # 回归：/events/{id}、Schema、限界队列
├── e2e_blackbox/                # 端到端测试（3 个）
│   ├── test_adb_sms_injection.py #   ADB 注入 → 转发 → Webhook 验证
│   └── test_e2e_no_retry.py      #   E2E 不重试验证
└── performance/                 # 性能基准（4 个）
    ├── bench_webhook_receiver.py     #  Webhook 基准 CLI 工具（独立运行）
    ├── bench_e2e_sms_throughput.py   #  E2E 吞吐基准 CLI 工具
    ├── test_webhook_receiver_perf.py #  Webhook 性能烟测（20 请求）
    └── test_e2e_throughput_perf.py   #  E2E 吞吐烟测（3 请求）
```

## 运行命令

```bash
# 全部测试（跳过 e2e 和性能）
uv run pytest

# 按目录运行
uv run pytest tests/unit/ -v                            # 单元测试
uv run pytest tests/api_webhook/ -v                     # API 契约测试
uv run pytest tests/e2e_blackbox/ -v                    # E2E 测试

# 按标记运行
uv run pytest -m "not e2e"                              # 默认 CI 子集
uv run pytest -m e2e                                     # 仅 e2e
uv run pytest -m performance                             # 仅性能
uv run pytest -m manual                                  # 仅人工触发

# 单个测试
uv run pytest tests/api_webhook/test_webhook_basic.py::test_webhook_receive_json_body -v

# 带 HTML 报告
uv run pytest --html=reports/report.html --self-contained-html
```

## 触发模式详解

### HTTP 模式（`TRIGGER_MODE=http`）

直接向 mock server 发送 HTTP 请求，无需 Android 设备。适用于 CI 和快速迭代。

```bash
TRIGGER_MODE=http uv run pytest tests/api_webhook/ -v
```

### ADB 模式（`TRIGGER_MODE=adb`）

通过 ADB 向模拟器注入真实短信，需要 SmsForwarder 应用正在运行并配置了转发规则。

```bash
TRIGGER_MODE=adb TRIGGER_STRICT=1 uv run pytest -m e2e -v
```

### SMS 注入子模式（`SMS_INJECT_MODE`）

控制 ADB 命令的执行方式：

| 值 | 机制 | 适用环境 |
|---|---|---|
| `local`（默认） | 直接在当前环境执行 `adb` | 本地开发、Linux CI |
| `mac_cmd` | 通过 OrbStack `mac` 命令在宿主机执行 `adb` | macOS + OrbStack |
| `ssh` | SSH 到远程宿主机执行 `adb` | 远程模拟器服务器 |

```bash
# OrbStack 环境
SMS_INJECT_MODE=mac_cmd ADB_SERIAL=emulator-5554 uv run pytest -m e2e

# SSH 远程模拟器
SMS_INJECT_MODE=ssh SMS_INJECT_SSH_HOST=user@remote uv run pytest -m e2e
```

## 核心 Fixture 说明

| Fixture | 作用域 | 说明 |
|---|---|---|
| `mock_base` | session | Mock server 基地址（字符串） |
| `mock_reset` | function | 测试前自动清空事件和故障状态 |
| `mock_counter` | function | 返回当前事件总数的可调用对象 |
| `wait_for_event` | function | 等待事件数达到目标值 |
| `get_new_events` | function | 根据 before_count 获取新增事件列表 |
| `get_latest_event` | function | 获取最新捕获的事件 |
| `event_trigger` | function | 统一事件触发入口（配合 trigger_config） |
| `trigger_config` | session | 触发配置（从 CLI/env 解析） |
| `adb` | session | ADB 客户端实例（自动检测设备） |

## E2E 测试前提

运行 E2E 测试需要满足以下条件：

1. Android 模拟器或真机已连接（`adb devices` 显示 `device` 状态）
2. SmsForwarder APK 已安装（`app/apk/SmsF_3.3.3.*.apk`）
3. SmsForwarder 已配置转发规则：
   - 匹配包含 `[E2E]` 标记的短信
   - 转发通道设置为目标 mock server 的 webhook 地址
4. Mock server 可被设备访问（注意 10.0.2.2 映射）

## 编写新测试

1. 选择对应目录（`unit/`、`api_webhook/`、`e2e_blackbox/`、`performance/`）
2. 文件名使用 `test_` 前缀
3. 测试函数名描述具体场景
4. 使用已有 fixture（`mock_base`、`mock_reset`、`wait_for_event` 等）
5. 添加合适的 pytest marker
6. API 测试：验证 HTTP 状态码、响应 schema、事件内容
7. E2E 测试：使用 `event_trigger.send_sms()` + `wait_for_event()` + `parse_event_body()`
