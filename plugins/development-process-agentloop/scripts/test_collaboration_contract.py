#!/usr/bin/env python3

import copy
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
import yaml


ENGINE = Path(__file__).with_name("agentloop.py")
SPEC = importlib.util.spec_from_file_location("agentloop_engine", ENGINE)
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
PLUGIN_ROOT = ENGINE.parents[1]


def invoke(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(ENGINE), "--root", str(root), *args],
        text=True,
        capture_output=True,
    )


def succeed(root: Path, *args: str) -> str:
    result = invoke(root, *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Contract Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "contract@example.invalid"], cwd=root, check=True)
        (root / "README.md").write_text("# contract test\n")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

        loop_id = succeed(root, "init", "--title", "前后端用户协作", "--level", "standard")
        loop_path = root / ".agentloop" / "loops" / loop_id / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        assert "collaboration contract requirement" in "; ".join(
            engine.transition_errors(root, loop, "awaiting_requirement_confirmation", [])
        )
        succeed(
            root, "transition", loop_id, "clarifying", "--actor", "requirement-agent",
            "--reason", "开始澄清共享边界",
        )
        succeed(
            root, "contract-declare", loop_id, "--actor", "requirement-agent",
            "--required", "--reason", "前后端必须共享接口和字段语义",
            "--consumer", "backend-agent", "--consumer", "frontend-agent",
        )
        loop = yaml.safe_load(loop_path.read_text())
        loop["acceptance_obligations"] = [{
            "acceptance_id": "AC-01",
            "criterion": "用户创建成功并返回 ACTIVE",
            "source": "requirement.md",
            "required": True,
            "implementation_paths": ["backend.py", "frontend.py"],
            "verification": None,
        }]
        loop_path.write_text(yaml.safe_dump(loop, allow_unicode=True, sort_keys=False))
        contract = yaml.safe_load(
            (PLUGIN_ROOT / "references" / "agentloop" / "examples" / "development-contract.yaml").read_text()
        )
        contract["loop_id"] = loop_id
        contract["status"] = "draft"
        contract_path = loop_path.with_name("development-contract.yaml")
        contract_path.write_text(yaml.safe_dump(contract, allow_unicode=True, sort_keys=False))
        missing_confirmation = invoke(
            root, "contract-confirm", loop_id, "--actor", "loop-coordinator",
            "--confirmed-by", "backend-agent",
        )
        assert missing_confirmation.returncode != 0
        assert "exactly cover every contract consumer" in missing_confirmation.stderr
        succeed(
            root, "contract-confirm", loop_id, "--actor", "loop-coordinator",
            "--confirmed-by", "backend-agent", "--confirmed-by", "frontend-agent",
        )
        loop = yaml.safe_load(loop_path.read_text())
        assert yaml.safe_load(contract_path.read_text())["status"] == "confirmed"
        assert engine.collaboration_contract_errors(root, loop) == []

        for name in ("backend.py", "frontend.py", "contract_test.py"):
            (root / name).write_text(f"# {name}\n")
        subprocess.run(["git", "add", "backend.py", "frontend.py", "contract_test.py"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "implement contract"], cwd=root, check=True)
        code_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
        ).stdout.strip()
        evidence = yaml.safe_load(
            (PLUGIN_ROOT / "references" / "agentloop" / "examples" / "evidence.yaml").read_text()
        )
        evidence["loop_id"] = loop_id
        run = evidence["runs"][0]
        run["evidence_id"] = f"{loop_id}-evidence-01"
        run["requirement_version"] = 1
        run["code_commit"] = code_commit
        run["contract_consistency"] = {
            "contract_digest": loop["collaboration_contract"]["digest"],
            "participants": ["backend-agent", "frontend-agent"],
            "checks": [
                {
                    "contract_id": contract_id,
                    "kind": kind,
                    "providers": ["backend.py" if kind != "acceptance" else "contract_test.py"],
                    "consumers": ["frontend.py"],
                    "result": "passed",
                }
                for contract_id, kind in (
                    ("API-01", "api"),
                    ("DATA-01", "data"),
                    ("BEH-01", "behavior"),
                    ("ACC-01", "acceptance"),
                )
            ],
            "violations": [],
        }
        schema_errors = list(engine.schema_validator("evidence.schema.json").iter_errors(evidence))
        assert not schema_errors, schema_errors[0].message if schema_errors else ""
        evidence_path = loop_path.with_name("evidence.yaml")
        evidence_path.write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False))
        engine.write_control_snapshot(root, loop)
        assert engine.collaboration_contract_verification_errors(root, loop) == []

        incomplete = copy.deepcopy(evidence)
        incomplete["runs"][0]["contract_consistency"]["checks"].pop()
        evidence_path.write_text(yaml.safe_dump(incomplete, allow_unicode=True, sort_keys=False))
        errors = engine.collaboration_contract_verification_errors(root, loop)
        assert any("coverage is incomplete" in error for error in errors)

        evidence_path.write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False))
        contract_path.write_text(contract_path.read_text() + "\n")
        errors = engine.collaboration_contract_errors(root, loop)
        assert "collaboration contract changed after confirmation" in errors

    print("passed: collaborative contract declaration, freeze, and consistency evidence")


if __name__ == "__main__":
    main()
