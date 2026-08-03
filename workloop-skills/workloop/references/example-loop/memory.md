# Workloop memory

Keep at most 20 entries. Add only reusable lessons from real failures or independent review findings.

| ID | Trigger | Lesson | Prevention check | Source Loop | Last triggered |
|---|---|---|---|---|---|
| M1 | An API returns an identifier for a newly persisted record | Serialization can return a value that does not retrieve the persisted row | Run a create-and-read integration test against the persisted identifier | wl-20260803-01 | wl-20260803-01 (2026-08-03) |

Count: 1 / 20
