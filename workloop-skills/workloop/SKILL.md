---
name: workloop
description: Route software implementation, refactoring, debugging, migration, or resumed work through a lightweight cognition-and-evidence loop. Use when starting or resuming development work, when intent or assumptions need clarification, when work must be split into verifiable items, when shared module or agent boundaries need a contract, or when completion needs independent semantic review.
---

# Workloop

Control cognition quality and evidence truth; leave implementation choices to engineering judgment.

## Apply the constitution

1. Keep one human-readable artifact per stage: `spec.md`, `plan.md`, `review.md`, plus project-level `memory.md`.
2. Accept real command output, report paths, screenshots, source inspection, or human confirmation as evidence; reject self-assertion.
3. Close assumptions that affect scope or acceptance before planning.
4. Require a reviewer who did not perform the implementation to compare spec, plan, diff, and evidence.
5. Split work into another Loop when one clean context cannot finish it; do not add lifecycle states.
6. Turn reusable failures into executable prevention checks, then promote repeated checks into tests, lint, CI, or hooks.
7. Keep at most 20 memory entries.
8. Load only this router, the current phase Skill, current artifacts, and matching memory entries.

## Route by status

For a new requirement, create `.workloop/loops/wl-YYYYMMDD-NN/spec.md` from [spec.md](assets/spec.md), record the current commit as `base_commit`, and use `workloop-spec`.

For an existing Loop, read only the `status` in `spec.md` first:

| Status | Skill | Artifact |
|---|---|---|
| `clarifying` | `workloop-spec` | `spec.md` |
| `specified` | `workloop-plan` | `plan.md` |
| `executing` | `workloop-execute` | `plan.md` evidence index |
| `reviewing` | `workloop-review` in an independent context | `review.md` |
| review passed | `workloop-memory` | `.workloop/memory.md` |
| `blocked` | Resume at `blocked_from` only after `resume_when` is true | none |
| `done` or `cancelled` | Stop | none |

Keep state only in `spec.md` frontmatter. Use `clarifying → specified → executing → reviewing → done`; allow `blocked` and `cancelled` only as described above.

## Use the strict layer when available

Before changing state, run:

```bash
python3 <workloop-plugin>/scripts/workloop.py check \
  --loop-dir .workloop/loops/<loop-id> --target <status>
```

Before assigning a work item, generate its projection:

```bash
python3 <workloop-plugin>/scripts/workloop.py project \
  --loop-dir .workloop/loops/<loop-id> --work-item T1
```

Treat Contract, projection, and machine Gate support as optional strict-layer capabilities. Do not make the method depend on the plugin.
