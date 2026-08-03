---
name: workloop-plan
description: Use when a loop's spec is complete (status specified) and tasks need to be generated before execution starts.
---

# Workloop Plan：计划生成

## 产物

`.workloop/loops/<id>/plan.md`，从 `workloop/templates/plan.md` 复制。

## 规则

1. **从验收标准反推任务**，不是从实现思路正推。每个任务标注它覆盖哪条 AC；有 AC 没被任何任务覆盖，计划不完整。
2. **每个任务一个上下文能完成**（一次会话内读得完相关代码、写得完改动、跑得完验证）。装不下就拆；拆完仍装不下，说明该拆成多个 loop——回到 workloop-spec 把需求切开，不要造更大的 plan。
3. **每个任务写验证方式**：优先可执行命令；确实无法命令化的写人工步骤（谁、做什么、看到什么算过）。
4. **风险应对区块**：写明 spec 声明的最大风险由哪个任务或验证覆盖。风险没人覆盖的计划不得进入执行。
5. 计划是动态的：执行中发现假设被推翻或任务需要增删时，允许改 plan，但必须在执行日志记一行，且若影响范围或验收，先回改 spec。

任务清单完成后，把 status 改为 `executing`。

## 常见错误

| 错误 | 纠正 |
|---|---|
| 按技术层拆任务（前端/后端/测试） | 按可验证的行为切；每个任务完成后系统处于可验证状态 |
| 验证方式写"跑测试"这种泛称 | 写出具体命令和期望结果 |
| 计划里塞满流程性任务（"更新文档状态"） | 任务只包含改变系统行为或产出证据的工作 |
