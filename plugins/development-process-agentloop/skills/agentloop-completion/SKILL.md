---
name: agentloop-completion
description: Handle only AgentLoop verified-state validation, user completion acceptance, and transition to done.
---

# AgentLoop Completion

Use only for `verified`. Work from the completion projection, which contains
the completion Gate, required acceptance obligations, current Evidence
summaries, Git delivery identity, and compact child status.

Run `validate`. Confirm every required acceptance ID has active passed Evidence
on the exact delivery or integration commit, all required subflows/children are
aggregated, and required integration verification passed. Confirm the delivery
commit exists and user changes remain preserved.

Request the completion Gate from the user. Record the explicit decision with
`gate`; never infer it. If approved, transition `verified → done`. If rejected,
preserve the reason, stale only affected Evidence, and return to the narrowest
appropriate phase.

Do not load implementation details, full Evidence reports, transition history,
or protocol documents unless validation reports a specific inconsistency.
