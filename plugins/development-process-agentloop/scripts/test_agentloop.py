#!/usr/bin/env python3

import hashlib
import hmac
import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml


ENGINE = Path(__file__).with_name("agentloop.py")
SYNC_REFERENCES = Path(__file__).with_name("sync_references.py")
PROTOTYPE_FIDELITY_TEST = Path(__file__).with_name("test_prototype_fidelity.py")
INTEGRATION_DATA_TEST = Path(__file__).with_name("test_integration_data_source.py")
PRODUCTION_PROTOTYPE_TEST = Path(__file__).with_name("test_production_prototype_gate.py")
HOOKS = ENGINE.parents[1] / "hooks" / "hooks.json"


def run(root: Path, *args: str) -> str:
    arguments = list(args)
    environment = os.environ.copy()
    environment["AGENTLOOP_GATE_EVENT_SECRET"] = "agentloop-test-secret"
    if "gate" in arguments and "approved" in arguments:
        def option(name: str) -> str:
            return arguments[arguments.index(name) + 1]
        loop = yaml.safe_load(
            (root / ".agentloop" / "loops" / arguments[1] / "loop.yaml").read_text()
        )
        subjects = [
            arguments[index + 1]
            for index, value in enumerate(arguments)
            if value == "--subject"
        ]
        if not subjects:
            filename = loop["files"].get("requirement") or loop["files"].get("work")
            subjects = [f".agentloop/loops/{arguments[1]}/{filename}"]
        manifest = bytearray()
        for subject in sorted(subjects):
            digest = hashlib.sha256((root / subject).read_bytes()).hexdigest()
            manifest.extend(subject.encode() + b"\0" + digest.encode() + b"\n")
        artifact_digest = hashlib.sha256(manifest).hexdigest()
        payload = "\0".join((
            arguments[1], arguments[2], option("--decision"), option("--actor"),
            option("--source"), option("--source-event-id"),
            str(loop["requirement_version"]), artifact_digest,
        )).encode()
        arguments.extend([
            "--event-signature",
            hmac.new(
                environment["AGENTLOOP_GATE_EVENT_SECRET"].encode(),
                payload,
                hashlib.sha256,
            ).hexdigest(),
        ])
    result = subprocess.run(
        ["python3", str(ENGINE), "--root", str(root), *arguments],
        text=True,
        capture_output=True,
        env=environment,
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

        protected_patch = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "hook", "pre-tool"],
            input=json.dumps({
                "cwd": str(root),
                "tool_input": {
                    "command": (
                        "*** Begin Patch\n"
                        "*** Update File: .agentloop/loops/x/loop.yaml\n"
                        "@@\n-state: draft\n+state: done\n"
                        "*** End Patch\n"
                    )
                },
            }),
            text=True,
            capture_output=True,
        )
        assert protected_patch.returncode == 0
        assert '"permissionDecision": "deny"' in protected_patch.stdout

        loop_id = run(root, "init", "--title", "修正文案", "--level", "trivial")
        run(root, "validate")
        loop_path = root / ".agentloop" / "loops" / loop_id / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        assert loop["state"] == "draft"
        assert (root / ".agentloop" / "schemas" / "loop.schema.json").exists()
        snapshot_path = root / ".agentloop" / "control" / f"{loop_id}.json"
        saved_loop = loop_path.read_text()
        saved_snapshot = snapshot_path.read_text()
        tampered = yaml.safe_load(saved_loop)
        tampered["state"] = "done"
        loop_path.write_text(yaml.safe_dump(tampered, allow_unicode=True, sort_keys=False))
        snapshot_path.unlink()
        result = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "validate"],
            text=True,
            capture_output=True,
        )
        assert result.returncode != 0 and "control snapshot is missing" in result.stderr
        loop_path.write_text(saved_loop)
        snapshot_path.write_text(saved_snapshot)

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
        loop["execution_profile"]["qualifications"].update({
            "single_delivery_unit": True,
            "scope_known": True,
            "low_risk": True,
            "directly_observable": True,
            "concurrent_work": False,
        })
        loop["classification"].update({
            "primary_type": "内部改进",
            "basis": "只调整测试仓库文案",
            "obligations": [
                {
                    "obligation_id": f"IMP-{index}",
                    "kind": kind,
                    "requirement": kind,
                    "source": "work.md",
                    "status": "confirmed",
                }
                for index, kind in enumerate((
                    "baseline", "metric", "target", "external-invariants", "allowed-scope"
                ), 1)
            ],
        })
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
        forged = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "gate", loop_id,
                "requirement_confirmation", "--decision", "approved",
                "--actor", "anyone", "--source", "invented",
                "--source-event-id", "invented-event",
            ],
            text=True,
            capture_output=True,
            env={**os.environ, "AGENTLOOP_GATE_EVENT_SECRET": "agentloop-test-secret"},
        )
        assert forged.returncode != 0 and "signature is invalid" in forged.stderr
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
        work_path = root / ".agentloop" / "loops" / loop_id / "work.md"
        approved_work = work_path.read_text()
        work_path.write_text(approved_work + "\nchanged after approval\n")
        result = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "transition", loop_id,
                "ready_for_development", "--actor", "loop-coordinator",
                "--reason", "should fail",
            ],
            text=True,
            capture_output=True,
        )
        assert result.returncode != 0 and "subject changed after approval" in result.stderr
        work_path.write_text(approved_work)
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
        run(
            root, "transition", composite, "cancelled",
            "--actor", "loop-coordinator", "--reason", "需求在澄清前取消",
        )
        composite = run(
            root,
            "init",
            "--title",
            "重新发起复合交付",
            "--level",
            "composite",
            "--subflow",
            "创建退款",
        )
        run(root, "validate")
        run(
            root, "transition", composite, "clarifying",
            "--actor", "requirement-agent", "--reason", "开始需求澄清",
        )
        run(root, "validate")
        unconfirmed = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "transition", composite,
                "awaiting_requirement_confirmation", "--actor", "requirement-agent",
                "--reason", "分类尚未确认",
            ],
            text=True,
            capture_output=True,
        )
        assert unconfirmed.returncode != 0
        assert "classification primary_type is not confirmed" in unconfirmed.stderr
        assured = run(root, "init", "--title", "根因修复", "--level", "standard")
        assured_dir = root / ".agentloop" / "loops" / assured
        assured_path = assured_dir / "loop.yaml"
        assured_loop = yaml.safe_load(assured_path.read_text())
        assured_loop["state"] = "development_preparing"
        assured_loop["execution_profile"]["status"] = "confirmed"
        assured_loop["routing"]["status"] = "decided"
        assured_loop["routing"]["development"]["main_flow"] = "root-cause"
        assured_loop["classification"].update({
            "primary_type": "内部改进",
            "basis": "控制程序根因修复",
            "obligations": [
                {
                    "obligation_id": f"ROOT-{index}",
                    "kind": kind,
                    "requirement": kind,
                    "source": "README.md",
                    "status": "confirmed",
                }
                for index, kind in enumerate((
                    "baseline", "metric", "target", "external-invariants", "allowed-scope"
                ), 1)
            ],
        })
        assured_path.write_text(
            yaml.safe_dump(assured_loop, allow_unicode=True, sort_keys=False)
        )
        (assured_dir / "development-assurance.yaml").write_text(
            yaml.safe_dump({
                "schema_version": 1,
                "loop_id": assured,
                "requirement_version": 1,
                "route": "root-cause",
                "obligations": [],
            }, allow_unicode=True, sort_keys=False)
        )
        sys_path = Path(__file__).with_name("agentloop.py")
        subprocess.run(
            ["python3", "-c", (
                "import importlib.util,yaml;"
                f"s=importlib.util.spec_from_file_location('a',{str(sys_path)!r});"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                f"r=m.Path({str(root)!r});"
                f"l=yaml.safe_load(m.loop_path(r,{assured!r}).read_text());"
                "m.write_control_snapshot(r,l)"
            )],
            check=True,
        )
        rejected = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "transition", assured,
                "developing", "--actor", "development-agent", "--reason", "missing",
            ],
            text=True,
            capture_output=True,
        )
        assert rejected.returncode != 0 and "assurance obligations are missing" in rejected.stderr
        source_ids = [
            item["obligation_id"] for item in assured_loop["classification"]["obligations"]
        ]
        (assured_dir / "development-assurance.yaml").write_text(
            yaml.safe_dump({
                "schema_version": 1,
                "loop_id": assured,
                "requirement_version": 1,
                "route": "root-cause",
                "obligations": [
                    {
                        "obligation_id": obligation_id,
                        "scope_id": None,
                        "source_obligation_ids": source_ids,
                        "artifact_paths": ["README.md"],
                        "checks": ["可重复检查"],
                        "gate_ids": [],
                        "recovery": "退回 development_preparing",
                    }
                    for obligation_id in ("reproduction", "failing-regression")
                ],
            }, allow_unicode=True, sort_keys=False)
        )
        run(
            root, "transition", assured, "developing",
            "--actor", "development-agent", "--reason", "assurance complete",
        )
        assured_loop = yaml.safe_load(assured_path.read_text())
        assured_loop["state"] = "verifying"
        assured_path.write_text(
            yaml.safe_dump(assured_loop, allow_unicode=True, sort_keys=False)
        )
        subprocess.run(
            ["python3", "-c", (
                "import importlib.util,yaml;"
                f"s=importlib.util.spec_from_file_location('a',{str(sys_path)!r});"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                f"r=m.Path({str(root)!r});"
                f"l=yaml.safe_load(m.loop_path(r,{assured!r}).read_text());"
                "m.write_control_snapshot(r,l)"
            )],
            check=True,
        )
        missing_report = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "evidence", assured,
                "--flow-id", "root-cause-flow", "--executor", "code",
                "--command-json", "[\"python3\",\"-c\",\"pass\"]",
            ],
            text=True,
            capture_output=True,
        )
        assert missing_report.returncode != 0 and "flow evidence requires" in missing_report.stderr
        contradictory = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "evidence", assured,
                "--check-id", "build", "--executor", "command",
                "--result", "failed",
                "--command-json", "[\"python3\",\"-c\",\"pass\"]",
            ],
            text=True,
            capture_output=True,
        )
        assert contradictory.returncode != 0 and "contradicts" in contradictory.stderr
        runtime_schema = root / ".agentloop" / "schemas" / "loop.schema.json"
        runtime_schema.write_text("{}\n")
        stale_runtime = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "validate"],
            text=True,
            capture_output=True,
        )
        assert stale_runtime.returncode != 0 and "runtime Schema is stale" in stale_runtime.stderr
        run(root, "runtime-upgrade")
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
    subprocess.run(["python3", str(PRODUCTION_PROTOTYPE_TEST)], check=True)
    print("passed: AgentLoop full plugin lifecycle")


if __name__ == "__main__":
    main()
