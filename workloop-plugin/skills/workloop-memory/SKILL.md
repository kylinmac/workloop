---
name: workloop-memory
description: Update Workloop project memory after an independent review or real failure. Use when deciding whether a lesson is reusable, when maintaining the 20-entry memory limit, or when promoting repeated lessons into automated tests, lint, CI, or hooks.
---

# Workloop Memory

Create `.workloop/memory.md` from `../workloop/assets/templates/memory.md` only when the project first needs Workloop state. Update it after review pass; write no new row when there is no qualifying lesson.

Admit a lesson only when all are true:

1. It came from a real failure or independently observed defect.
2. A future task can trigger it again.
3. Its trigger condition is specific enough to match before action.
4. Its prevention is an executable check or precise review assertion.

Keep at most 20 entries. Before adding one, merge the same root cause, remove the least recently triggered entry, or promote a repeated prevention check into test, lint, CI, or Hook and remove it from memory.

Reject slogans such as “verify carefully”, one-off incidents with no reusable trigger, and lessons that merely ask an Agent to declare more state.
