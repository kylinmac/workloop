#!/usr/bin/env python3

import importlib.util
import json
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


def write_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
        ).stdout.strip()

        created = call(root, "init", "--title", "生产预算系统", "--level", "standard")
        assert created.returncode == 0, created.stderr
        loop_id = created.stdout.strip()
        loop_dir = root / ".agentloop" / "loops" / loop_id
        loop_path = loop_dir / "loop.yaml"
        loop = yaml.safe_load(loop_path.read_text())
        prototype_path = root / "design" / "budget.html"
        prototype_path.parent.mkdir()
        prototype_path.write_text("<html><body>budget</body></html>")
        loop["state"] = "development_preparing"
        loop["execution_profile"]["status"] = "confirmed"
        loop["routing"]["status"] = "decided"
        loop["routing"]["development"]["main_flow"] = "product-prototype"
        loop["routing"]["verification"]["policy"] = "flow"
        loop["routing"]["verification"]["new_flows"] = ["budget-production"]
        loop["files"]["prototype_matrix"] = "prototype-implementation-matrix.yaml"
        loop["files"]["user_flow_slices"] = "user-flow-slices.yaml"
        loop["files"]["api_contract"] = ["api/openapi.yaml"]
        loop["prototype"] = {
            "implementation_basis": True,
            "type": "high_fidelity",
            "fidelity": {
                "structure": "strict", "visual": "strict",
                "interaction": "strict", "content": "adjustable",
            },
            "pages": [{
                "prototype_path": "design/budget.html",
                "route": "/budget",
                "acceptance": [{"acceptance_id": "AC-BUDGET", "criterion": "预算保存后刷新和重登仍保持"}],
                "allowed_deviations": [],
            }],
        }
        write_yaml(loop_path, loop)
        interaction = {
            "interaction_id": "save-budget",
            "region_id": "main",
            "control_id": "save",
            "effect": "server_mutation",
            "precondition_database_state": "budgets 中存在 sentinel 记录",
            "action": "浏览器输入预算并点击保存",
            "operation_id": "updateBudget",
            "expected_response": "200 且返回 persisted sentinel",
            "persistence_assertion": "Repository 查询为新值",
            "readback_operation_id": "getBudget",
            "refresh_assertion": "刷新页面仍显示新值",
            "relogin_assertion": "重新登录仍显示新值",
            "error_assertion": "非法值返回 422",
            "permission_assertion": "普通成员返回 403",
            "downstream_assertion": "报表流程读取新预算",
            "audit_assertion": "审计记录包含修改人和前后值",
            "reuse_or_exemption": None,
            "state_change": "服务端预算持久化",
            "acceptance_ids": ["AC-BUDGET"],
        }
        write_yaml(loop_dir / "prototype-implementation-matrix.yaml", {
            "schema_version": 1,
            "loop_id": loop_id,
            "requirement_version": 1,
            "pages": [{
                "prototype_path": "design/budget.html",
                "route": "/budget",
                "subflow_id": None,
                "regions": [{"region_id": "main", "layout": "form", "required_controls": [
                    {"control_id": "save", "description": "保存预算"}
                ]}],
                "interactions": [interaction],
                "states": {
                    "loading": "加载", "empty": "暂无数据",
                    "error": "错误", "unauthorized": "无权限",
                },
                "data_sources": ["GET /api/budget", "PUT /api/budget"],
                "business_data": [{
                    "display_id": "budget-value",
                    "source_type": "api_field",
                    "source": "getBudget response.amount",
                    "empty_behavior": "暂无数据",
                }],
                "permissions": ["budget:write"],
                "responsive": ["窄屏单列"],
                "allowed_deviations": [],
            }],
        })
        write_yaml(loop_dir / "user-flow-slices.yaml", {
            "journeys": [{
                "journey_id": "budget-lifecycle",
                "steps": ["create", "edit", "save", "refresh", "relogin", "query", "downstream", "audit"],
                "interaction_ids": ["save-budget"],
            }],
        })
        AGENTLOOP.write_control_snapshot(root, loop)
        rejected = call(root, "transition", loop_id, "developing", "--actor", "dev", "--reason", "契约缺失")
        assert rejected.returncode != 0 and "API contract" in rejected.stderr

        write_yaml(root / "api" / "openapi.yaml", {
            "openapi": "3.0.3",
            "info": {"title": "Budget", "version": "1"},
            "paths": {
                "/api/budget": {
                    "put": {"operationId": "updateBudget", "responses": {"200": {"description": "ok"}}},
                    "get": {"operationId": "getBudget", "responses": {"200": {"description": "ok"}}},
                }
            },
        })
        passed = call(root, "transition", loop_id, "developing", "--actor", "dev", "--reason", "契约与旅程完整")
        assert passed.returncode == 0, passed.stderr

        runner = root / "tests" / "budget_ui.py"
        runner.parent.mkdir()
        runner.write_text(
            "import json, os\n"
            "from pathlib import Path\n"
            "root=Path.cwd(); art=root/'artifacts'; art.mkdir(exist_ok=True)\n"
            "[(art/n).write_text('sentinel') for n in ['ref.png','impl.png','journey.json']]\n"
            "report={'code_commit':os.environ['AGENTLOOP_CODE_COMMIT'],'run_nonce':os.environ['AGENTLOOP_RUN_NONCE'],"
            "'assertions':14,'executed_steps':['budget-save'],'assertions_by_step':{'budget-save':14},'skipped_required':0,"
            "'coverage':[{'prototype_path':'design/budget.html','route':'/budget','region_id':'main',"
            "'interaction_id':'save-budget','acceptance_id':'AC-BUDGET','automation_step':'budget-save',"
            "'evidence_paths':['artifacts/journey.json']}],"
            "'visual':{'viewport':{'width':1440,'height':900},'comparison':'both','allowed_differences':[],"
            "'pass_criteria':'DOM 完整且截图差异小于 1%','references':[{'prototype_path':'design/budget.html',"
            "'reference_path':'artifacts/ref.png','implementation_path':'artifacts/impl.png'}],'result':'passed'},"
            "'business_function':{'interactions':[{'interaction_id':'save-budget','assertion_count':13,"
            "'skipped':False,'ui_action':True,'operation':True,'response':True,'persistence':True,"
            "'readback':True,'refresh':True,'relogin':True,'error':True,'permission':True,'downstream':True,"
            "'audit':True,'evidence_paths':['artifacts/journey.json']}],"
            "'journeys':[{'journey_id':'budget-lifecycle','steps':['create','edit','save','refresh','relogin',"
            "'query','downstream','audit'],'assertion_count':14,'skipped':False,"
            "'evidence_paths':['artifacts/journey.json']}]}}\n"
            "Path(os.environ['AGENTLOOP_REPORT_PATH']).write_text(json.dumps(report))\n"
        )
        write_yaml(root / ".agentloop" / "flows" / "budget-production.yaml", {
            "schema_version": 1,
            "flow_id": "budget-production",
            "title": "预算生产旅程",
            "executor": "ui",
            "status": "active",
            "covers": {
                "paths": [], "interfaces": ["PUT /api/budget", "GET /api/budget"],
                "routes": ["/budget"], "db_objects": ["budgets"], "states": [], "tags": [],
            },
            "preconditions": ["隔离数据库"],
            "steps": [{
                "step_id": "budget-save", "action": "执行完整预算旅程",
                "expect": "持久化且可审计", "screenshot": "artifacts/impl.png",
            }],
            "checks": ["visual", "interaction", "business_function"],
            "automation": {"path": "tests/budget_ui.py"},
            "prototype": {"type": "high_fidelity", "references": [
                {"prototype_path": "design/budget.html", "route": "/budget"}
            ]},
            "visual_validation": {
                "viewport": {"width": 1440, "height": 900},
                "comparison": "both",
                "allowed_differences": [],
                "pass_criteria": "DOM 完整且截图差异小于 1%",
            },
            "coverage": [{
                "prototype_path": "design/budget.html", "route": "/budget",
                "region_id": "main", "interaction_id": "save-budget",
                "acceptance_id": "AC-BUDGET", "automation_steps": ["budget-save"],
            }],
        })
        loop = yaml.safe_load(loop_path.read_text())
        loop["state"] = "verifying"
        loop["git"]["head_commit"] = head
        write_yaml(loop_path, loop)
        AGENTLOOP.write_control_snapshot(root, loop)
        evidence = call(
            root, "evidence", loop_id, "--flow-id", "budget-production", "--executor", "ui",
            "--command-json", '["python3","tests/budget_ui.py"]',
            "--report-path", "artifacts/budget-report.json",
        )
        assert evidence.returncode == 0, evidence.stderr
        verified = call(root, "transition", loop_id, "verified", "--actor", "verify", "--reason", "业务与视觉独立通过")
        assert verified.returncode == 0, verified.stderr

        tampered = yaml.safe_load(loop_path.read_text())
        tampered["state"] = "developing"
        write_yaml(loop_path, tampered)
        detected = call(root, "status")
        assert detected.returncode != 0 and "unauthorized" in detected.stderr
        assert yaml.safe_load(loop_path.read_text())["state"] == "verified"

        composite = call(
            root, "init", "--title", "复合流程", "--level", "composite", "--subflow", "业务页面"
        )
        assert composite.returncode == 0, composite.stderr
        composite_id = composite.stdout.strip()
        composite_path = root / ".agentloop" / "loops" / composite_id / "loop.yaml"
        parent = yaml.safe_load(composite_path.read_text())
        parent["state"] = "orchestrating"
        parent["routing"]["status"] = "decided"
        parent["routing"]["verification"]["new_flows"] = ["integration-command"]
        write_yaml(root / ".agentloop" / "flows" / "integration-command.yaml", {
            "schema_version": 1,
            "flow_id": "integration-command",
            "title": "非视觉集成检查",
            "executor": "command",
            "status": "active",
            "covers": {
                "paths": [], "interfaces": [], "routes": [],
                "db_objects": [], "states": [], "tags": [],
            },
            "preconditions": [],
            "steps": [{"step_id": "build", "action": "构建", "expect": "成功"}],
            "checks": ["build"],
        })
        write_yaml(composite_path, parent)
        AGENTLOOP.write_control_snapshot(root, parent)
        subflow_id = parent["subflows"][0]["subflow_id"]
        moved = call(
            root, "transition", composite_id, "development_preparing",
            "--subflow-id", subflow_id, "--actor", "coordinator", "--reason", "子流程准备",
        )
        assert moved.returncode == 0, moved.stderr
        assert yaml.safe_load(composite_path.read_text())["state"] == "orchestrating"
        assert yaml.safe_load(composite_path.read_text())["subflows"][0]["state"] == "development_preparing"
        parent = yaml.safe_load(composite_path.read_text())
        parent["git"]["integration"]["delivery_commit"] = "c4e33a5"
        def verifying_transition(owner: str, commit: str) -> dict:
            return {
                "from": "ready_for_verification", "to": "verifying", "subflow_id": owner,
                "actor": "verify", "at": "2026-01-01T00:00:00+00:00",
                "requirement_version": 1, "git_commit": commit, "evidence": [], "reason": "test",
            }
        parent["transitions"].extend([
            verifying_transition(subflow_id, "old-subflow"),
            verifying_transition("sf-other", "other-subflow"),
            verifying_transition(subflow_id, "46804e8"),
        ])
        assert AGENTLOOP.tested_commit_for_scope(parent, subflow_id) == "46804e8"
        assert AGENTLOOP.tested_commit_for_scope(parent, "sf-missing") is None
        assert AGENTLOOP.tested_commit_for_scope(parent, None) == "c4e33a5"

        parent["state"] = "blocked"
        parent["blocked"] = {
            "reason": "旧集成提交",
            "owner": "coordinator",
            "unblock_condition": "记录当前集成 checkpoint",
            "resume_state": "orchestrating",
        }
        parent["prototype"] = loop["prototype"]
        parent["files"].update({
            "prototype_matrix": "prototype-implementation-matrix.yaml",
            "user_flow_slices": "user-flow-slices.yaml",
            "api_contract": ["api/openapi.yaml"],
        })
        parent["subflows"][0]["state"] = "passed"
        parent["subflows"][0]["main_flow"] = "product-prototype"
        parent["subflows"][0]["prototype_pages"] = [{
            "prototype_path": "design/budget.html", "route": "/budget",
        }]
        parent["subflows"][0]["verification"]["new_flows"] = ["budget-production"]
        parent["integration_verification"]["required"] = True
        parent["integration_verification"]["state"] = "failed"
        parent["transitions"][-1]["git_commit"] = head
        matrix = yaml.safe_load((loop_dir / "prototype-implementation-matrix.yaml").read_text())
        matrix["loop_id"] = composite_id
        matrix["pages"][0]["subflow_id"] = subflow_id
        write_yaml(composite_path.parent / "prototype-implementation-matrix.yaml", matrix)
        write_yaml(
            composite_path.parent / "user-flow-slices.yaml",
            yaml.safe_load((loop_dir / "user-flow-slices.yaml").read_text()),
        )
        run = yaml.safe_load((loop_dir / "evidence.yaml").read_text())["runs"][-1]
        run.update({
            "evidence_id": f"{composite_id}-evidence-01",
            "subflow_id": subflow_id,
            "code_commit": head,
        })
        run["test_report"]["code_commit"] = head
        invalid_run = dict(run)
        invalid_run["evidence_id"] = f"{composite_id}-evidence-stale"
        invalid_run["code_commit"] = "stale-commit"
        write_yaml(composite_path.parent / "evidence.yaml", {
            "schema_version": 1, "loop_id": composite_id, "runs": [invalid_run],
        })
        write_yaml(composite_path, parent)
        AGENTLOOP.write_control_snapshot(root, parent)
        rejected_checkpoint = call(
            root, "integration-checkpoint", composite_id,
            "--actor", "coordinator", "--reason", "错误提交",
            "--evidence", invalid_run["evidence_id"],
        )
        assert rejected_checkpoint.returncode != 0 and "current requirement and commit" in rejected_checkpoint.stderr
        write_yaml(composite_path.parent / "evidence.yaml", {
            "schema_version": 1, "loop_id": composite_id, "runs": [run],
        })
        AGENTLOOP.write_control_snapshot(root, parent)
        checkpoint = call(
            root, "integration-checkpoint", composite_id,
            "--actor", "coordinator", "--reason", "当前集成回归通过",
            "--evidence", run["evidence_id"], "--git-commit", head,
        )
        assert checkpoint.returncode == 0, checkpoint.stderr
        checkpointed = yaml.safe_load(composite_path.read_text())
        assert checkpointed["git"]["integration"]["head_commit"] == head
        assert checkpointed["git"]["integration"]["delivery_commit"] == head
        assert checkpointed["integration_verification"]["handoff"]["code_commit"] == head
        resumed = call(
            root, "transition", composite_id, "orchestrating",
            "--actor", "coordinator", "--reason", "checkpoint 已完成",
        )
        assert resumed.returncode == 0, resumed.stderr
        aggregated = call(
            root, "transition", composite_id, "verified",
            "--actor", "coordinator", "--reason", "聚合子流程 Evidence",
        )
        assert aggregated.returncode == 0, aggregated.stderr
        validated = call(root, "validate")
        assert validated.returncode == 0, validated.stderr

    print("passed: production prototype and control gates")


if __name__ == "__main__":
    main()
