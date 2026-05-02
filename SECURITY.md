# Security Policy

## 适用对象

本安全策略适用于 [SmsForwarder 测试项目](https://github.com/xkAustin/smsforwarder-test-project) 的全部代码，包括 mock server、测试套件、ADB 工具和 CI/CD 配置。

## 需要关注的安全领域

### Mock Server 安全边界

Mock server（`tools/mock_server/app.py`）已实施以下防护：

- **内存保护**：事件队列上限 `MAX_EVENTS = 5000`，防止无限制内存增长
- **故障注入上限**：`MAX_DELAY_MS = 60000`（60 秒）、`MAX_FAIL_COUNT = 10000`，防止 DoS
- **输入钳位**：`/events?limit=N` 钳位到 `[1, 500]`，防止超大查询
- **解码安全**：`_safe_decode` 使用 `errors="replace"` 处理非 UTF-8 输入

注意事项：

- Mock server 仅供测试使用，不应暴露在公网上
- Mock server 无身份认证机制，仅限本地（`127.0.0.1`）或内网访问
- 故障注入端点（`/fault/config`）无额外鉴权

### SSH 短信注入

`tools/adb/sms_injector.py` 使用 `shlex.join()` 构造 SSH 远程命令，防止命令注入。修改注入逻辑时：
- 始终通过 `shlex.join()` 或等效机制传递参数
- 当 `ssh_host` 为空时拒绝 SSH 模式调用（已有 `ValueError` 检查）
- 不要将未经验证的用户输入拼接到 shell 命令中

### CI/CD 安全

- `.github/workflows/python-tests.yml` 配置了 `permissions: contents: read`
- `.github/workflows/e2e.yml` 仅支持 `workflow_dispatch` 手动触发
- CI 中的 secret 通过 GitHub Secrets 注入（`ADB_SERIAL` 等），禁止硬编码
- E2E runner 为 self-hosted，需确保运行环境安全

### 依赖安全

- 使用 `uv.lock` 锁定所有依赖版本
- GitHub Dependabot 自动监控依赖漏洞（参见 `.github/dependabot.yml`）

## 报告漏洞

如果你发现安全漏洞，请执行以下操作：

1. **不要**在公开 Issue 中报告
2. 发送邮件至项目维护者（参见提交记录中的邮箱）
3. 在报告中包含：
   - 受影响的组件与版本
   - 复现步骤
   - 潜在影响说明
   - 建议的修复方案（如有）

安全修复将在下一个补丁版本中发布，并将在 CHANGELOG 中注明。

## 支持的版本

此仓库为测试项目，仅支持当前 `main` 分支。安全修复通过 PR 合入并立即生效。

## 安全检查清单

修改以下组件时请参考对应检查项：

### Webhook 处理变更
- [ ] 请求体大小是否有限制？
- [ ] 内容类型解析是否安全？
- [ ] JSON 解析失败的降级行为是否正确？

### Mock Server 端点变更
- [ ] 新端点是否需要限流或大小限制？
- [ ] 参数验证是否覆盖负数、超大值、空值？
- [ ] 错误响应是否避免泄露内部状态？

### ADB 工具变更
- [ ] shell 参数是否通过 `shlex.join()` 传递？
- [ ] SSH 主机和命令是否经过验证？
- [ ] 用户提供的文本是否被正确转义？

### CI/CD 变更
- [ ] workflow 文件的 `permissions` 是否设为最小权限？
- [ ] 是否避免在日志中打印 secret？
- [ ] 自托管 runner 的环境是否隔离？
