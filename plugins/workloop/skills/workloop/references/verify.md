# Verify semantic consistency

Verification is an evidence-backed comparison between declared obligations and the actual result. A passing command without an acceptance mapping is insufficient.

## Evidence item

Record a stable ID, `kind`, `result`, `validity`, covered IDs, method, and a compact source reference. Use `passed` or `failed`; use `active` or `stale`. Prefer exact commands, test report paths, screenshots, URLs, commits, or reproducible observations over prose claims.

## Checks by transition

Before `ready`:

- goal and scope are non-empty;
- every acceptance item is checkable;
- material cognition is recorded;
- each acceptance item is assigned to a work item.

Before `executing`:

- at least one work item exists;
- dependencies and references resolve;
- cognition blocking execution is resolved with Evidence;
- shared boundaries have contract items and participant ownership.

Before `verifying`:

- implementation work items are done or the remaining work is explicitly verification-only;
- real verification methods exist for each acceptance item.

Before `done`:

- every acceptance item has active passed Evidence;
- every contract item has active passed contract Evidence;
- cognition blocking completion is resolved;
- all work items are done;
- every failed Evidence has a failure card whose prevention has active passed re-verification Evidence.

## Semantic boundary

The checker can prove coverage, references, states, and declared comparisons. It cannot infer arbitrary business semantics from code. The verifying Agent must compare each contract statement and acceptance statement against real provider and consumer behavior, then submit structured Evidence that names the covered IDs.
