# 开发记录

## 根因与影响

`host_hmac` 在提交 `9ab804d9df33a7a530b8bebe382e820a69a67449`（2026-07-31 15:08:50 +08:00）中加入并成为默认值，但插件没有 Codex 宿主 Gate adapter。普通需求确认与完成验收因此依赖一个当前运行环境无法生成的签名事件。

## 兼容设计

- 新项目普通 Gate 默认 `local_attestation`。
- `host_hmac` 保持显式可选且失败关闭。
- `destructive_action` 单独默认 `host_hmac`，不随普通 Gate 降级。
- 旧项目通过控制命令显式迁移，不在 runtime-upgrade 中静默覆盖用户策略。
- 回归覆盖普通确认、HMAC 负向、高风险 Gate、旧项目迁移和需求阶段 Hook 写入路径。

## 输入与需求版本

## 主开发流程及依据

## 现有系统调查

## 编码前产物及检查

- `development-assurance.yaml` 将复现和失败回归映射到分类义务。
- 兼容策略不自动覆盖旧项目；使用 `approval-mode` 显式迁移普通 Gate。

## 子流程与依赖

## 实现和修改文件

- `agentloop/examples/project.yaml`、`agentloop/schemas/project.schema.json`：普通 Gate 默认本地确认，破坏性 Gate 独立保持 HMAC。
- `plugins/development-process-agentloop/scripts/agentloop.py`：按 Gate 类型选择认证、增加迁移命令和 doctor 提示、修复需求阶段 Hook 与绝对路径归一化。
- `plugins/development-process-agentloop/scripts/test_agentloop.py`：增加本地确认、HMAC 负向、高风险 Gate、迁移和 Hook 回归。
- `agentloop/产物与目录协议.md`、插件 Skill：明确当前 Codex 能力与两种认证强度。
- `agentloop/issues/038-*`、`039-*`：分别记录不可达 HMAC Gate 和需求阶段 Hook 死锁。

## 开发自检

- `/usr/bin/python3 .../test_agentloop.py`：通过。
- `/opt/homebrew/bin/python3 .../test_agentloop.py`：通过。
- 插件目录校验、引用同步校验和 `git diff --check`：通过。

## 测试交接
