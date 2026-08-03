---
name: workloop-execute
description: Implement an active Workloop work item and capture real evidence. Use when spec status is executing, when a task projection should constrain context and file scope, or when a task is about to be marked done without its verification being run.
---

# Workloop Execute

For the single `active` work item, repeat:

```text
load projection → implement within scope → run verification → store raw evidence → index Evidence → mark done → commit
```

Generate the plugin projection when available. Otherwise load only the work item's referenced ACs, assumptions, Contracts, dependencies, scopes, and matching memory entries.

Use real evidence. Store full output, screenshot, or report in the project; add only a compact `EVn` row to the Evidence index. A task is not `done` until every listed Evidence ID exists and covers the task's ACs or Contracts.

If an assumption is disproved, update it to `rejected`. Return to `clarifying` when scope or acceptance changes. If external information or authority is required, set `blocked`, `blocked_from: executing`, and an exact `resume_when` condition.

When all work items are `done`, all listed Evidence references resolve, and work is committed, set `status: reviewing` and dispatch `workloop-review` to a context that did not implement the change. Do not write your own review.
