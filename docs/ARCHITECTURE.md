# Architecture

## 系统全景

```
┌────────────────────────────────────────────────────────────────────┐
│                       被测试目标 (System Under Test)                 │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              SmsForwarder Android App                       │   │
│  │  app/src/SmsForwarder/                                      │   │
│  │                                                              │   │
│  │  ┌────────┐  ┌────────┐  ┌─────────┐  ┌────────────────┐  │   │
│  │  │ SMS    │  │ Call   │  │ App     │  │ Location/      │  │   │
│  │  │Receiver│  │Receiver│  │Notif Svc│  │Battery/Network │  │   │
│  │  └───┬────┘  └───┬────┘  └────┬────┘  └───────┬────────┘  │   │
│  │      └───────────┴────────────┴────────────────┘           │   │
│  │                          │                                   │   │
│  │                   ┌──────▼──────┐                            │   │
│  │                   │ Rule Engine │  ← 16 条匹配操作           │   │
│  │                   └──────┬──────┘                            │   │
│  │                          │                                   │   │
│  │                   ┌──────▼──────┐                            │   │
│  │                   │SendUtils    │  ← 16 个转发通道           │   │
│  │                   │ senderLogic │  ← ALL/UntilFail/          │   │
│  │                   └──────┬──────┘     UntilSuccess/Retry     │   │
│  └──────────────────────────┼──────────────────────────────────┘   │
│                             │ Webhook POST/GET/PUT                 │
└─────────────────────────────┼──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                      测试基础设施 (Test Infrastructure)               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 EventTrigger (tests/utils/trigger.py)          │  │
│  │                                                                  │
│  │  send_sms() ──→ 模式路由:                                       │
│  │    ├─ http   → send_webhook_form()  (POST form 到 mock)         │
│  │    ├─ adb    → inject_sms() → emulator                          │
│  │    ├─ auto   → 智能选择 (prefer HTTP, fallback ADB)              │
│  │    └─ manual → 占位返回                                         │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │           Mock Webhook Server (tools/mock_server/app.py)       │  │
│  │                                                                  │
│  │  FastAPI Application                                            │
│  │  ├─ CapturedEvent dataclass (10 fields)                         │
│  │  ├─ EVENTS: deque[CapturedEvent] (maxlen=5000)                  │
│  │  ├─ Fault injection state (mode, fail_count, delay_ms)          │
│  │  └─ Endpoints: /health, /reset, /events, /events/{id},          │
│  │                /fault/reset, /fault/config, /webhook            │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │               ADB Tools (tools/adb/)                           │  │
│  │                                                                  │
│  │  AdbClient:                                                     │
│  │  ├─ run() → 泛用 adb 命令封装                                   │
│  │  ├─ get_devices() → 解析 adb devices -l                         │
│  │  ├─ choose_serial() → 自动选择设备 (emulator-first)              │
│  │  └─ is_emulator_serial() → 正则匹配 emulator-<port>              │
│  │                                                                  │
│  │  inject_sms():                                                  │
│  │  ├─ local   → subprocess.run(["adb", ...])                      │
│  │  ├─ mac_cmd → subprocess.run(["mac", "adb", ...])               │
│  │  └─ ssh     → subprocess.run(["ssh", host, shlex.join(cmd)])    │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## 核心设计决策

### 1. 事件触发模式（EventTrigger）

**问题**：同一套测试需要同时支持有设备（模拟器）和无设备（CI）环境。

**方案**：通过 `TriggerMode` 枚举统一事件发送入口，测试代码调用 `event_trigger.send_sms()` 而无需关心底层实现。

```
send_sms(phone, text)
   │
   ├── mode=http   → POST form 到 mock /webhook （模拟 SmsForwarder 转发行为）
   ├── mode=adb    → ADB emu sms send 注入真实短信
   ├── mode=auto   → 优先 HTTP，设备可用时可选 ADB
   └── mode=manual → 返回占位结果，等待人工操作
```

**优势**：
- 同一测试可在有/无设备环境运行
- 测试代码与触发方式解耦
- 可通过环境变量切换模式（CI 友好）

### 2. Mock Server 设计

**问题**：SmsForwarder 将处理后的消息转发到配置的 Webhook 地址，如何在不修改 App 的情况下验证转发内容？

**方案**：实现一个轻量级 FastAPI 服务，扮演"webhook 接收端"角色：
- 捕获所有 HTTP 方法的请求
- 将请求元数据（method、path、headers、body）存储到内存双端队列
- 提供查询 API 供测试验证

**设计权衡**：
- **同步存储**：事件在响应返回前写入 deque。虽然端点声明为 `async`，但事件写入是同步操作，确保测试查询时事件已就绪
- **限界队列**：`deque(maxlen=5000)` 防止内存无限增长。适合测试场景（通常 < 100 个事件），不适合生产级 webhook 接收
- **故障注入**：通过全局状态 + 中间件逻辑实现，简单但非线程安全（测试中串行使用足够）

### 3. ADB 设备选择策略

**问题**：多设备场景下如何自动选择正确的 ADB 设备？

**层级**：
1. `--adb-serial` CLI 参数（最高优先级）
2. `ADB_SERIAL` 环境变量（`choose_serial` 内置）
3. 自动检测：优先 `emulator-<port>` 格式的模拟器
4. 回退：第一个 `state=device` 的设备

**模拟器识别**：正则 `^emulator-\d+$`，匹配 Android 模拟器命名规范。

### 4. 短信注入模式

**问题**：macOS 上 Docker 容器内的 ADB 如何访问宿主机的模拟器？

**方案**：三种注入模式覆盖不同运行环境：

| 环境 | 模式 | 命令 |
|---|---|---|
| Linux / 本地 macOS | `local` | `adb -s <serial> emu sms send ...` |
| macOS OrbStack | `mac_cmd` | `mac adb -s <serial> emu sms send ...` |
| 远程模拟器服务器 | `ssh` | `ssh <host> 'adb -s <serial> emu sms send ...'` |

SSH 模式下使用 `shlex.join()` 构造远程命令，防止参数注入。

### 5. 测试分层

```
┌─────────────────────────────────────────┐
│           E2E 测试 (e2e_blackbox/)        │  ← 最慢，需要设备
│   验证：ADB 注入 → App处理 → Webhook转发    │
├─────────────────────────────────────────┤
│         API 契约测试 (api_webhook/)        │  ← 中等，需要 mock server
│   验证：HTTP 方法、Header、Body、故障注入     │
├─────────────────────────────────────────┤
│           单元测试 (unit/)                 │  ← 最快，纯逻辑
│   验证：工具函数、数据类、安全边界            │
└─────────────────────────────────────────┘
```

CI 默认运行 API 契约 + 单元测试（63 个，约 11 秒），E2E 按需手动触发。

## 数据流

### E2E 测试流程

```
1. mock_reset()
   └─→ POST /reset + POST /fault/reset
       清空过往事件和故障状态

2. before = mock_counter()
   └─→ GET /events?limit=1
       记录起始事件数

3. event_trigger.send_sms(phone, text)
   ├─ [http] ──→ POST /webhook (form-encoded)
   └─ [adb]  ──→ ADB emu sms send → SmsForwarder → Webhook POST

4. wait_for_event(before_count=before, timeout_s=10)
   └─→ 轮询 GET /events?limit=1, 等待 count >= before + 1

5. cap = get_new_events(before_count=before)
   new_events = cap()
   └─→ GET /events?limit=N, 计算新增 items

6. parse_event_body(event)
   └─→ 解码 body_text / body_json / form
       执行断言
```

### 故障注入流程

```
1. POST /fault/config?mode=fail&fail_count=2
2. POST /webhook  →  500 (第 1 次)
3. POST /webhook  →  500 (第 2 次)
4. POST /webhook  →  200 (恢复正常)
5. 验证: GET /events → count=3, 3 条都记录了
```

## 关键文件详解

### `tests/conftest.py` — 测试生命周期

- **Session 级**：自动启动/停止 mock server（uvicorn）
- **Session 级**：`mock_base`、`trigger_config`、`adb`、`e2e_wait`
- **Function 级**：`mock_reset`（每次测试前清空状态）、`event_trigger`、`mock_counter`、`wait_for_event`、`get_new_events`、`get_latest_event`
- **CLI 注册**：11 个 pytest 自定义选项

### `tools/mock_server/app.py` — Mock Server

180 行 FastAPI 应用：
- `CapturedEvent` 数据类（10 个字段：id、ts_ms、method、path、query、headers、body_raw、body_json、body_form、response_status）
- 事件队列：`deque(maxlen=5000)`
- 故障注入：全局变量 `FAULT_MODE`、`FAIL_COUNT_LEFT`、`DELAY_MS`
- 安全钳位：`MAX_DELAY_MS=60000`、`MAX_FAIL_COUNT=10000`、`limit∈[1,500]`

### `tests/utils/trigger.py` — 事件触发系统

245 行核心抽象：
- `TriggerConfig`：不可变配置（frozen dataclass）
- `TriggerResult`：触发结果（mode、serial、used_fallback、detail）
- `EventTrigger`：4 个公开方法（`send_webhook_json`、`send_webhook_form`、`send_sms`、`send_sms_batch`）
- 内部：模拟器端口推导、控制台可达性检查、HTTP fallback 链

## 扩展点

### 添加新的转发通道测试

1. 在 `tools/mock_server/app.py` 中确认 mock server 已支持捕获该通道的请求格式
2. 在 `tests/api_webhook/` 创建测试文件
3. 使用 `requests` 模拟该通道的 HTTP 请求格式
4. 通过 `get_events()` + `parse_event_body()` 验证内容

### 添加新的 SmsForwarder 事件源测试

1. 如需 E2E 测试：使用 `adb` 模式 + `SmsReceiver` 的广播机制
2. 如需 API 测试：通过 `event_trigger.send_webhook_form()` 模拟转发请求

### 添加性能基准

1. 参考 `bench_webhook_receiver.py` 的结构
2. 实现 `reset()`、`run()`、`percentile()` 函数
3. 创建对应的 pytest 烟测（小规模验证）
4. 使用 `pytest.mark.performance` 标记
