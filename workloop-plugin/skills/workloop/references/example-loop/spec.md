---
loop: wl-20260803-01
status: done
title: Persist a user and return its identifier
created: 2026-08-03
base_commit: abc1234
---

## Intent

`POST /users` persists a user and returns the identifier that can retrieve the same record.

**Non-goals:** No user-interface work and no bulk import.

## Facts and assumptions

Facts:

- The route already exists. — Source: `src/users.py`
- The client already calls `POST /users`. — Source: `web/api/users.ts`

| ID | Assumption | Impact | Status | Evidence or source |
|---|---|---|---|---|
| A1 | The users table is available in the test database | implementation | confirmed | `migrations/001_users.sql` |

## Maximum risk

The returned identifier might not match the persisted record after serialization. — Verification: run the integration test that creates and reads the same user.

## Acceptance criteria

- [x] `AC1` — `POST /users` returns the persisted identifier
  - Verification: `pytest tests/test_users.py::test_create_returns_persisted_id`
- [x] `AC2` — The client reads the identifier from the documented response field
  - Verification: `npm test -- users-api.test.ts`
