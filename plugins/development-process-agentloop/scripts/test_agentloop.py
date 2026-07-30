#!/usr/bin/env python3

import json
import subprocess
import tempfile
from pathlib import Path

import yaml


ENGINE = Path(__file__).with_name("agentloop.py")
SYNC_REFERENCES = Path(__file__).with_name("sync_references.py")
PROTOTYPE_FIDELITY_TEST = Path(__file__).with_name("test_prototype_fidelity.py")
INTEGRATION_DATA_TEST = Path(__file__).with_name("test_integration_data_source.py")
HOOKS = ENGINE.parents[1] / "hooks" / "hooks.json"


def run(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["python3", str(ENGINE), "--root", str(root), *args],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def main() -> None:
    subprocess.run(["python3", str(SYNC_REFERENCES), "verify"], check=True)
    source_root = Path(__file__).resolve().parents[3]
    if (source_root / ".git").exists():
        subprocess.run(["python3", str(SYNC_REFERENCES), "check"], check=True)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old_root = root / "cache" / "old"
        current_root = root / "cache" / "current"
        (current_root / "scripts").mkdir(parents=True)
        (current_root / "scripts" / "agentloop.py").write_text(
            "from pathlib import Path\nimport sys\n"
            "Path('hook-result').write_text(' '.join(sys.argv[1:]))\n"
        )
        hook = json.loads(HOOKS.read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
        subprocess.run(
            hook.replace("${PLUGIN_ROOT}", str(old_root)),
            cwd=root,
            shell=True,
            check=True,
        )
        assert (root / "hook-result").read_text() == "hook stop"

        git(root, "init", "-q")
        git(root, "config", "user.name", "AgentLoop Test")
        git(root, "config", "user.email", "agentloop@example.invalid")
        (root / "README.md").write_text("# Test\n")
        git(root, "add", "README.md")
        git(root, "commit", "-qm", "baseline")

        loop_id = run(root, "init", "--title", "修正文案", "--level", "trivial")
        run(root, "validate")
        loop_path = root / ".agentloop" / "loops" / loop_id / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        assert loop["state"] == "draft"
        assert (root / ".agentloop" / "schemas" / "loop.schema.json").exists()

        run(
            root,
            "transition",
            loop_id,
            "clarifying",
            "--actor",
            "requirement-agent",
            "--reason",
            "已记录原始需求",
        )
        loop = yaml.safe_load(loop_path.read_text())
        loop["execution_profile"]["status"] = "confirmed"
        loop["execution_profile"]["reason"] = "单一文案变更且可直接观察"
        loop_path.write_text(yaml.safe_dump(loop, allow_unicode=True, sort_keys=False))
        run(
            root,
            "transition",
            loop_id,
            "awaiting_requirement_confirmation",
            "--actor",
            "requirement-agent",
            "--reason",
            "事实、范围和验收已核对",
        )
        run(
            root,
            "gate",
            loop_id,
            "requirement_confirmation",
            "--decision",
            "approved",
            "--actor",
            "test-user",
            "--source",
            "test-host",
            "--source-event-id",
            "turn-001",
        )
        run(
            root,
            "transition",
            loop_id,
            "ready_for_development",
            "--actor",
            "loop-coordinator",
            "--reason",
            "需求确认通过",
        )
        run(
            root,
            "route",
            loop_id,
            "--actor",
            "development-agent",
            "--confidence",
            "high",
            "--main-flow",
            "quick-change",
            "--reason",
            "位置和影响明确",
            "--verification",
            "self_check",
            "--verification-reason",
            "结果可直接观察",
        )
        run(
            root,
            "transition",
            loop_id,
            "development_preparing",
            "--actor",
            "development-agent",
            "--reason",
            "Git和路由已检查",
        )
        run(
            root,
            "transition",
            loop_id,
            "developing",
            "--actor",
            "development-agent",
            "--reason",
            "编码前检查通过",
        )
        run(
            root,
            "transition",
            loop_id,
            "verified",
            "--actor",
            "loop-coordinator",
            "--reason",
            "直接检查满足验收",
            "--evidence",
            "work.md#开发自检",
        )
        run(
            root,
            "gate",
            loop_id,
            "completion",
            "--decision",
            "approved",
            "--actor",
            "test-user",
            "--source",
            "test-host",
            "--source-event-id",
            "turn-002",
        )
        run(
            root,
            "transition",
            loop_id,
            "done",
            "--actor",
            "loop-coordinator",
            "--reason",
            "完成Gate通过",
        )
        run(root, "validate")
        assert run(root, "status") == "no active Loops"
        assert yaml.safe_load(loop_path.read_text())["scope"]["claim"] == "released"

        composite = run(
            root,
            "init",
            "--title",
            "复合交付",
            "--level",
            "composite",
            "--subflow",
            "创建退款",
            "--subflow",
            "回退支付",
        )
        assert composite.startswith("al-")
        epic_ids = run(
            root,
            "init",
            "--title",
            "大型建设",
            "--kind",
            "epic",
            "--child",
            "账户服务",
            "--child",
            "订单服务",
        ).splitlines()
        assert len(epic_ids) == 3
        run(root, "validate")
        run(root, "doctor")

    subprocess.run(["python3", str(PROTOTYPE_FIDELITY_TEST)], check=True)
    subprocess.run(["python3", str(INTEGRATION_DATA_TEST)], check=True)
    print("passed: AgentLoop full plugin lifecycle")


if __name__ == "__main__":
    main()
