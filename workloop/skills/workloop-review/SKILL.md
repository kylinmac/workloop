---
name: workloop-review
description: Use when a loop reaches reviewing status and needs cognitive consistency verification, or when dispatched as an independent reviewer for a workloop loop.
---

# Workloop Review：认知一致性校验

## 派发协议（执行者的最后一步）

执行者把 status 改为 `reviewing` 后，唯一剩余职责是**发起**审查，然后等待结论：

1. 派一个未参与执行的干净上下文（子代理 / 新会话 / 人）。
2. 给审查者的输入固定为一句话：`按 workloop-review 审查 .workloop/loops/<loop-id>/，diff 范围 git diff <base_commit>..HEAD`。不给对话历史、不给解释。
3. review.md 由审查者写入。审查者必须在文中留下**外部锚**：子代理会话 ID、独立会话标识或人的署名——无锚的 review 按宪法第 2 条无效。
4. 结论出来后，执行者按结论**机械执行**：pass → 完成 workloop-memory 更新并勾选 spec 验收标准（依据校验项 2/3），status 改 `done`；fail → 按指定位置退回。执行者对 fail 有异议时升级给人裁决，裁决前 fail 有效，不得单方面推翻。

| 合理化借口 | 现实 |
|---|---|
| "任务简单，我自己顺手 review 一下" | 自我报告审计不了自己，这正是旧系统失败的根因。派独立视角。 |
| "证据都在，走个形式就行" | 语义抽查必须真实重跑，否则 review 只是第二层自我声明。 |

## 审查者的工作

只读四样：spec.md、plan.md、`git diff <base_commit>..HEAD`、plan 中各任务证据。不读执行过程的对话历史——审查的是产物，不是叙述。

产物 `review.md`（模板 `workloop/templates/review.md`），六项校验逐项给结论和依据：

1. 每条验收标准 ↔ plan 任务（映射完整性）
2. 每条验收标准 ↔ diff 实现（语义验证：实现的行为是否就是 AC 说的行为，不是名字像）
3. 证据真实性（输出与验证命令匹配、带日期或提交 hash、非编造非过期）
4. 假设表完整性（影响分类合理、没有应关未关的假设、rejected 假设无残留影响）
5. diff 无范围蔓延（没有 spec 意图之外的变更）
6. 最大风险确实被验证覆盖

**语义抽查**：选 1-2 条最关键的 AC，亲自重跑验证命令，比对结果。这是唯一能击穿"证据造假/过期"的手段，不可省略。

## 结论

- **pass**：无保留通过。
- **fail**：列问题清单并指明退回位置——实现问题退 `executing`，需求或假设问题退 `clarifying`。不允许"有保留地通过"。
