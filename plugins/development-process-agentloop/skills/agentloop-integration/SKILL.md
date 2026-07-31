---
name: agentloop-integration
description: Handle only AgentLoop composite or epic orchestration, subflow scheduling, integration commits, and parent aggregation.
---

# AgentLoop Integration

Use for parent `orchestrating` or a passed subflow awaiting aggregation. Work
from the parent `context` projection. Use `context --subflow-id <id>` before
doing work inside one subflow; do not load every subflow body together.

Read only:

- `references/agentloop/路由与阶段交接协议.md` for dependency scheduling;
- `references/rules/Git版本控制与可追溯规则.md` for merge/checkpoint work;
- `references/agentloop/执行重试与恢复协议.md` after a failed unit.

Advance subflows only with `transition --subflow-id`; parent orchestration does
not grant coding permission. Merge verified source commits into the declared
integration branch, rerun each delivery's required checks on one integration
head, and use `integration-transition` plus `integration-checkpoint` when
integration verification is required.

Aggregate acceptance, prototype coverage, executable automation, valid visual
Evidence, data lineage, and exact integration-commit binding—not merely child
`passed` states. Cross-repository epics additionally preserve dependency
versions, delivery commits, deployment order, compatibility, and rollback.

Do not load full child histories, unrelated subflow artifacts, or requirement
clarification material. Open a focused projection only when that unit is next.
