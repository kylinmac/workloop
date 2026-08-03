---
name: agentloop-development
description: Handle only AgentLoop routing, coding preparation, implementation, and development handoff work.
---

# AgentLoop Development

Use for `ready_for_development`, `development_preparing`, and `developing`, or a
focused subflow in those states. Work from the `context` projection.

Read only:

- `references/agentloop/路由与阶段交接协议.md` when routing is undecided;
- the single file under `references/development/flows/` named by
  `routing.development.main_flow`;
- `references/rules/Git版本控制与可追溯规则.md` before the first code write,
  worktree operation, or commit.

Route once with `route`. In `development_preparing`, create only the artifacts
required by that route. Product-prototype work must generate its behavior
inventory, implementation matrix, user-flow slices, API contract, and data
model/reuse declaration before coding. Other non-trivial routes use
`development-assurance.yaml`.

When `collaboration_contract.required` is true, load the projected
`development_contract`, confirm it before entering development, and implement
only its shared API, data semantics, behavior, and acceptance scenarios. If it
is wrong or incomplete, update and reconfirm the contract; never infer a local
variant for one participant.

In `developing`, implement the confirmed acceptance obligations, run focused
checks, and create a traceable commit. Frontend business data must come from
formal APIs; backend data that belongs in a database must be queried there.
Create test data through seed/factory/fixtures.

Transition to `ready_for_verification` with the development artifact and exact
commit. Do not load Gate history, old Evidence runs, integration history, or
unselected development flows.
