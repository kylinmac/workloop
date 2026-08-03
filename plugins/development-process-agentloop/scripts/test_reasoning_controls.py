#!/usr/bin/env python3

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
import yaml


ENGINE = Path(__file__).with_name("agentloop.py")


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

    print("passed: reasoning control negative CLI cases")


if __name__ == "__main__":
    main()
