---
name: workloop-spec-cn
description: 在计划或编码前生成或修订 Workloop 需求说明。适用于新需求、澄清循环、需求变化、意图分析、假设提取、风险评估和可观察验收标准。
---

# Workloop 需求理解

把 `../workloop/assets/templates/spec.md` 复制到 `.workloop/loops/<id>/spec.md`。

1. 把请求改写为可观察的用户结果，并明确非目标；实质歧义必须向用户确认。
2. 有来源的事实与无来源的假设分开记录。
3. 假设影响分类为 `scope`、`acceptance`、`implementation` 或 `non-blocking`。
4. 用成本最低的真实证据关闭影响范围和验收的假设；二者仍为 `open` 时不得进入 `specified`。
5. 写出唯一最大不确定性及其验证方法；其他实质风险转换为验收标准。
6. 每条验收标准使用稳定 `ACn` ID、可观察结果，以及具体命令或人工验证步骤。

只有产物完整且阻塞假设关闭后才能设置 `status: specified`。验收复选框保持未勾选，由独立审查者在实现后勾选。

不得用以下内容替代要求：

- 用实现细节代替可观察验收结果；
- 用“应该”“可能”或惯例代替来源；
- 仅为推进状态而把假设改标为 `non-blocking`。
