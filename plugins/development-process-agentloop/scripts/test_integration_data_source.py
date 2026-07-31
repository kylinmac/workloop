#!/usr/bin/env python3

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
import yaml


ENGINE = Path(__file__).with_name("agentloop.py")
SPEC = importlib.util.spec_from_file_location("agentloop_engine", ENGINE)
AGENTLOOP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(AGENTLOOP)


def call(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(ENGINE), "--root", str(root), *args],
        text=True,
        capture_output=True,
    )


def write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "AgentLoop Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "agentloop@example.invalid"], cwd=root, check=True)
        (root / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

        created = call(root, "init", "--title", "真实数据链路", "--level", "standard")
        assert created.returncode == 0, created.stderr
        loop_id = created.stdout.strip()
        loop_dir = root / ".agentloop" / "loops" / loop_id
        loop_path = loop_dir / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        loop["classification"].update({
            "control_version": 2,
            "primary_type": "内部改进",
            "basis": "验证数据库到 UI 的数据链路",
            "obligations": [
                {
                    "obligation_id": f"IMP-{index}",
                    "kind": kind,
                    "requirement": kind,
                    "source": "requirement.md",
                    "status": "confirmed",
                }
                for index, kind in enumerate((
                    "baseline", "metric", "target", "external-invariants", "allowed-scope"
                ), 1)
            ],
        })
        loop["acceptance_obligations"] = [{
            "acceptance_id": "AC-DATA",
            "criterion": "数据库 sentinel 经 API 展示到订单页",
            "source": "requirement.md",
            "required": True,
            "implementation_paths": ["tests/orders_data_lineage.py"],
            "verification": {
                "flow_id": "orders-data-lineage",
                "check_id": None,
                "executor": "ui",
                "subflow_id": None,
            },
        }]
        loop["state"] = "verified"
        loop["execution_profile"]["status"] = "confirmed"
        loop["routing"]["status"] = "decided"
        loop["routing"]["verification"]["policy"] = "flow"
        loop["routing"]["verification"]["new_flows"] = ["orders-data-lineage"]
        loop["integration_data"] = {
            "required": True,
            "reason": "订单页通过后端查询数据库",
            "frontend_routes": ["/orders"],
            "backend_endpoints": ["GET /api/orders"],
            "database_objects": ["orders"],
            "verification_flow_id": "orders-data-lineage",
        }
        write_yaml(loop_path, loop)
        write_yaml(loop_dir / "development-assurance.yaml", {
            "schema_version": 1,
            "loop_id": loop_id,
            "requirement_version": 1,
            "route": "quick-change",
            "obligations": [{
                "obligation_id": "impact-scope",
                "scope_id": None,
                "source_obligation_ids": [
                    item["obligation_id"] for item in loop["classification"]["obligations"]
                ],
                "artifact_paths": ["README.md"],
                "checks": ["data lineage regression"],
                "gate_ids": [],
                "recovery": "return to development_preparing",
            }],
        })
        AGENTLOOP.write_control_snapshot(root, loop)

        automation = root / "tests" / "orders_data_lineage.py"
        automation.parent.mkdir(parents=True)
        automation.write_text("print('seed database, query API, assert UI sentinel')\n")
        flow_path = root / ".agentloop" / "flows" / "orders-data-lineage.yaml"
        write_yaml(flow_path, {
            "schema_version": 1,
            "flow_id": "orders-data-lineage",
            "title": "订单数据库到页面",
            "executor": "ui",
            "status": "active",
            "covers": {
                "paths": [],
                "interfaces": ["GET /api/orders"],
                "routes": ["/orders"],
                "db_objects": ["orders"],
                "states": [],
                "tags": [],
            },
            "preconditions": ["隔离测试数据库可用"],
            "steps": [{"action": "生成订单并打开订单页", "expect": "页面展示同一 sentinel"}],
            "checks": ["data_lineage"],
            "automation": {"path": "tests/orders_data_lineage.py"},
        })

        evidence_path = loop_dir / "evidence.yaml"
        run = {
            "evidence_id": f"{loop_id}-evidence-01",
            "flow_id": "orders-data-lineage",
            "check_id": None,
            "subflow_id": None,
            "acceptance_ids": ["AC-DATA"],
            "requirement_version": 1,
            "executor": "ui",
            "command": ["python3", "tests/orders_data_lineage.py"],
            "result": "passed",
            "exit_code": 0,
            "counts": {"passed": 1, "failed": 0, "skipped": 0},
            "validity": "active",
            "code_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip(),
            "environment": "isolated-test-db",
            "started_at": "2026-07-31T01:00:00+08:00",
            "ended_at": "2026-07-31T01:00:01+08:00",
            "duration_ms": 1000,
            "stdout_path": None,
            "stderr_path": None,
            "coverage": [],
            "artifacts": [],
        }
        write_yaml(evidence_path, {"schema_version": 1, "loop_id": loop_id, "runs": [run]})
        AGENTLOOP.write_control_snapshot(root, loop)
        assert call(root, "validate").returncode != 0

        loop["state"] = "verifying"
        write_yaml(loop_path, loop)
        AGENTLOOP.write_control_snapshot(root, loop)
        rejected = call(root, "transition", loop_id, "verified", "--actor", "test", "--reason", "缺少链路证据")
        assert rejected.returncode != 0

        artifacts = root / "artifacts"
        artifacts.mkdir()
        for name in ("db-row.json", "api-response.json", "orders-page.png"):
            (artifacts / name).write_text("agentloop-7f3a\n")
        run["data_lineage"] = {
            "sentinel": "agentloop-7f3a",
            "database": {
                "generated_by": "factory",
                "objects": ["orders"],
                "observed_sentinel": "agentloop-7f3a",
                "evidence_paths": ["artifacts/db-row.json"],
            },
            "backend": {
                "endpoints": ["GET /api/orders"],
                "observed_sentinel": "wrong",
                "evidence_paths": ["artifacts/api-response.json"],
            },
            "frontend": {
                "routes": ["/orders"],
                "observed_sentinel": "agentloop-7f3a",
                "evidence_paths": ["artifacts/orders-page.png"],
            },
        }
        write_yaml(evidence_path, {"schema_version": 1, "loop_id": loop_id, "runs": [run]})
        AGENTLOOP.write_control_snapshot(root, loop)
        assert call(root, "transition", loop_id, "verified", "--actor", "test", "--reason", "sentinel 不一致").returncode != 0

        run["data_lineage"]["backend"]["observed_sentinel"] = "agentloop-7f3a"
        write_yaml(evidence_path, {"schema_version": 1, "loop_id": loop_id, "runs": [run]})
        AGENTLOOP.write_control_snapshot(root, loop)
        passed = call(root, "transition", loop_id, "verified", "--actor", "test", "--reason", "真实数据链路完整")
        assert passed.returncode == 0, passed.stderr
        assert call(root, "validate").returncode == 0

    print("passed: integration data source gate")


if __name__ == "__main__":
    main()
