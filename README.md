# SmsForwarder 测试项目

这是一个针对开源项目 **SmsForwarder** 构建的完整测试工程，
覆盖黑盒测试、接口测试、自动化测试、性能测试，并逐步引入白盒测试。

## 测试内容

- 黑盒测试：核心功能与异常场景验证
- 接口测试：Webhook / HTTP 转发接口契约验证
- 自动化测试：基于 Python + pytest 的可回归测试
- 性能测试：高频消息与稳定性测试
- 白盒测试：核心逻辑单元测试

## 技术栈

- Python
- pytest
- requests / httpx
- 自定义 mock Webhook Server
- GitHub Actions


## 使用说明

详细的测试说明与目录解释请查看 `tests/README.md`

## 快速运行

全量测试：

```
uv run pytest
```

只跑 e2e：

```
uv run pytest -m e2e
```

不跑 e2e/performance/manual：

```
uv run pytest -m "not e2e"
```

## Docker 环境运行

本项目支持使用 Docker Compose 构建隔离的测试环境。

### 构建环境

```bash
docker compose build
# 或者使用 Makefile
make build
```

### 运行测试

运行非 E2E 测试（不需要设备）：

```bash
docker compose up --exit-code-from tests
# 或者
make test
```

### 清理环境

```bash
docker compose down -v
# 或者
make clean
```
