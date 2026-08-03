# Plan: Persist a user and return its identifier

## Risk coverage

- Maximum risk: The returned identifier might not match the persisted record after serialization.
- Covered by: T1 integration verification and EV1.

## Contracts

### CT1 — Created user identifier

- Statement: A successful `POST /users` response exposes the persisted identifier as `userId`.
- Providers: backend user endpoint
- Consumers: web API client
- Work items: T1, T2
- Verification: create a user through the endpoint and read `userId` through the client fixture
- Evidence: EV1, EV2

## Work items

### T1 — Persist and return the user identifier

- Status: done
- Covers: AC1
- Assumptions: A1
- Depends on: none
- Scope: `src/users.py`, `tests/test_users.py`
- Contracts: CT1
- Memory: M1
- Output: Endpoint response containing the persisted `userId`
- Verification: `pytest tests/test_users.py::test_create_returns_persisted_id`
- Evidence: EV1

### T2 — Consume the shared identifier field

- Status: done
- Covers: AC2
- Assumptions: none
- Depends on: T1
- Scope: `web/api/users.ts`, `web/api/users-api.test.ts`
- Contracts: CT1
- Memory: none
- Output: Client mapping for the `userId` response field
- Verification: `npm test -- users-api.test.ts`
- Evidence: EV2

## Evidence index

| ID | Result | Observed at | Source | Covers |
|---|---|---|---|---|
| EV1 | pass | 2026-08-03 / def5678 | `reports/users-integration.txt` | AC1, CT1 |
| EV2 | pass | 2026-08-03 / def5678 | `reports/users-client.txt` | AC2, CT1 |

## Execution log

- 2026-08-03 — No deviations from the specified scope.
