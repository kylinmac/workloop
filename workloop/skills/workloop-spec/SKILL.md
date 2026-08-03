---
name: workloop-spec
description: Use when a new requirement arrives or an existing loop is in clarifying status, before any planning or coding. Covers intent analysis, assumption extraction, and risk assessment.
---

# Workloop Spec：意图、假设、风险

## 产物

`.workloop/loops/<id>/spec.md`，从 `workloop/templates/spec.md` 复制。四个区块全部必填。

## 步骤

1. **意图分析**：把原始输入改写为用户视角的可观察结果，并写出非目标。写完向用户复述确认——意图错了后面全错。
2. **假设提取**：逐句检查自己对需求的理解，凡是没有来源的判断（"应该""大概""通常"）都进假设表，标注影响类型（范围/验收/实现/无阻塞）。
3. **假设关闭**：影响范围或验收的假设，用最便宜的方式立即验证——读代码、跑命令、问用户。关闭时在表格里贴证据。**不允许**带着 open 的阻塞假设进入 specified。注意：影响分类会被 review 复核，降级假设混过 gate 会在校验项 4 被抓回。
4. **风险评估**：一句话写出本次最大不确定性和对应验证手段。只写最大的一个，次要风险如需要就转成验收标准。
5. **验收标准**：每条是可观察结果 + 验证方式。验证方式必须具体到命令或可执行的人工步骤；写不出验证方式的验收标准说明意图还没想清楚，回到第 1 步。

全部完成且阻塞假设关闭后，把 status 改为 `specified`。验收标准的勾选不在本阶段——它由 reviewer 在 review pass 后依据校验结论完成。

## 常见错误

| 错误 | 纠正 |
|---|---|
| 把假设写成事实（"接口是兼容的"） | 没有来源的陈述一律进假设表 |
| 假设表只写了技术假设 | 范围假设（"用户只要 X 不要 Y"）最危险，优先提取 |
| 验收标准写成实现描述（"新增一个函数"） | 改写为外部可观察结果（"调用 X 返回 Y"） |
| 为了推进把阻塞假设改标"无阻塞" | 影响类型由假设被推翻的后果决定，不由进度压力决定 |
