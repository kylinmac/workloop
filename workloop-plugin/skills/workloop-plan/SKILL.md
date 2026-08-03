---
name: workloop-plan
description: Convert a specified Workloop requirement into small verifiable work items. Use when plan.md must be created or revised, acceptance coverage must be mapped, execution scope must be isolated, or a shared API, data, behavior, or acceptance boundary needs an optional Contract.
---

# Workloop Plan

Copy `../workloop/assets/templates/plan.md` to `.workloop/loops/<id>/plan.md`.

1. Derive work items backward from acceptance criteria. Map every item to stable AC IDs.
2. Make each item fit one clean context and leave the system in a verifiable state.
3. Declare dependencies, allowed paths, outputs, and an exact verification command or human step.
4. Cover the spec's maximum risk with an explicit work item or verification.
5. Add a Contract only when two modules, agents, or delivery units share meaning. Give it a stable `CTn` ID, providers, consumers, linked work items, observable statement, and verification.
6. Keep raw logs outside `plan.md`. Add only compact Evidence rows with stable `EVn` IDs, result, time, source path, and covered AC/Contract IDs.

Set exactly one ready item to `active` before implementation. Keep all other unfinished items `pending` or `blocked`. Set `status: executing` only after every AC is covered and all Contract references are reciprocal.

When execution changes scope or acceptance, revise `spec.md` first. Record only plan deviations in the execution log.
