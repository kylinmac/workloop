# Plan independent work items

Translate acceptance into the smallest useful work graph. Each work item must be independently projectable and have a clear completion result.

## Work item fields

Define:

- `id`, `title`, and `status`;
- `depends_on` work-item IDs;
- `scope.paths` and optional `scope.excludes`;
- `cognition_ids` needed for this work only;
- `acceptance_ids` advanced by the work;
- `contract_ids` implemented or consumed by the work;
- concrete `outputs` and `verification` methods.

Avoid work items named only “frontend”, “backend”, or “testing” when they conceal multiple independently verifiable outcomes. Also avoid tiny packages that produce no independently useful result.

Only a work item whose dependencies are `done` and whose execution-blocking cognition is resolved is ready.

## Shared-boundary contract

Add `contracts` only when two or more participants or modules share an API, data, behavior, or acceptance boundary. Each contract item needs:

- stable ID and `kind`;
- provider and consumer participants;
- a precise semantic statement, including field meaning when relevant;
- implementation work-item IDs.

The contract is part of `plan.json`, not a fifth default artifact. Any contract change invalidates earlier contract Evidence by digest or explicit staleness in the strict plugin phase. In the Skill phase, rerun the affected checks and replace or stale the Evidence manually.

## Dynamic replanning

Revise only the affected work items when Evidence rejects an assumption or a failure reveals a wrong decision. Preserve IDs for unchanged obligations so prior valid Evidence remains traceable.
