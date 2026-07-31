#!/usr/bin/env python3

import importlib.util
import subprocess
import tempfile
from pathlib import Path

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


def page(index: int) -> dict:
    name = f"design/0{index}-page.html"
    route = f"/page-{index}"
    return {
        "prototype_path": name,
        "route": route,
        "subflow_id": None,
        "regions": [{
            "region_id": "main",
            "layout": "header + content",
            "required_controls": [{"control_id": "open", "description": "打开详情"}],
        }],
        "interactions": [{
            "interaction_id": f"open-detail-{index}",
            "region_id": "main",
            "control_id": "open",
            "effect": "client_only_exempt",
            "precondition_database_state": "不适用；纯导航",
            "action": "点击详情",
            "operation_id": None,
            "expected_response": "不适用；纯导航",
            "persistence_assertion": "不产生业务写入",
            "readback_operation_id": None,
            "refresh_assertion": "刷新后路由保持",
            "relogin_assertion": "重新登录后按权限可访问",
            "error_assertion": "加载失败显示错误状态",
            "permission_assertion": "无权限显示 403",
            "downstream_assertion": "不适用；纯导航",
            "audit_assertion": "不适用；纯导航",
            "reuse_or_exemption": "原型保真回归只验证客户端导航",
            "state_change": "显示详情",
            "acceptance_ids": [f"AC-UI-0{index}"],
        }],
        "states": {
            "loading": "显示加载状态",
            "empty": "显示空状态",
            "error": "显示错误状态",
            "unauthorized": "显示无权限状态",
        },
        "data_sources": [f"GET /api/page-{index}"],
        "business_data": [{
            "display_id": "page-content",
            "source_type": "api_field",
            "source": f"GET /api/page-{index} response.content",
            "empty_behavior": "暂无数据",
        }],
        "permissions": ["page:view"],
        "responsive": ["小屏单列"],
        "allowed_deviations": [],
    }


def flow_row(item: dict) -> dict:
    return {
        "prototype_path": item["prototype_path"],
        "route": item["route"],
        "region_id": "main",
        "interaction_id": item["interactions"][0]["interaction_id"],
        "acceptance_id": item["interactions"][0]["acceptance_ids"][0],
        "automation_steps": [f"page-{item['route'][-1]}"],
    }


def evidence_row(item: dict) -> dict:
    value = flow_row(item)
    return {
        **{key: value[key] for key in (
            "prototype_path", "route", "region_id", "interaction_id", "acceptance_id"
        )},
        "automation_step": value["automation_steps"][0],
        "evidence_paths": [f"artifacts/page-{item['route'][-1]}-implementation.png"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repeated = root / "same-line.html"
        repeated.write_text("<a href='/same'>a</a><a href='/same'>b</a><a href='/same'>c</a>")
        repeated_behaviors = AGENTLOOP.scan_prototype_behaviors(repeated, "same-line.html")
        assert len(repeated_behaviors) == 3
        assert len({item["behavior_id"] for item in repeated_behaviors}) == 3
        assert len({item["source_column"] for item in repeated_behaviors}) == 3
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "AgentLoop Test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "agentloop@example.invalid"], cwd=root, check=True)
        (root / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

        result = call(root, "init", "--title", "三页高保真实现", "--level", "standard")
        assert result.returncode == 0, result.stderr
        loop_id = result.stdout.strip()
        loop_dir = root / ".agentloop" / "loops" / loop_id
        loop_path = loop_dir / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        loop["classification"]["control_version"] = 1
        pages = [page(index) for index in range(1, 4)]
        for item in pages:
            path = root / item["prototype_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"<button id='open'>open</button><script>"
                f"document.getElementById('open').addEventListener('click',()=>{{location.href='/detail-{item['route'][-1]}'}})"
                f"</script>"
            )

        loop["state"] = "development_preparing"
        loop["execution_profile"]["status"] = "confirmed"
        loop["routing"]["status"] = "decided"
        loop["routing"]["development"]["main_flow"] = "product-prototype"
        loop["routing"]["development"]["required_outputs"] = ["prototype-implementation-matrix"]
        loop["routing"]["verification"]["policy"] = "flow"
        loop["routing"]["verification"]["new_flows"] = ["prototype-ui"]
        loop["files"]["prototype_matrix"] = "prototype-implementation-matrix.yaml"
        loop["files"]["user_flow_slices"] = "user-flow-slices.yaml"
        loop["files"]["api_contract"] = ["api/openapi.yaml"]
        loop["prototype"] = {
            "implementation_basis": True,
            "type": "high_fidelity",
            "fidelity": {
                "structure": "strict",
                "visual": "strict",
                "interaction": "strict",
                "content": "strict",
            },
            "pages": [{
                "prototype_path": item["prototype_path"],
                "route": item["route"],
                "acceptance": [{
                    "acceptance_id": item["interactions"][0]["acceptance_ids"][0],
                    "criterion": f"{item['route']} 的结构、视觉和详情交互满足原型",
                }],
                "allowed_deviations": [],
            } for item in pages],
        }
        loop_path.write_text(yaml.safe_dump(loop, allow_unicode=True, sort_keys=False))
        AGENTLOOP.write_control_snapshot(root, loop)
        scanned = call(root, "prototype-scan", loop_id, "--actor", "development-agent")
        assert scanned.returncode == 0, scanned.stderr
        inventory = yaml.safe_load(
            (loop_dir / "prototype-behavior-inventory.yaml").read_text()
        )
        for item, source in zip(pages, inventory["sources"]):
            behavior_ids = [behavior["behavior_id"] for behavior in source["behaviors"]]
            navigation_behavior = next(
                behavior for behavior in source["behaviors"] if behavior["kind"] == "navigation"
            )
            interaction = item["interactions"][0]
            interaction["source_behavior_ids"] = behavior_ids
            interaction["journey_required"] = True
            interaction["navigation"] = {
                "source_route": item["route"],
                "trigger": "click",
                "direct_entry_allowed": False,
                "outcomes": [{
                    "outcome_id": f"open-detail-{item['route'][-1]}",
                    "source_behavior_id": navigation_behavior["behavior_id"],
                    "condition": "点击详情",
                    "expected_target": f"/detail-{item['route'][-1]}",
                }],
            }
        (loop_dir / "user-flow-slices.yaml").write_text(yaml.safe_dump({
            "journeys": [{
                "journey_id": "production-smoke",
                "steps": ["create", "edit", "save", "refresh", "relogin", "query", "downstream", "audit"],
                "interaction_ids": [item["interactions"][0]["interaction_id"] for item in pages],
                "outcome_ids": [f"open-detail-{index}" for index in range(1, 4)],
            }],
        }, allow_unicode=True, sort_keys=False))
        (loop_dir / "prototype-implementation-matrix.yaml").write_text(yaml.safe_dump({
            "schema_version": 1,
            "loop_id": loop_id,
            "requirement_version": 1,
            "pages": pages[:1],
        }, allow_unicode=True, sort_keys=False))
        rejected = call(
            root, "transition", loop_id, "developing",
            "--actor", "development-agent", "--reason", "矩阵不完整时不应编码",
        )
        assert rejected.returncode != 0
        loop = yaml.safe_load(loop_path.read_text())
        loop["state"] = "verifying"
        loop_path.write_text(yaml.safe_dump(loop, allow_unicode=True, sort_keys=False))
        (loop_dir / "prototype-implementation-matrix.yaml").write_text(yaml.safe_dump({
            "schema_version": 1,
            "loop_id": loop_id,
            "requirement_version": 1,
            "pages": pages,
        }, allow_unicode=True, sort_keys=False))

        reports = root / "reports"
        reports.mkdir()
        (reports / "ui.md").write_text("# 页面打开通过\n")
        flow_path = root / ".agentloop" / "flows" / "prototype-ui.yaml"
        flow_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "flow_id": "prototype-ui",
            "title": "不完整原型检查",
            "executor": "ui",
            "status": "active",
            "covers": {"paths": [], "interfaces": [], "routes": ["/page-1"], "db_objects": [], "states": [], "tags": []},
            "preconditions": [],
            "steps": [{"action": "打开页面", "expect": "页面可见"}],
            "checks": ["visual"],
            "automation": {"path": "reports/ui.md"},
        }, allow_unicode=True, sort_keys=False))
        (loop_dir / "evidence.yaml").write_text(yaml.safe_dump({
            "schema_version": 1,
            "loop_id": loop_id,
            "runs": [{
                "evidence_id": f"{loop_id}-evidence-01",
                "flow_id": "prototype-ui",
                "check_id": None,
                "subflow_id": None,
                "requirement_version": 1,
                "executor": "ui",
                "command": ["open", "/page-1"],
                "result": "passed",
                "exit_code": 0,
                "counts": {"passed": 1, "failed": 0, "skipped": 0},
                "validity": "active",
                "code_commit": subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
                ).stdout.strip(),
                "environment": "local",
                "started_at": "2026-07-30T14:00:00+08:00",
                "ended_at": "2026-07-30T14:00:01+08:00",
                "duration_ms": 1000,
                "stdout_path": "reports/ui.md",
                "stderr_path": None,
                "coverage": [],
                "artifacts": [],
            }],
        }, allow_unicode=True, sort_keys=False))
        AGENTLOOP.write_control_snapshot(root, loop)

        assert call(root, "validate").returncode != 0
        rejected = call(
            root, "transition", loop_id, "verified",
            "--actor", "loop-coordinator", "--reason", "不应通过",
        )
        assert rejected.returncode != 0
        assert yaml.safe_load(loop_path.read_text())["state"] == "verifying"

        standalone = yaml.safe_load(loop_path.read_text())
        composite = yaml.safe_load(loop_path.read_text())
        composite["state"] = "orchestrating"
        composite["execution_profile"]["level"] = "composite"
        composite["subflows"] = []
        AGENTLOOP.add_subflows(composite, ["产品页面"])
        subflow = composite["subflows"][0]
        subflow["state"] = "passed"
        subflow["main_flow"] = "product-prototype"
        subflow["prototype_pages"] = [
            {"prototype_path": item["prototype_path"], "route": item["route"]}
            for item in pages
        ]
        subflow["verification"]["policy"] = "flow"
        subflow["verification"]["new_flows"] = ["prototype-ui"]
        composite["git"]["integration"]["status"] = "verified"
        loop_path.write_text(yaml.safe_dump(composite, allow_unicode=True, sort_keys=False))
        matrix = yaml.safe_load((loop_dir / "prototype-implementation-matrix.yaml").read_text())
        for item in matrix["pages"]:
            item["subflow_id"] = subflow["subflow_id"]
        (loop_dir / "prototype-implementation-matrix.yaml").write_text(
            yaml.safe_dump(matrix, allow_unicode=True, sort_keys=False)
        )
        evidence = yaml.safe_load((loop_dir / "evidence.yaml").read_text())
        evidence["runs"][0]["subflow_id"] = subflow["subflow_id"]
        (loop_dir / "evidence.yaml").write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False))
        AGENTLOOP.write_control_snapshot(root, composite)
        rejected = call(
            root, "transition", loop_id, "verified",
            "--actor", "loop-coordinator", "--reason", "父级不应只信任 passed",
        )
        assert rejected.returncode != 0

        loop = standalone
        loop["state"] = "verifying"
        loop_path.write_text(yaml.safe_dump(loop, allow_unicode=True, sort_keys=False))
        for item in matrix["pages"]:
            item["subflow_id"] = None
        (loop_dir / "prototype-implementation-matrix.yaml").write_text(
            yaml.safe_dump(matrix, allow_unicode=True, sort_keys=False)
        )
        evidence["runs"][0]["subflow_id"] = None
        (loop_dir / "evidence.yaml").write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False))
        AGENTLOOP.write_control_snapshot(root, loop)

        automation = root / "tests" / "ui" / "prototype.py"
        automation.parent.mkdir(parents=True)
        automation.write_text("print('prototype coverage passed')\n")
        artifacts = root / "artifacts"
        artifacts.mkdir()
        for index in range(1, 4):
            (artifacts / f"page-{index}-reference.png").write_text("reference")
            (artifacts / f"page-{index}-implementation.png").write_text("implementation")
            (artifacts / f"page-{index}-navigation.json").write_text("{}")
        viewport = {"width": 1440, "height": 900}
        flow_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "flow_id": "prototype-ui",
            "title": "完整原型检查",
            "executor": "ui",
            "status": "active",
            "covers": {"paths": [], "interfaces": [], "routes": [item["route"] for item in pages], "db_objects": [], "states": [], "tags": []},
            "preconditions": [],
            "steps": [{
                "step_id": f"page-{index}",
                "action": f"验证第 {index} 页结构、视觉和交互",
                "expect": "满足原型及允许差异",
                "screenshot": f"page-{index}",
            } for index in range(1, 4)],
            "checks": ["visual", "interaction"],
            "automation": {"path": "tests/ui/prototype.py"},
            "prototype": {
                "type": "high_fidelity",
                "references": [{"prototype_path": item["prototype_path"], "route": item["route"]} for item in pages],
            },
            "visual_validation": {
                "viewport": viewport,
                "comparison": "both",
                "allowed_differences": [],
                "pass_criteria": "DOM 必需项全量匹配且截图差异不超过 1%",
            },
            "coverage": [flow_row(item) for item in pages],
        }, allow_unicode=True, sort_keys=False))
        evidence = yaml.safe_load((loop_dir / "evidence.yaml").read_text())
        run = evidence["runs"][0]
        run["coverage"] = [evidence_row(item) for item in pages]
        run["visual"] = {
            "viewport": viewport,
            "comparison": "both",
            "allowed_differences": [],
            "pass_criteria": "DOM 必需项全量匹配且截图差异不超过 1%",
            "references": [{
                "prototype_path": item["prototype_path"],
                "reference_path": f"artifacts/page-{index}-reference.png",
                "implementation_path": f"artifacts/page-{index}-implementation.png",
            } for index, item in enumerate(pages, 1)],
            "result": "passed",
        }
        run["navigation"] = {
            "edges": [{
                "interaction_id": item["interactions"][0]["interaction_id"],
                "outcome_id": f"open-detail-{index}",
                "source_route": item["route"],
                "action": "user_action",
                "direct_navigation": False,
                "observed_target": f"/detail-{index}",
                "evidence_paths": [f"artifacts/page-{index}-navigation.json"],
            } for index, item in enumerate(pages, 1)]
        }
        run["navigation"]["edges"][0]["direct_navigation"] = True
        (loop_dir / "evidence.yaml").write_text(
            yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False)
        )
        assert call(root, "validate").returncode != 0
        run["navigation"]["edges"][0]["direct_navigation"] = False
        (loop_dir / "evidence.yaml").write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False))

        passed = call(root, "validate")
        assert passed.returncode == 0, passed.stderr
        passed = call(
            root, "transition", loop_id, "verified",
            "--actor", "loop-coordinator", "--reason", "原型覆盖与视觉证据完整",
        )
        assert passed.returncode == 0, passed.stderr
        legacy_loop = yaml.safe_load(loop_path.read_text())
        legacy_loop["files"].pop("prototype_behavior_inventory")
        loop_path.write_text(yaml.safe_dump(legacy_loop, allow_unicode=True, sort_keys=False))
        (loop_dir / "prototype-behavior-inventory.yaml").unlink()
        AGENTLOOP.write_control_snapshot(root, legacy_loop)
        recovered = call(
            root, "gate", loop_id, "completion",
            "--decision", "rejected",
            "--actor", "test-user",
            "--source", "test-host",
            "--source-event-id", "prototype-rejection-001",
            "--reason", "第 2 页与原型不一致",
            "--affected-page", "/page-2",
            "--revalidation-scope", "/page-2",
        )
        assert recovered.returncode == 0, recovered.stderr
        recovered_loop = yaml.safe_load(loop_path.read_text())
        assert recovered_loop["state"] == "development_preparing"
        assert recovered_loop["failure_handoff"]["affected_routes"] == ["/page-2"]
        assert yaml.safe_load((loop_dir / "evidence.yaml").read_text())["runs"][0]["validity"] == "stale"

    print("passed: prototype fidelity gate rejects partial UI evidence")


if __name__ == "__main__":
    main()
