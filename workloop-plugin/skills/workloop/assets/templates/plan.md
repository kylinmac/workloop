# Plan: <same title as spec>

## Risk coverage

- Maximum risk: <copy the risk from spec>
- Covered by: <work item or verification ID>

## Contracts

Write `None.` when no shared boundary exists. Otherwise repeat this block:

### CT1 — <boundary name>

- Statement: <observable shared meaning>
- Providers: <module or participant>
- Consumers: <different module or participant>
- Work items: T1, T2
- Verification: <command or human step>
- Evidence: pending

## Work items

### T1 — <verifiable behavior slice>

- Status: active
- Covers: AC1
- Assumptions: A1 or none
- Depends on: none
- Scope: `path/or/glob`
- Contracts: CT1 or none
- Memory: M1 or none
- Output: <observable deliverable>
- Verification: `<command>` or <precise human step>
- Evidence: pending

### T2 — <next behavior slice>

- Status: pending
- Covers: AC2
- Assumptions: none
- Depends on: T1
- Scope: `path/or/glob`
- Contracts: none
- Memory: none
- Output: <observable deliverable>
- Verification: `<command>` or <precise human step>
- Evidence: pending

Use `pending`, `active`, `done`, or `blocked` for Status. Keep exactly one `active` item while executing.

## Evidence index

Keep raw output outside this file. Use `pass`, `fail`, or `stale` for Result.

| ID | Result | Observed at | Source | Covers |
|---|---|---|---|---|
| EV1 | pass | YYYY-MM-DD or commit | `path/to/report` | AC1, CT1 |

## Execution log

Record only deviations: newly discovered information, rejected assumptions, or changed work items.

- <date> — <deviation and response>
