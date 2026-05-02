# Contributing

欢迎为 SmsForwarder 测试项目贡献代码。

## 开发环境

```bash
git clone https://github.com/xkAustin/smsforwarder-test-project.git
cd smsforwarder-test-project
uv sync --frozen
```

## 代码风格

- Python ≥ 3.12
- 4 空格缩进
- 函数和模块使用 `snake_case`，类使用 `PascalCase`
- 公共 API 使用类型注解
- 优先使用 `dataclass` 表达结构化数据
- 导入顺序：标准库 → 第三方 → 本地模块
- 新文件头部添加 `from __future__ import annotations`

## 测试规范

### 标记使用

| 标记 | 何时使用 |
|---|---|
| （无标记） | 不依赖设备的快速测试 |
| `e2e` | 需要 Android 设备/模拟器 |
| `performance` | 性能基准测试 |
| `manual` | 需要人工触发或判断 |

### 测试命名

- 文件名：`test_<feature>.py`（如 `test_webhook_basic.py`）
- 函数名：`test_<what>_<condition>`（如 `test_webhook_receive_json_body`）

### 测试编写原则

- 每个测试只验证一个行为
- 使用已有 fixture，不要重复造轮子
- 使用 `mock_reset` fixture 确保测试隔离
- 使用 `wait_for_event` + `get_new_events` 处理异步流程
- 在断言中包含明确的错误消息

### 运行测试

提交前请运行：

```bash
# 快速开发子集
uv run pytest -m "not e2e and not performance and not manual"

# 如有相关改动
uv run pytest tests/unit/ -v
```

## Commit 规范

- 使用简短的祈使句主题
- 可使用前缀：`fix:`、`feat:`、`test:`、`refactor:`、`docs:`、`style:`
- 每条 commit 聚焦一个变更

示例：
```
test: cover GET/PUT/PATCH webhook methods
refactor: deduplicate adb serial selection logic
fix: correct __init.py filename typo
docs: add concurrency test documentation
```

## Pull Request 流程

1. 从 `main` 分支创建功能分支
2. 编写代码和测试
3. 确保所有测试通过（`uv run pytest -m "not e2e"`）
4. 如有新功能，更新相关文档
5. 提交 PR，包含：
   - 行为变更描述
   - 运行的验证命令
   - 关联的 Issue（如有）

## 目录约定

| 目录 | 用途 |
|---|---|
| `tools/` | 可复用的测试基础设施 |
| `tests/unit/` | 纯逻辑单元测试 |
| `tests/api_webhook/` | Webhook 契约与集成测试 |
| `tests/e2e_blackbox/` | 端到端黑盒测试 |
| `tests/performance/` | 性能基准 |
| `tests/utils/` | 测试辅助工具 |
| `scripts/` | 辅助脚本 |

## 项目配置

修改 `pyproject.toml` 时注意：
- 新增 pytest marker 需更新 `[tool.pytest.ini_options.markers]`
- 新增依赖需同步更新 `uv.lock`：`uv lock`
