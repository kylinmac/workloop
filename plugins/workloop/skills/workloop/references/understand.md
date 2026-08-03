# Understand the task

Produce a small `brief.json`; do not reproduce the whole conversation.

## Intent

Record one outcome-oriented goal, explicit in-scope and out-of-scope boundaries, and constraints that can change implementation choices. Convert each promised user-visible or system-visible result into an acceptance item with a stable ID and a checkable statement.

Reject vague acceptance such as “works correctly”, “same as the design”, or “tests pass”. State the observable behavior, condition, and expected result.

## Cognition

Create a cognition item only when it can affect routing, execution, verification, or completion.

- `fact`: verified input with a source in `evidence_ids` or `source`.
- `assumption`: a proposition currently used without proof.
- `unknown`: missing information without a selected proposition.
- `conflict`: two or more incompatible sourced claims.
- `decision`: a choice among explicit options, with rationale and `based_on` cognition IDs.

Use `blocks` to name the earliest target state that cannot safely be entered while the item remains unresolved. Do not block early stages for a verification-only unknown.

Statuses are `unverified`, `confirmed`, `rejected`, `conflicted`, and `resolved`. A non-fact item may become confirmed, rejected, or resolved only when its `evidence_ids` are non-empty.

## Risk obligations

Record a risk only when it adds a concrete obligation. Examples:

- shared API or data meaning → create contract items in the plan;
- migration or destructive data change → add rollback and integrity acceptance;
- permission, money, or production impact → require stronger real-environment Evidence;
- performance claim → add a measurable acceptance threshold.

Do not choose a new workflow tier.
