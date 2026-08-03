import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "workloop.py"
REPOSITORY = Path(__file__).parents[2]
TEMPLATES = REPOSITORY / "workloop-skills" / "workloop" / "assets" / "templates"
EXAMPLE_LOOP = REPOSITORY / "workloop-skills" / "workloop" / "references" / "example-loop"
SPEC = importlib.util.spec_from_file_location("workloop", SCRIPT)
workloop = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(workloop)


def spec_text(status="executing", assumption_status="confirmed", checked=False):
    mark = "x" if checked else " "
    return f"""---
loop: wl-20260803-01
status: {status}
title: Create a persisted user
created: 2026-08-03
base_commit: abc1234
---

## Intent

POST /users returns a persisted user ID.

**Non-goals:** No UI work.

## Facts and assumptions

Facts:

- The route exists. — Source: src/users.py

| ID | Assumption | Impact | Status | Evidence or source |
|---|---|---|---|---|
| A1 | The users table exists | implementation | {assumption_status} | migrations/001.sql |

## Maximum risk

Serialization differs after readback. — Verification: integration test.

## Acceptance criteria

- [{mark}] `AC1` — POST /users returns the persisted identifier
  - Verification: `pytest tests/test_users.py`
"""


def plan_text(item_status="active", reciprocal=True, evidence=False):
    contracts = "CT1" if reciprocal else "none"
    ev = "EV1, EV2" if evidence else "pending"
    rows = """
| EV1 | pass | 2026-08-03 | `reports/users.txt` | AC1 |
| EV2 | pass | 2026-08-03 | `reports/contract.txt` | CT1 |
""" if evidence else ""
    return f"""# Plan: Create a persisted user

## Risk coverage

- Maximum risk: Serialization differs after readback.
- Covered by: T1

## Contracts

### CT1 — User identifier

- Statement: userId is the persisted identifier
- Providers: backend
- Consumers: frontend
- Work items: T1
- Verification: integration test
- Evidence: {ev}

## Work items

### T1 — Implement user creation

- Status: {item_status}
- Covers: AC1
- Assumptions: A1
- Depends on: none
- Scope: `src/users.py`, `tests/test_users.py`
- Contracts: {contracts}
- Memory: none
- Output: Persisted user endpoint
- Verification: `pytest tests/test_users.py`
- Evidence: {ev}

## Evidence index

| ID | Result | Observed at | Source | Covers |
|---|---|---|---|---|
{rows}

## Execution log

- None.
"""


def review_text(result="pass", anchor="review-session-7"):
    rows = "\n".join(
        f"| {number} | check {number} | {result} | independently verified |"
        for number in range(1, 7)
    )
    return f"""# Review: Create a persisted user

- Reviewer anchor: {anchor}
- Reviewed: artifacts and diff
- Date: 2026-08-03

## Cognitive consistency

| # | Check | Result | Basis |
|---|---|---|---|
{rows}

## Independent sample

- AC1 — pytest — passed; reports/review.txt

## Conclusion

**{result}**

Memory update: none
"""


class WorkloopTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".git").mkdir()
        self.loop = self.root / ".workloop" / "loops" / "wl-20260803-01"
        self.loop.mkdir(parents=True)
        (self.loop / "spec.md").write_text(spec_text(), encoding="utf-8")
        (self.loop / "plan.md").write_text(plan_text(), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def errors(self, target):
        return workloop.validate(self.loop, target)[0]

    def test_canonical_templates_match_the_parser_contract(self):
        parsed_spec = workloop.parse_spec((TEMPLATES / "spec.md").read_text(encoding="utf-8"))
        parsed_plan = workloop.parse_plan((TEMPLATES / "plan.md").read_text(encoding="utf-8"))
        self.assertEqual(list(parsed_spec["acceptance"]), ["AC1", "AC2"])
        self.assertEqual(list(parsed_plan["contracts"]), ["CT1"])
        self.assertEqual(list(parsed_plan["items"]), ["T1", "T2"])

    def test_complete_example_passes_the_done_gate(self):
        for name in ("spec.md", "plan.md", "review.md"):
            (self.loop / name).write_text((EXAMPLE_LOOP / name).read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.errors("done"), [])

    def test_valid_executing_loop(self):
        self.assertEqual(self.errors("executing"), [])

    def test_scope_assumption_blocks_specified(self):
        text = spec_text(status="clarifying").replace("implementation | confirmed", "scope | open")
        (self.loop / "spec.md").write_text(text, encoding="utf-8")
        self.assertIn("A1 blocks specified: scope assumption is open", self.errors("specified"))

    def test_active_implementation_assumption_is_blocked(self):
        (self.loop / "spec.md").write_text(spec_text(assumption_status="open"), encoding="utf-8")
        self.assertIn("A1 blocks active work item T1", self.errors("executing"))

    def test_acceptance_must_map_to_work_item(self):
        (self.loop / "plan.md").write_text(plan_text().replace("- Covers: AC1", "- Covers: none"), encoding="utf-8")
        self.assertIn("AC1 is not covered by any work item", self.errors("executing"))

    def test_contract_requires_reciprocal_reference(self):
        (self.loop / "plan.md").write_text(plan_text(reciprocal=False), encoding="utf-8")
        self.assertIn("CT1 is not referenced back by T1", self.errors("executing"))

    def test_reviewing_requires_passed_ac_and_contract_evidence(self):
        (self.loop / "plan.md").write_text(plan_text(item_status="done"), encoding="utf-8")
        errors = self.errors("reviewing")
        self.assertIn("AC1 lacks passed Evidence", errors)
        self.assertIn("CT1 lacks passed Evidence", errors)

    def test_projection_contains_only_referenced_context(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = workloop.main(["project", "--loop-dir", str(self.loop), "--work-item", "T1"])
        self.assertEqual(code, 0)
        value = json.loads(output.getvalue())
        self.assertEqual(list(value["acceptance"]), ["AC1"])
        self.assertEqual(list(value["assumptions"]), ["A1"])
        self.assertEqual(list(value["contracts"]), ["CT1"])

    def test_done_requires_independent_review_and_checked_ac(self):
        (self.loop / "spec.md").write_text(spec_text(status="reviewing", checked=True), encoding="utf-8")
        (self.loop / "plan.md").write_text(plan_text(item_status="done", evidence=True), encoding="utf-8")
        (self.loop / "review.md").write_text(review_text(), encoding="utf-8")
        self.assertEqual(self.errors("done"), [])
        (self.loop / "review.md").write_text(review_text(anchor="<reviewer>"), encoding="utf-8")
        self.assertIn("reviewer anchor is missing or still a placeholder", self.errors("done"))

    def test_transition_rejects_state_skip(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = workloop.main(["transition", "--loop-dir", str(self.loop), "--to", "done"])
        self.assertEqual(code, 2)
        self.assertIn("illegal transition", error.getvalue())

    def test_hook_denies_out_of_scope_patch(self):
        event = {
            "cwd": str(self.root),
            "tool_input": {"command": "*** Begin Patch\n*** Update File: src/admin.py\n*** End Patch"},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            old_stdin = workloop.sys.stdin
            workloop.sys.stdin = io.StringIO(json.dumps(event))
            try:
                code = workloop.main(["hook", "pre-tool"])
            finally:
                workloop.sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("outside the active work item's Scope", output.getvalue())

    def test_hook_accepts_absolute_in_scope_patch(self):
        target = self.root / "src" / "users.py"
        event = {
            "cwd": str(self.root),
            "tool_input": {"command": f"*** Begin Patch\n*** Update File: {target}\n*** End Patch"},
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            old_stdin = workloop.sys.stdin
            workloop.sys.stdin = io.StringIO(json.dumps(event))
            try:
                code = workloop.main(["hook", "pre-tool"])
            finally:
                workloop.sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
