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
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


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


def fail(root: Path, expected: str, *args: str) -> None:
    result = invoke(root, *args)
    assert result.returncode != 0, result.stdout
    assert expected in result.stderr, result.stderr


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Reasoning Test"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "reasoning@example.invalid"],
            cwd=root,
            check=True,
        )
        (root / "README.md").write_text("# reasoning controls\n")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

        loop_id = succeed(root, "init", "--title", "推理控制负向测试", "--level", "standard")
        loop_path = root / ".agentloop" / "loops" / loop_id / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        assert loop["knowledge_state"] == {"known": [], "unknowns": [], "conflicts": []}
        assert loop["quality_metrics"] == []
        assert loop["failure_memory"] == []

        fail(
            root,
            "known knowledge requires at least one --source",
            "knowledge", loop_id, "--knowledge-id", "KNO-01", "--kind", "known",
            "--actor", "tester", "--statement", "接口存在", "--impact", "implementation",
        )
        succeed(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-01", "--kind", "known",
            "--actor", "tester", "--statement", "接口存在", "--impact", "implementation",
            "--source", "api/openapi.yaml",
        )
        succeed(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-02", "--kind", "unknown",
            "--actor", "tester", "--statement", "部署环境是否支持该接口",
            "--impact", "routing",
        )
        fail(
            root,
            "resolved knowledge requires --resolution and --evidence",
            "knowledge", loop_id, "--knowledge-id", "KNO-02", "--kind", "unknown",
            "--actor", "tester", "--status", "resolved", "--resolution", "支持",
        )
        succeed(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-02", "--kind", "unknown",
            "--actor", "tester", "--status", "resolved", "--resolution", "支持",
            "--evidence", "环境探测日志",
        )
        fail(
            root,
            "conflicting knowledge requires at least two --source-claim values",
            "knowledge", loop_id, "--knowledge-id", "KNO-03", "--kind", "conflict",
            "--actor", "tester", "--statement", "字段是否允许为空", "--impact", "acceptance",
            "--source-claim", '{"source":"schema","claim":"允许"}',
        )
        succeed(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-03", "--kind", "conflict",
            "--actor", "tester", "--statement", "字段是否允许为空", "--impact", "acceptance",
            "--source-claim", '{"source":"schema","claim":"允许"}',
            "--source-claim", '{"source":"runtime","claim":"拒绝"}',
        )
        fail(
            root,
            "knowledge_id already exists with a different kind",
            "knowledge", loop_id, "--knowledge-id", "KNO-03", "--kind", "known",
            "--actor", "tester", "--statement", "冲突", "--impact", "acceptance",
            "--source", "test",
        )
        succeed(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-03", "--kind", "conflict",
            "--actor", "tester", "--status", "resolved", "--resolution", "运行时行为为准",
            "--evidence", "回归测试",
        )

        fail(
            root,
            "new assumption requires --statement and --impact",
            "assumption", loop_id, "--assumption-id", "ASM-01", "--actor", "tester",
            "--status", "unverified",
        )
        fail(
            root,
            "confirmed or rejected assumption requires --evidence",
            "assumption", loop_id, "--assumption-id", "ASM-01", "--actor", "tester",
            "--statement", "接口保持兼容", "--impact", "implementation",
            "--status", "confirmed",
        )
        succeed(
            root,
            "assumption", loop_id, "--assumption-id", "ASM-01", "--actor", "tester",
            "--statement", "接口保持兼容", "--impact", "implementation",
            "--status", "unverified",
        )
        fail(
            root,
            "confirmed or rejected assumption requires --evidence",
            "assumption", loop_id, "--assumption-id", "ASM-01", "--actor", "tester",
            "--status", "rejected",
        )
        loop = yaml.safe_load(loop_path.read_text())
        assert loop["assumptions"][0]["status"] == "unverified"
        assert loop["knowledge_state"]["unknowns"][0]["status"] == "resolved"
        assert loop["knowledge_state"]["conflicts"][0]["status"] == "resolved"

        fail(
            root,
            "--selected must be one of --option",
            "decision", loop_id, "--decision-id", "DEC-01", "--actor", "tester",
            "--question", "采用哪种方案", "--option", "A", "--option", "B",
            "--selected", "C", "--evidence", "实验", "--rationale", "比较结果",
        )
        fail(
            root,
            "decision invalid",
            "decision", loop_id, "--decision-id", "DEC-01", "--actor", "tester",
            "--question", "采用哪种方案", "--option", "A", "--option", "A",
            "--selected", "A", "--evidence", "实验", "--rationale", "比较结果",
        )
        succeed(
            root,
            "decision", loop_id, "--decision-id", "DEC-01", "--actor", "tester",
            "--question", "采用哪种方案", "--option", "A", "--option", "B",
            "--selected", "A", "--evidence", "实验", "--rationale", "比较结果",
        )
        fail(
            root,
            "decision already exists",
            "decision", loop_id, "--decision-id", "DEC-01", "--actor", "tester",
            "--question", "重复决策", "--option", "A", "--option", "B",
            "--selected", "A", "--evidence", "实验", "--rationale", "重复",
        )

        succeed(
            root,
            "quality-metric", loop_id, "--metric-id", "MET-01", "--actor", "tester",
            "--name", "响应时间", "--unit", "ms", "--baseline", "150",
            "--operator", "lte", "--target", "100", "--required",
        )
        fail(
            root,
            "measured quality metric requires at least one --evidence",
            "quality-metric", loop_id, "--metric-id", "MET-01", "--actor", "tester",
            "--actual", "120",
        )
        succeed(
            root,
            "quality-metric", loop_id, "--metric-id", "MET-01", "--actor", "tester",
            "--actual", "120", "--evidence", "benchmark-failed.json",
        )
        evidence_path = loop_path.with_name("evidence.yaml")
        evidence_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "loop_id": loop_id,
            "runs": [
                {
                    "evidence_id": f"{loop_id}-evidence-01",
                    "requirement_version": 1,
                    "result": "failed",
                    "validity": "stale",
                },
                {
                    "evidence_id": f"{loop_id}-evidence-02",
                    "requirement_version": 1,
                    "result": "passed",
                    "validity": "active",
                },
            ],
        }, allow_unicode=True, sort_keys=False))
        engine.write_control_snapshot(root, yaml.safe_load(loop_path.read_text()))
        fail(
            root,
            "requires an assumption/decision link or --unlinked-reason",
            "failure-memory", loop_id, "--failure-id", "FAI-01", "--actor", "tester",
            "--evidence-id", f"{loop_id}-evidence-01", "--mistake", "错误使用旧口径",
            "--actual-reason", "关键假设未验证", "--prevention", "先验证时间口径",
        )
        fail(
            root,
            "unknown assumptions",
            "failure-memory", loop_id, "--failure-id", "FAI-01", "--actor", "tester",
            "--evidence-id", f"{loop_id}-evidence-01", "--mistake", "错误使用旧口径",
            "--actual-reason", "关键假设未验证", "--prevention", "先验证时间口径",
            "--assumption-id", "ASM-99",
        )
        succeed(
            root,
            "failure-memory", loop_id, "--failure-id", "FAI-01", "--actor", "tester",
            "--evidence-id", f"{loop_id}-evidence-01", "--mistake", "错误使用旧口径",
            "--actual-reason", "关键假设未验证", "--prevention", "先验证时间口径",
            "--assumption-id", "ASM-01", "--decision-id", "DEC-01",
            "--metric-id", "MET-01",
        )
        loop = yaml.safe_load(loop_path.read_text())
        completion_errors = engine.learning_control_errors(root, loop, completion=True)
        assert any("failure prevention is not verified" in error for error in completion_errors)
        assert any("required quality metrics are not met" in error for error in completion_errors)
        succeed(
            root,
            "quality-metric", loop_id, "--metric-id", "MET-01", "--actor", "tester",
            "--actual", "80", "--evidence", "benchmark-passed.json",
        )
        fail(
            root,
            "prevention evidence is not active and passed",
            "failure-memory", loop_id, "--failure-id", "FAI-01", "--actor", "tester",
            "--status", "prevention_verified",
            "--verification-evidence", f"{loop_id}-evidence-01",
        )
        succeed(
            root,
            "failure-memory", loop_id, "--failure-id", "FAI-01", "--actor", "tester",
            "--status", "prevention_verified",
            "--verification-evidence", f"{loop_id}-evidence-02",
        )
        loop = yaml.safe_load(loop_path.read_text())
        assert engine.learning_control_errors(root, loop, completion=True) == []

    print("passed: reasoning control negative CLI cases")


if __name__ == "__main__":
    main()
