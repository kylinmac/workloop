# Codex 宿主未接入 HMAC 导致人工 Gate 不可达

## 现象

用户已在 Codex 对话中明确确认，普通需求或完成 Gate 仍要求 `AGENTLOOP_GATE_EVENT_SECRET` 和事件签名；界面没有能产生该签名的 AgentLoop 确认入口。

## 影响

新项目默认 `host_hmac` 时会停在人工 Gate，用户重复确认也无法合法推进。

## 根因

提交 `9ab804d9df33a7a530b8bebe382e820a69a67449` 于 2026-07-31 15:08:50 +08:00 引入 HMAC 校验并设为默认，但插件没有同步交付 Codex 宿主 Gate adapter、能力发现或兼容默认值。

## 旧门禁为何没拦截

回归测试自行注入测试密钥并生成签名，只证明校验算法可用，没有在真实“宿主不注入密钥”的环境验证 Gate 可达性。

## 修复

- 新项目普通 Gate 默认 `local_attestation`。
- 保留显式 `host_hmac` 并继续失败关闭。
- `destructive_action` 单独默认 `host_hmac`。
- 增加 `approval-mode` 迁移命令和 `doctor` 恢复提示，不静默覆盖旧项目策略。

## 回归

- 新项目无需 HMAC 可记录普通确认。
- 显式 `host_hmac` 的伪造签名仍失败。
- 普通 Gate 使用本地确认时，破坏性 Gate 缺少宿主密钥仍失败。
- 旧项目切换普通认证后可继续。

## 预防规则

依赖宿主能力的强制 Gate 必须同时提供能力检测、可执行适配器和可达恢复路径；测试不得只靠测试进程注入宿主凭据证明生产可用。
