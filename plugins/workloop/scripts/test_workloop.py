#!/usr/bin/env python3

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("workloop.py")
SPEC = importlib.util.spec_from_file_location("workloop", SCRIPT)
workloop = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(workloop)


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class WorkloopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            code = workloop.main(["init", "--root", str(self.root), "--task-id", "TASK-001", "--title", "Create users"])
        self.assertEqual(code, 0)
        self.task = self.root / ".workloop" / "tasks" / "TASK-001"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_valid_ready(self) -> None:
        brief = json.loads((self.task / "brief.json").read_text())
        brief["acceptance"] = [{"id": "AC-001", "statement": "POST /users returns a persisted user ID"}]
        brief["cognition"] = [{
            "id": "COG-001", "type": "assumption", "statement": "The users table exists",
            "status": "confirmed", "blocks": ["executing"], "evidence_ids": ["EVD-001"]
        }]
        write(self.task / "brief.json", brief)
        write(self.task / "plan.json", {
            "task_id": "TASK-001",
            "work_items": [{
                "id": "WI-001", "title": "Implement user creation", "status": "pending",
                "depends_on": [], "scope": {"paths": ["backend/users"]},
                "cognition_ids": ["COG-001"], "acceptance_ids": ["AC-001"], "contract_ids": [],
                "outputs": ["User creation endpoint"], "verification": ["Run API integration test"]
            }],
            "contracts": []
        })
        write(self.task / "evidence.json", {
            "task_id": "TASK-001",
            "items": [{
                "id": "EVD-001", "kind": "cognition", "result": "passed", "validity": "active",
                "method": "Inspect migration", "source": "db/migrations/001_users.sql",
                "acceptance_ids": [], "cognition_ids": ["COG-001"], "contract_ids": []
            }]
        })

    def test_init_creates_exact_core_artifacts(self) -> None:
        self.assertEqual({path.name for path in self.task.iterdir()}, set(workloop.FILES))

    def test_ready_requires_acceptance_and_work_item(self) -> None:
        errors = workloop.validate_task(workloop.load_task(self.task), "ready")
        self.assertIn("ready requires at least one acceptance item", errors)
        self.assertIn("ready requires at least one work item", errors)

    def test_execution_rejects_unverified_blocking_assumption(self) -> None:
        self.make_valid_ready()
        brief = json.loads((self.task / "brief.json").read_text())
        brief["cognition"][0]["status"] = "unverified"
        brief["cognition"][0]["evidence_ids"] = []
        write(self.task / "brief.json", brief)
        errors = workloop.validate_task(workloop.load_task(self.task), "executing")
        self.assertIn("cognition COG-001 blocks target state executing", errors)

    def test_resolved_cognition_rejects_stale_proof(self) -> None:
        self.make_valid_ready()
        evidence = json.loads((self.task / "evidence.json").read_text())
        evidence["items"][0]["validity"] = "stale"
        write(self.task / "evidence.json", evidence)
        errors = workloop.validate_task(workloop.load_task(self.task), "ready")
        self.assertIn("cognition[COG-001] is resolved without active passed Evidence or a source", errors)

    def test_project_contains_only_selected_context(self) -> None:
        self.make_valid_ready()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = workloop.main(["project", "--task-dir", str(self.task), "--work-item", "WI-001"])
        self.assertEqual(code, 0)
        projection = json.loads(output.getvalue())
        self.assertEqual(projection["work_item"]["id"], "WI-001")
        self.assertEqual([item["id"] for item in projection["acceptance"]], ["AC-001"])
        self.assertEqual([item["id"] for item in projection["cognition"]], ["COG-001"])

    def test_done_requires_acceptance_evidence(self) -> None:
        self.make_valid_ready()
        plan = json.loads((self.task / "plan.json").read_text())
        plan["work_items"][0]["status"] = "done"
        write(self.task / "plan.json", plan)
        errors = workloop.validate_task(workloop.load_task(self.task), "done")
        self.assertIn("acceptance AC-001 lacks active passed Evidence", errors)

    def test_contract_requires_reciprocal_work_item_reference(self) -> None:
        self.make_valid_ready()
        plan = json.loads((self.task / "plan.json").read_text())
        plan["contracts"] = [{
            "id": "API-001", "kind": "api", "statement": "userId means the persisted identifier",
            "providers": ["backend"], "consumers": ["frontend"], "work_item_ids": ["WI-001"]
        }]
        write(self.task / "plan.json", plan)
        errors = workloop.validate_task(workloop.load_task(self.task), "ready")
        self.assertIn("contracts[API-001] is not referenced back by work item WI-001", errors)

    def test_done_requires_failure_memory_and_verified_prevention(self) -> None:
        self.make_valid_ready()
        plan = json.loads((self.task / "plan.json").read_text())
        plan["work_items"][0]["status"] = "done"
        write(self.task / "plan.json", plan)
        evidence = json.loads((self.task / "evidence.json").read_text())
        evidence["items"].extend([
            {"id": "EVD-FAIL", "kind": "test", "result": "failed", "validity": "stale",
             "method": "Run test", "source": "reports/first-run.txt", "acceptance_ids": ["AC-001"],
             "cognition_ids": [], "contract_ids": []},
            {"id": "EVD-PASS", "kind": "test", "result": "passed", "validity": "active",
             "method": "Run test", "source": "reports/final-run.txt", "acceptance_ids": ["AC-001"],
             "cognition_ids": [], "contract_ids": []}
        ])
        write(self.task / "evidence.json", evidence)
        errors = workloop.validate_task(workloop.load_task(self.task), "done")
        self.assertIn("failed Evidence EVD-FAIL lacks a failure card", errors)

    def test_transition_rejects_invalid_skip(self) -> None:
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = workloop.main(["transition", "--task-dir", str(self.task), "--to", "executing"])
        self.assertEqual(code, 2)
        self.assertIn("illegal transition", error.getvalue())


if __name__ == "__main__":
    unittest.main()
