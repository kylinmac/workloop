---
name: workloop-plan-cn
description: 把已明确的 Workloop 需求转换为小型可验证工作项。适用于创建或修订 plan.md、映射验收覆盖、隔离执行范围，或为共享 API、数据、行为及验收边界建立可选契约。
---

# Workloop 计划

把 `../workloop/assets/templates/plan.md` 复制到 `.workloop/loops/<id>/plan.md`。

1. 从验收标准反推工作项，每项映射稳定 AC ID。
2. 每个工作项应能在一个干净上下文中完成，并让系统保持可验证状态。
3. 明确依赖、允许路径、输出，以及精确验证命令或人工步骤。
4. 用明确工作项或验证覆盖需求中的最大风险。
5. 仅当两个模块、Agent 或交付单元共享语义时添加契约；记录稳定 `CTn` ID、供给方、消费方、关联工作项、可观察声明和验证方法。
6. 原始日志放在 `plan.md` 外，只记录紧凑的证据行：稳定 `EVn` ID、结果、时间、来源路径和覆盖的验收或契约 ID。

实现前只把一个就绪项设为 `active`，其余未完成项为 `pending` 或 `blocked`。所有 AC 已覆盖且契约引用双向完整后，才能设置 `status: executing`。

执行中范围或验收变化时，先修订 `spec.md`。执行日志只记录计划偏差。
