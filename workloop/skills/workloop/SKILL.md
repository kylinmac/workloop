---
name: workloop
description: Use when starting any development requirement, resuming an interrupted task, or unsure which workloop phase applies. Entry point and router for the workloop methodology.
---

# Workloop 入口

## 核心原则

只控制认知质量和证据真实性，过程给自由。每阶段一份固定 Markdown 产物，宪法见 `workloop/README.md`（必读）。

## 路由

新需求：列 `.workloop/loops/` 取当日最大序号 +1 生成 loop-id，创建目录，记录 `base_commit`（推荐建同名分支），进入 workloop-spec。已有 loop：读 `spec.md` frontmatter 的 `status`：

| status | 使用 skill | 本阶段唯一产物 |
|---|---|---|
| clarifying | workloop-spec | spec.md |
| specified | workloop-plan | plan.md |
| executing | workloop-execute | plan.md 内证据 + 提交 |
| reviewing | workloop-review（独立视角，按其派发协议） | review.md；pass 后接 workloop-memory |
| blocked | 读 frontmatter 的 `resume_when`，条件解除后按 `blocked_from` 回原阶段 | — |
| done / cancelled | 终态，不再改动 | — |

## 恢复

中断后恢复只需读三个文件：spec.md（状态+假设+验收）、plan.md（进度+证据）、memory.md（教训）。读完即可继续，不需要其他上下文。

## 铁律

- 开始任何阶段前，先读 `.workloop/memory.md` 中触发条件匹配当前改动的条目；命中并实际使用了某条时，更新该条的"最近触发"列。
- 阶段推进条件见 README「阶段推进条件」表，不满足不得改 status。
- 需求变化：先改 spec（假设表、验收标准），再改 plan，顺序不可反。需求作废：status 改 `cancelled` 并在 spec 记一行原因。
