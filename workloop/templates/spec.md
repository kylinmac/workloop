---
loop: wl-YYYYMMDD-01
status: clarifying   # clarifying | specified | executing | reviewing | done | blocked | cancelled
title: <一句话标题>
created: YYYY-MM-DD
base_commit: <创建 loop 时的提交 hash；review 的 diff 起点>
# blocked 时追加：
# blocked_from: <原阶段>
# resume_when: <恢复条件>
---

## 意图

<要达成什么，用用户视角的可观察结果描述。>

**非目标**：<明确不做什么，防止范围蔓延。没有则写"无"。>

<!-- cancelled 时在此记一行作废原因 -->

## 事实与假设

事实（每条带来源：文件路径、命令输出、用户原话）：

- <事实 1> —— 来源：<...>

假设（推测都写进来；影响"范围/验收/实现方式"的假设在进入 specified 前必须关闭）：

| ID | 假设 | 影响 | 状态 | 验证方式 / 关闭证据 |
|---|---|---|---|---|
| A1 | <推测内容> | 范围/验收/实现/无阻塞 | open | <打算怎么验证；关闭时贴证据> |

状态取值：`open`（未验证）/ `confirmed`（已证实）/ `rejected`（已证伪，需说明对计划的影响）。

## 风险

本次最大的不确定性是：<一句话>。对应的验证手段：<命令、原型或人工确认步骤>。

## 验收标准

每条必须是可观察结果，且写明验证方式（命令优先，人工步骤次之）。
勾选由 reviewer 在 review pass 后依据校验项 2/3 完成，执行阶段不勾。

- [ ] AC1: <可观察结果> —— 验证：`<命令>` 或 <人工步骤>
- [ ] AC2: ...
