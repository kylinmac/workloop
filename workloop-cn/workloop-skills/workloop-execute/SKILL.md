---
name: workloop-execute-cn
description: 实现活动 Workloop 工作项并采集真实证据。适用于 spec 状态为 executing、需要用任务投影限制上下文和文件范围，或工作项即将标记完成但尚未执行验证。
---

# Workloop 执行

对唯一 `active` 工作项重复以下闭环：

```text
加载投影 → 在范围内实现 → 运行验证 → 保存原始证据 → 索引证据 → 标记完成 → 提交
```

插件可用时生成工作项投影；否则只加载该工作项引用的 AC、假设、契约、依赖、范围和匹配记忆。

使用真实证据。完整输出、截图或报告保存在项目中，证据索引只添加紧凑的 `EVn` 行。所有已列证据 ID 存在并覆盖任务的 AC 或契约之前，工作项不得设为 `done`。

假设被证伪时改为 `rejected`。范围或验收变化时返回 `clarifying`。需要外部信息或权限时，设置 `blocked`、`blocked_from: executing` 和精确 `resume_when` 条件。

所有工作项为 `done`、证据引用均可解析且改动已经提交后，设置 `status: reviewing`，并把 `workloop-review` 交给未参与实现的上下文。不得为自己的实现撰写审查结论。
