---
name: workloop-spec
description: Produce or revise a Workloop spec before planning or coding. Use for new requirements, clarifying loops, changed requirements, intent analysis, assumption extraction, risk assessment, and observable acceptance criteria.
---

# Workloop Spec

Copy `../workloop/assets/spec.md` to `.workloop/loops/<id>/spec.md`.

1. Rewrite the request as an observable user outcome and explicit non-goals. Confirm material ambiguity with the user.
2. Record sourced facts separately from unsourced assumptions.
3. Classify assumption impact as `scope`, `acceptance`, `implementation`, or `non-blocking`.
4. Close `scope` and `acceptance` assumptions with the cheapest real evidence. Do not enter `specified` while either remains `open`.
5. Name the single largest uncertainty and its verification method. Convert other material risks into acceptance criteria.
6. Give every acceptance criterion a stable `ACn` ID, an observable outcome, and a concrete command or human verification step.

Set `status: specified` only when the artifact is complete and blocking assumptions are closed. Leave acceptance checkboxes unchecked; the independent reviewer checks them after implementation.

Reject these substitutions:

- an implementation detail in place of an observable acceptance result;
- “should”, “probably”, or convention in place of a source;
- relabeling an assumption `non-blocking` merely to advance state.
