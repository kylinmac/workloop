---
name: workloop
description: Structure software changes as a lightweight cognition-first loop with fixed task brief, work plan, evidence, and failure-memory artifacts. Use for implementing, refactoring, debugging, or resuming development work when Codex should clarify intent and assumptions, split work into independently executable items, validate semantic consistency, prove acceptance with evidence, or learn from failed attempts. Also use when multiple agents or modules need isolated work packages and a shared boundary contract.
---

# Workloop

Use one small protocol for every task. Add obligations when risk requires them; do not select a larger parallel process.

## Locate or start the task

Resolve `<plugin-root>` as the directory containing `.codex-plugin/plugin.json`.

Look for `.workloop/tasks/*/brief.json`. Resume the matching active task when one exists. Otherwise initialize one:

```bash
python3 <plugin-root>/scripts/workloop.py init \
  --root . --task-id TASK-001 --title "<goal>"
```

The task directory always contains:

- `brief.json`: intent, scope, acceptance, cognition, risks, state;
- `plan.json`: work items and optional shared-boundary contracts;
- `evidence.json`: compact evidence index;
- `failures.json`: failure cards; keep `items` empty until a real failure.

Do not create additional lifecycle documents unless the repository itself needs a user-facing specification.

## Run the loop

1. **Understand.** Read [understand.md](references/understand.md). Update the brief with the goal, boundaries, independently checkable acceptance, and only material cognition items.
2. **Plan.** Read [plan.md](references/plan.md). Convert risks into obligations and acceptance into independently executable work items. Add a shared-boundary contract only when at least two participants or modules must agree.
3. **Execute.** Select one ready work item. Generate its isolated context before implementation:

   ```bash
   python3 <plugin-root>/scripts/workloop.py project \
     --task-dir .workloop/tasks/TASK-001 --work-item WI-001
   ```

   Treat the projection as the work package for the current Agent or Subagent. Preserve user changes and stay inside its declared scope.
4. **Verify.** Read [verify.md](references/verify.md). Record real results in `evidence.json`, then check the intended transition:

   ```bash
   python3 <plugin-root>/scripts/workloop.py check \
     --task-dir .workloop/tasks/TASK-001 --target verifying
   ```
5. **Learn after failure.** Read [failure-learning.md](references/failure-learning.md) only after failed Evidence. Add a failure card, revise the affected cognition or plan, and verify the prevention before completion.

## State transitions

Use:

```text
draft → ready → executing → verifying → done
```

Use `blocked` when progress needs external information or authority. Use `revise` when the current understanding or plan is wrong. Return from either state to the narrowest valid normal state.

Change state through the checked transition command:

```bash
python3 <plugin-root>/scripts/workloop.py transition \
  --task-dir .workloop/tasks/TASK-001 --to ready
```

The first version validates transitions but does not protect files from direct edits; tamper resistance belongs to the later strict plugin layer.

## Keep context small

- Load only the current reference file and current work-item projection.
- Pass IDs and conclusions by default, not full logs or historical conversations.
- Keep evidence bodies outside the four artifacts and reference them by path or URL.
- Do not load completed work-item details unless a current dependency or failure requires them.
- Do not create a failure card, contract, quality target, or cognition item merely because the schema permits it.

## Completion rule

Run `check --target done`. Do not declare completion unless every acceptance item, contract item, blocking cognition item, work item, and failed attempt satisfies the reported conditions.
