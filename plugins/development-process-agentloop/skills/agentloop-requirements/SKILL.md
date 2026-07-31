---
name: agentloop-requirements
description: Handle only AgentLoop draft, clarification, classification, requirement confirmation, and requirement Gate work.
---

# AgentLoop Requirements

Use only for `draft`, `clarifying`, and
`awaiting_requirement_confirmation`. Work from the `context` projection and the
declared requirement/work file.

Read only:

- `references/requirements/flows/需求确认流程.md`
- `references/requirements/需求分类.md` when classification is incomplete
- `references/agentloop/产物与目录协议.md` only when artifact shape is unclear

Required outcome:

- preserve the raw request, facts, goal, scope, non-goals, constraints, and
  executable acceptance obligations;
- complete the chosen classification obligations and execution-profile
  qualifications before confirmation;
- declare whether prototypes are implementation bases and whether database →
  API → UI lineage applies;
- replace vague acceptance such as “按原型实现” with independently checkable
  criteria.

Move `draft → clarifying`, then
`clarifying → awaiting_requirement_confirmation` through `transition`. At the
manual Gate, stop for an explicit current-conversation decision and record it
with `gate`. Ordinary Gates use the configured local attestation unless a real
host adapter provides HMAC. Never infer approval from silence.

Do not load development, verification, integration, Evidence, or transition
history in this phase.
