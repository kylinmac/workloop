#!/usr/bin/env python3

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
import yaml
from schema_validation import Validator


ENGINE = Path(__file__).with_name("agentloop.py")
SYNC_REFERENCES = Path(__file__).with_name("sync_references.py")
PROTOTYPE_FIDELITY_TEST = Path(__file__).with_name("test_prototype_fidelity.py")
INTEGRATION_DATA_TEST = Path(__file__).with_name("test_integration_data_source.py")
PRODUCTION_PROTOTYPE_TEST = Path(__file__).with_name("test_production_prototype_gate.py")
CONTEXT_PROJECTION_TEST = Path(__file__).with_name("test_context_projection.py")
REASONING_CONTROLS_TEST = Path(__file__).with_name("test_reasoning_controls.py")
HOOKS = ENGINE.parents[1] / "hooks" / "hooks.json"
SKILLS = ENGINE.parents[1] / "skills"


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
    subprocess.run(["python3", str(CONTEXT_PROJECTION_TEST)], check=True)
    subprocess.run(["python3", str(REASONING_CONTROLS_TEST)], check=True)
    system_python = Path("/usr/bin/python3")
    if system_python.exists():
        subprocess.run([str(system_python), str(ENGINE), "doctor"], check=True)
    source_root = Path(__file__).resolve().parents[3]
    if (source_root / ".git").exists():
        subprocess.run(["python3", str(SYNC_REFERENCES), "check"], check=True)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old_root = root / "cache" / "old"
        current_root = root / "cache" / "current"
        for plugin_root, marker in ((old_root, "selected"), (current_root, "wrong")):
            (plugin_root / "scripts").mkdir(parents=True)
            (plugin_root / "scripts" / "agentloop.py").write_text(
                "from pathlib import Path\nimport sys\n"
                f"Path('hook-result').write_text({marker!r} + ':' + ' '.join(sys.argv[1:]))\n"
            )
        hook = json.loads(HOOKS.read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
        session_hook = json.loads(HOOKS.read_text())["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert "${PLUGIN_ROOT}/scripts/agentloop.py" in session_hook
        router = (SKILLS / "agentloop" / "SKILL.md").read_text()
        assert len(router.splitlines()) <= 80
        for phase in ("requirements", "development", "verification", "integration", "completion", "recovery"):
            phase_skill = (SKILLS / f"agentloop-{phase}" / "SKILL.md").read_text()
            assert len(phase_skill.splitlines()) <= 60
        subprocess.run(
            hook.replace("${PLUGIN_ROOT}", str(old_root)),
            cwd=root,
            shell=True,
            check=True,
        )
        assert (root / "hook-result").read_text() == "selected:hook stop"

        git(root, "init", "-q")
        git(root, "config", "user.name", "AgentLoop Test")
        git(root, "config", "user.email", "agentloop@example.invalid")
        (root / "README.md").write_text("# Test\n")
        git(root, "add", "README.md")
        git(root, "commit", "-qm", "baseline")
        if system_python.exists():
            system_init = subprocess.run(
                [
                    str(system_python), str(ENGINE), "--root", str(root), "init",
                    "--title", "system python runtime", "--level", "standard",
                ],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                [str(system_python), str(ENGINE), "--root", str(root), "validate"],
                check=True,
            )
            subprocess.run(
                [
                    str(system_python), str(ENGINE), "--root", str(root), "transition",
                    system_init, "cancelled", "--actor", "test",
                    "--reason", "system runtime verified",
                ],
                check=True,
            )

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
        project_path = root / ".agentloop" / "project.yaml"
        project = yaml.safe_load(project_path.read_text())
        assert project["approval"]["manual_event_authentication"] == "local_attestation"
        assert project["approval"]["destructive_event_authentication"] == "host_hmac"
        loop_path = root / ".agentloop" / "loops" / loop_id / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        assert loop["state"] == "draft"
        session_context = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "hook", "session-start"],
            input=json.dumps({"cwd": str(root)}),
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        assert " context <loop-id>" in session_context
        assert "load loop.yaml" not in session_context
        requirement_context_text = run(root, "context", loop_id)
        requirement_context = yaml.safe_load(requirement_context_text)
        assert requirement_context["phase"] == "requirements"
        assert requirement_context["phase_skill"] == "development-process-agentloop:agentloop-requirements"
        assert requirement_context["source"]["path"].endswith(f"{loop_id}/loop.yaml")
        assert "classification" in requirement_context
        assert not {"transitions", "gate_events", "git", "routing", "evidence"} & requirement_context.keys()
        assert len(requirement_context_text) < len(loop_path.read_text()) * 0.7
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
        requirement_patch = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "hook", "pre-tool"],
            input=json.dumps({
                "cwd": str(root),
                "tool_input": {
                    "command": (
                        "*** Begin Patch\n"
                        f"*** Update File: {root / '.agentloop' / 'loops' / loop_id / 'work.md'}\n"
                        "@@\n-old\n+new\n"
                        "*** End Patch\n"
                    )
                },
            }),
            text=True,
            capture_output=True,
        )
        assert '"permissionDecision": "deny"' not in requirement_patch.stdout, requirement_patch.stdout
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
        loop["acceptance_obligations"] = [
            {
                "acceptance_id": acceptance_id,
                "criterion": criterion,
                "source": "work.md",
                "required": True,
                "implementation_paths": ["README.md"],
                "verification": {
                    "flow_id": None,
                    "check_id": "self-check",
                    "executor": "command",
                    "subflow_id": None,
                },
            }
            for acceptance_id, criterion in (
                ("AC-01", "README 文案变更可直接观察"),
                ("AC-02", "相邻内容保持不变"),
            )
        ]
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
        run(root, "approval-mode", "--manual", "host_hmac")
        doctor = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "doctor"],
            text=True,
            capture_output=True,
            check=True,
            env={key: value for key, value in os.environ.items() if key != "AGENTLOOP_GATE_EVENT_SECRET"},
        )
        assert "approval-mode --manual local_attestation" in doctor.stdout
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
        destructive = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "gate", loop_id,
                "destructive_action", "--decision", "approved",
                "--actor", "test-user", "--source", "test-host",
                "--source-event-id", "destructive-001",
            ],
            text=True,
            capture_output=True,
            env={key: value for key, value in os.environ.items() if key != "AGENTLOOP_GATE_EVENT_SECRET"},
        )
        assert destructive.returncode != 0 and "host-injected" in destructive.stderr
        run(root, "approval-mode", "--manual", "local_attestation")
        local_gate = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "gate", loop_id,
                "requirement_confirmation", "--decision", "approved",
                "--actor", "test-user", "--source", "codex-chat-local-attestation",
                "--source-event-id", "turn-001",
            ],
            text=True,
            capture_output=True,
        )
        assert local_gate.returncode == 0, local_gate.stderr
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
            "knowledge", loop_id, "--knowledge-id", "KNO-10", "--kind", "unknown",
            "--actor", "requirement-agent", "--statement", "目标页面是否仍使用该文案",
            "--impact", "routing",
        )
        blocked_route = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "route", loop_id,
                "--actor", "development-agent", "--confidence", "high",
                "--main-flow", "quick-change", "--reason", "位置和影响明确",
                "--risk-category", "localized-change", "--risk-statement", "局部回归",
                "--risk-evidence", "单文件范围", "--risk-severity", "low",
                "--verification", "self_check", "--verification-reason", "直接观察",
            ],
            text=True,
            capture_output=True,
        )
        assert blocked_route.returncode != 0 and "unresolved knowledge" in blocked_route.stderr
        run(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-10", "--kind", "unknown",
            "--actor", "requirement-agent", "--status", "resolved",
            "--resolution", "仍使用", "--evidence", "页面路由检查",
        )
        run(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-11", "--kind", "unknown",
            "--actor", "development-agent", "--statement", "目标文件采用哪种编码",
            "--impact", "implementation",
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
            "--risk-category", "localized-change",
            "--risk-statement", "变更范围局限且主要风险是局部回归",
            "--risk-evidence", "已确认的单文件范围和验收映射",
            "--risk-severity", "low",
            "--secondary-risk", json.dumps({
                "category": "user-experience",
                "statement": "文案变化可能影响页面表达",
                "evidence": "README 是用户可见入口",
                "severity": "low",
                "handling": "supporting_flow",
            }, ensure_ascii=False),
            "--secondary-risk", json.dumps({
                "category": "technical-feasibility",
                "statement": "系统 Python 环境必须可运行",
                "evidence": "插件声明为自包含运行时",
                "severity": "low",
                "handling": "verification_obligation",
                "verification_obligation": "使用 /usr/bin/python3 执行 doctor",
            }, ensure_ascii=False),
            "--verification",
            "self_check",
            "--verification-reason",
            "结果可直接观察",
        )
        routed = yaml.safe_load(loop_path.read_text())
        assert len(routed["routing"]["risk_driver"]["secondary_risks"]) == 2
        assert "product-prototype" in routed["routing"]["development"]["supporting_flows"]
        blocked_development = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "transition", loop_id,
                "development_preparing", "--actor", "development-agent",
                "--reason", "实现未知项尚未解决",
            ],
            text=True,
            capture_output=True,
        )
        assert (
            blocked_development.returncode != 0
            and "unresolved knowledge" in blocked_development.stderr
        )
        run(
            root,
            "knowledge", loop_id, "--knowledge-id", "KNO-11", "--kind", "unknown",
            "--actor", "development-agent", "--status", "resolved",
            "--resolution", "UTF-8", "--evidence", "文件编码检查",
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
        development_context = yaml.safe_load(run(root, "context", loop_id))
        assert development_context["phase"] == "development"
        assert development_context["phase_skill"] == "development-process-agentloop:agentloop-development"
        assert "routing" in development_context and "git" in development_context
        assert not {"classification", "transitions", "gate_events", "evidence", "blocked"} & development_context.keys()
        protected = yaml.safe_load(loop_path.read_text())
        protected["execution_profile"]["level"] = "composite"
        loop_path.write_text(yaml.safe_dump(protected, allow_unicode=True, sort_keys=False))
        tamper_result = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "status"],
            text=True,
            capture_output=True,
        )
        assert tamper_result.returncode != 0 and "unauthorized" in tamper_result.stderr
        assert yaml.safe_load(loop_path.read_text())["execution_profile"]["level"] == "trivial"
        illegal_route = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "route", loop_id,
                "--actor", "development-agent", "--confidence", "high",
                "--main-flow", "quick-change", "--reason", "illegal reroute",
                "--risk-category", "localized-change", "--risk-statement", "local",
                "--risk-evidence", "scope", "--risk-severity", "low",
                "--verification", "self_check", "--verification-reason", "illegal",
            ],
            text=True,
            capture_output=True,
        )
        assert illegal_route.returncode != 0 and "routing is only allowed" in illegal_route.stderr
        run(
            root,
            "evidence",
            loop_id,
            "--check-id",
            "self-check",
            "--acceptance-id",
            "AC-01",
            "--executor",
            "command",
            "--command-json",
            "[\"python3\",\"-c\",\"pass\"]",
        )
        incomplete = subprocess.run(
            [
                "python3", str(ENGINE), "--root", str(root), "transition", loop_id,
                "verified", "--actor", "loop-coordinator", "--reason", "coverage incomplete",
                "--evidence", "work.md#开发自检",
            ],
            text=True,
            capture_output=True,
        )
        assert incomplete.returncode != 0
        assert "acceptance evidence is incomplete" in incomplete.stderr
        run(
            root,
            "evidence",
            loop_id,
            "--check-id",
            "self-check",
            "--acceptance-id",
            "AC-01",
            "--acceptance-id",
            "AC-02",
            "--executor",
            "command",
            "--command-json",
            "[\"python3\",\"-c\",\"pass\"]",
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
        completion_context = yaml.safe_load(run(root, "context", loop_id))
        assert completion_context["phase"] == "completion"
        assert completion_context["phase_skill"] == "development-process-agentloop:agentloop-completion"
        assert completion_context["evidence"][0]["result"] == "passed"
        assert not {"classification", "routing", "transitions", "gate_events", "execution"} & completion_context.keys()
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

        legacy = run(root, "init", "--title", "旧控制 Loop", "--level", "standard")
        legacy_path = root / ".agentloop" / "loops" / legacy / "loop.yaml"
        legacy_loop = yaml.safe_load(legacy_path.read_text())
        legacy_loop["classification"]["control_version"] = 1
        legacy_loop.pop("acceptance_obligations")
        legacy_loop.pop("assumptions")
        legacy_loop.pop("decision_records")
        legacy_loop.pop("knowledge_state")
        legacy_loop.pop("quality_metrics")
        legacy_loop.pop("failure_memory")
        legacy_loop["routing"].pop("risk_driver")
        legacy_path.write_text(yaml.safe_dump(legacy_loop, allow_unicode=True, sort_keys=False))
        legacy_validation = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "validate"],
            text=True,
            capture_output=True,
        )
        assert legacy_validation.returncode != 0 and "migrate-v2" in legacy_validation.stderr
        run(root, "migrate-v2", legacy, "--actor", "loop-coordinator")
        migrated = yaml.safe_load(legacy_path.read_text())
        assert migrated["state"] == "clarifying"
        assert migrated["classification"]["control_version"] == 2
        assert migrated["acceptance_obligations"] == []
        assert migrated["assumptions"] == []
        assert migrated["decision_records"] == []
        assert migrated["knowledge_state"] == {"known": [], "unknowns": [], "conflicts": []}
        assert migrated["quality_metrics"] == []
        assert migrated["failure_memory"] == []
        assert migrated["routing"]["risk_driver"] is None
        assert migrated["routing"]["status"] == "pending"
        run(
            root, "transition", legacy, "cancelled",
            "--actor", "loop-coordinator", "--reason", "迁移回归完成",
        )
        terminal_history = yaml.safe_load(legacy_path.read_text())
        terminal_history.pop("acceptance_obligations")
        loop_schema = json.loads(
            (ENGINE.parents[1] / "references" / "agentloop" / "schemas" / "loop.schema.json").read_text()
        )
        assert not list(Validator(loop_schema).iter_errors(terminal_history))

        reasoning_legacy = run(
            root, "init", "--title", "旧推理控制 Loop", "--level", "standard"
        )
        reasoning_path = root / ".agentloop" / "loops" / reasoning_legacy / "loop.yaml"
        reasoning_loop = yaml.safe_load(reasoning_path.read_text())
        reasoning_loop.pop("assumptions")
        reasoning_loop.pop("decision_records")
        reasoning_loop.pop("knowledge_state")
        reasoning_loop.pop("quality_metrics")
        reasoning_loop.pop("failure_memory")
        reasoning_loop["routing"].pop("risk_driver")
        reasoning_path.write_text(
            yaml.safe_dump(reasoning_loop, allow_unicode=True, sort_keys=False)
        )
        reasoning_validation = subprocess.run(
            ["python3", str(ENGINE), "--root", str(root), "validate"],
            text=True,
            capture_output=True,
        )
        assert (
            reasoning_validation.returncode != 0
            and "reasoning control fields require `agentloop migrate-v2`"
            in reasoning_validation.stderr
        )
        run(root, "migrate-v2", reasoning_legacy, "--actor", "loop-coordinator")
        migrated_reasoning = yaml.safe_load(reasoning_path.read_text())
        assert migrated_reasoning["assumptions"] == []
        assert migrated_reasoning["decision_records"] == []
        assert migrated_reasoning["knowledge_state"] == {"known": [], "unknowns": [], "conflicts": []}
        assert migrated_reasoning["quality_metrics"] == []
        assert migrated_reasoning["failure_memory"] == []
        assert migrated_reasoning["routing"]["risk_driver"] is None
        run(
            root, "transition", reasoning_legacy, "cancelled",
            "--actor", "loop-coordinator", "--reason", "推理迁移回归完成",
        )

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
        assured_loop["acceptance_obligations"] = [
            {
                "acceptance_id": "AC-ROOT",
                "criterion": "根因流程可执行",
                "source": "README.md",
                "required": True,
                "implementation_paths": ["README.md"],
                "verification": {
                    "flow_id": "root-cause-flow",
                    "check_id": None,
                    "executor": "code",
                    "subflow_id": None,
                },
            },
            {
                "acceptance_id": "AC-BUILD",
                "criterion": "构建结果可信",
                "source": "README.md",
                "required": True,
                "implementation_paths": ["README.md"],
                "verification": {
                    "flow_id": None,
                    "check_id": "build",
                    "executor": "command",
                    "subflow_id": None,
                },
            },
        ]
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
                "--acceptance-id", "AC-ROOT",
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
                "--acceptance-id", "AC-BUILD",
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
        schema_dir = runtime_schema.parent
        interrupted_backup = schema_dir.with_name(".schemas.upgrade-backup")
        schema_dir.rename(interrupted_backup)
        run(root, "runtime-upgrade")
        assert schema_dir.is_dir() and not interrupted_backup.exists()
        assert runtime_schema.read_bytes() == (
            ENGINE.parents[1] / "references" / "agentloop" / "schemas" / "loop.schema.json"
        ).read_bytes()
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
