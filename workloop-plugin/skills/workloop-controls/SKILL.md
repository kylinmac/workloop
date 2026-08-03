---
name: workloop-controls
description: Enforce the deterministic part of the Workloop protocol. Use when checking a Loop state transition, validating AC or Contract coverage, generating an isolated work-item projection, diagnosing a Workloop gate failure, or preventing edits outside the active work item's declared scope.
---

# Workloop Controls

Use the control script for structure and references; use independent review for business semantics.

Resolve `<plugin-root>` as the directory containing `.codex-plugin/plugin.json`.

Check the current or intended state:

```bash
python3 <plugin-root>/scripts/workloop.py check \
  --loop-dir .workloop/loops/<loop-id> [--target <status>]
```

Change state only through the checked transition command:

```bash
python3 <plugin-root>/scripts/workloop.py transition \
  --loop-dir .workloop/loops/<loop-id> --to <status>
```

Generate a work package before implementation or delegation:

```bash
python3 <plugin-root>/scripts/workloop.py project \
  --loop-dir .workloop/loops/<loop-id> --work-item T1
```

The projection contains only the selected item, its dependencies, referenced ACs, assumptions, Contracts, Evidence, and explicitly selected memory entries.

Treat a passing Gate as structural evidence only. It cannot prove that requirements, code behavior, reviewer independence, or external evidence are truthful; `workloop-review` must still perform semantic comparison and re-run critical checks.
