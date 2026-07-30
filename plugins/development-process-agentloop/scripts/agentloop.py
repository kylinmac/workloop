#!/usr/bin/env python3
"""Repository-backed control plane for the AgentLoop Codex plugin."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as error:
    raise SystemExit(
        "AgentLoop requires Python packages PyYAML and jsonschema. "
        "Install them in the project environment before using the plugin."
    ) from error


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PLUGIN_ROOT / "references"
SCHEMA_ROOT = REFERENCE_ROOT / "agentloop" / "schemas"
EXAMPLE_ROOT = REFERENCE_ROOT / "agentloop" / "examples"
TERMINAL_STATES = {"done", "cancelled"}
EDITABLE_STATES = {
    "ready_for_development",
    "development_preparing",
    "developing",
    "ready_for_verification",
    "verifying",
    "orchestrating",
    "verified",
}
TRANSITIONS = {
    "draft": {"clarifying", "blocked", "cancelled"},
    "clarifying": {"awaiting_requirement_confirmation", "blocked", "cancelled"},
    "awaiting_requirement_confirmation": {"ready_for_development", "clarifying", "blocked", "cancelled"},
    "ready_for_development": {"development_preparing", "orchestrating", "clarifying", "blocked", "cancelled"},
    "development_preparing": {"developing", "clarifying", "blocked", "cancelled"},
    "developing": {"development_preparing", "ready_for_verification", "verified", "clarifying", "blocked", "cancelled"},
    "ready_for_verification": {"verifying", "developing", "clarifying", "blocked", "cancelled"},
    "verifying": {"verified", "developing", "clarifying", "blocked", "cancelled"},
    "orchestrating": {"verified", "clarifying", "blocked", "cancelled"},
    "verified": {"done", "clarifying", "blocked", "cancelled"},
    "blocked": set(),
}
AUTOMATION_SUFFIXES = {
    ".bash", ".cjs", ".go", ".java", ".js", ".jsx", ".kt", ".mjs",
    ".php", ".py", ".rb", ".rs", ".sh", ".swift", ".ts", ".tsx",
}
VAGUE_PROTOTYPE_ACCEPTANCE = {"按原型实现", "还原原型", "与原型一致"}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if check and result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def git_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(
            "project is not under Git. Complete the repository_bootstrap Gate, "
            "inspect the initial commit scope, initialize Git, and rerun."
        )
    return Path(result.stdout.strip()).resolve()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML object")
    return data


def atomic_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def schema_validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_ROOT / name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_file(path: Path, schema_name: str) -> list[str]:
    try:
        data = load_yaml(path)
    except Exception as error:
        return [f"{path}: {error}"]
    errors = sorted(schema_validator(schema_name).iter_errors(data), key=lambda item: list(item.path))
    return [f"{path}: {error.json_path}: {error.message}" for error in errors]


def project_file(root: Path, value: str) -> Path | None:
    path = (root / value).resolve()
    if path != root and root not in path.parents:
        return None
    return path


def flow_requires_visual(flow: dict) -> bool:
    return "visual" in flow.get("checks", []) or flow.get("prototype", {}).get("type") == "high_fidelity"


def automation_errors(root: Path, flow: dict) -> list[str]:
    automation = flow.get("automation")
    if not automation:
        return [f"flow {flow.get('flow_id')}: UI flow has no automation"] if flow.get("executor") == "ui" else []
    value = automation.get("path", "")
    path = project_file(root, value)
    if path is None:
        return [f"flow {flow.get('flow_id')}: automation escapes project root: {value}"]
    if path.suffix.lower() == ".md":
        return [f"flow {flow.get('flow_id')}: Markdown report cannot be automation: {value}"]
    if not path.is_file():
        return [f"flow {flow.get('flow_id')}: automation file does not exist: {value}"]
    if path.suffix.lower() not in AUTOMATION_SUFFIXES and not os.access(path, os.X_OK):
        return [f"flow {flow.get('flow_id')}: automation is not an executable test or script: {value}"]
    return []


def flow_semantic_errors(root: Path, flow: dict) -> list[str]:
    errors = automation_errors(root, flow)
    step_ids = [step.get("step_id") for step in flow.get("steps", []) if step.get("step_id")]
    if len(step_ids) != len(set(step_ids)):
        errors.append(f"flow {flow.get('flow_id')}: duplicate step_id")
    if not flow_requires_visual(flow):
        return errors
    references = {
        (item["prototype_path"], item["route"])
        for item in flow.get("prototype", {}).get("references", [])
    }
    coverage = flow.get("coverage", [])
    covered_pages = {(item["prototype_path"], item["route"]) for item in coverage}
    if references != covered_pages:
        errors.append(f"flow {flow.get('flow_id')}: visual coverage does not match prototype references")
    known_steps = set(step_ids)
    for item in coverage:
        missing = set(item.get("automation_steps", [])) - known_steps
        if missing:
            errors.append(
                f"flow {flow.get('flow_id')}: coverage references unknown automation steps: {sorted(missing)}"
            )
    for prototype_path, _ in references:
        path = project_file(root, prototype_path)
        if path is None or not path.is_file():
            errors.append(f"flow {flow.get('flow_id')}: reference prototype does not exist: {prototype_path}")
    return errors


def prototype_is_required(loop: dict, subflow: dict | None = None) -> bool:
    if subflow is not None:
        return subflow.get("main_flow") == "product-prototype" or bool(subflow.get("prototype_pages"))
    prototype = loop.get("prototype", {})
    return (
        loop.get("routing", {}).get("development", {}).get("main_flow") == "product-prototype"
        or prototype.get("implementation_basis") is True
        or prototype.get("type") == "high_fidelity"
    )


def prototype_declaration_errors(root: Path, loop: dict) -> list[str]:
    prototype = loop.get("prototype")
    if prototype is None:
        return ["prototype decision must be explicitly declared before requirement confirmation"]
    errors = []
    if prototype.get("implementation_basis"):
        for page in prototype.get("pages", []):
            source = project_file(root, page["prototype_path"])
            if source is None or not source.is_file():
                errors.append(f"declared prototype does not exist: {page['prototype_path']}")
            for acceptance in page.get("acceptance", []):
                criterion = acceptance["criterion"]
                if criterion.strip().rstrip("。") in VAGUE_PROTOTYPE_ACCEPTANCE:
                    errors.append(
                        f"prototype {page.get('prototype_path')}: acceptance criterion is not executable: {criterion}"
                    )
    return errors


def load_prototype_matrix(root: Path, loop: dict) -> tuple[dict | None, list[str]]:
    if not prototype_is_required(loop) and not any(
        prototype_is_required(loop, subflow) for subflow in loop.get("subflows", [])
    ):
        return None, []
    errors = []
    prototype = loop.get("prototype")
    if not prototype:
        return None, ["prototype declaration is required"]
    errors.extend(prototype_declaration_errors(root, loop))
    value = loop.get("files", {}).get("prototype_matrix")
    if not value:
        return None, errors + ["files.prototype_matrix is required"]
    path = loop_dir(root, loop["loop_id"]) / value
    if not path.is_file():
        return None, errors + [f"prototype implementation matrix is missing: {path}"]
    errors.extend(validate_file(path, "prototype-matrix.schema.json"))
    if errors:
        return None, errors
    matrix = load_yaml(path)
    if matrix["loop_id"] != loop["loop_id"]:
        errors.append("prototype matrix loop_id does not match Loop")
    if matrix["requirement_version"] != loop["requirement_version"]:
        errors.append("prototype matrix requirement_version is stale")
    declared = {
        (page["prototype_path"], page["route"])
        for page in prototype.get("pages", [])
    }
    implemented = {
        (page["prototype_path"], page["route"])
        for page in matrix.get("pages", [])
    }
    if declared != implemented:
        errors.append("prototype matrix pages do not exactly match declared prototype pages")
    declared_acceptance = {
        (page["prototype_path"], page["route"]): {
            item["acceptance_id"] for item in page["acceptance"]
        }
        for page in prototype.get("pages", [])
    }
    subflow_ids = {item["subflow_id"] for item in loop.get("subflows", [])}
    for page in matrix.get("pages", []):
        source = project_file(root, page["prototype_path"])
        if source is None or not source.is_file():
            errors.append(f"prototype source does not exist: {page['prototype_path']}")
        if loop.get("subflows") and page.get("subflow_id") not in subflow_ids:
            errors.append(f"prototype page has no valid subflow owner: {page['prototype_path']}")
        controls = {
            (region["region_id"], control["control_id"])
            for region in page["regions"]
            for control in region["required_controls"]
        }
        interactions = {
            (item["region_id"], item["control_id"])
            for item in page["interactions"]
        }
        if controls - interactions:
            errors.append(
                f"prototype page has controls without interaction coverage: {page['prototype_path']}"
            )
        if interactions - controls:
            errors.append(
                f"prototype page interactions reference unknown controls: {page['prototype_path']}"
            )
        mapped_acceptance = {
            acceptance_id
            for interaction in page["interactions"]
            for acceptance_id in interaction["acceptance_ids"]
        }
        if mapped_acceptance != declared_acceptance.get(
            (page["prototype_path"], page["route"]), set()
        ):
            errors.append(
                f"prototype page acceptance mapping is incomplete or unknown: {page['prototype_path']}"
            )
    return matrix, errors


def matrix_keys(matrix: dict, subflow_id: str | None = None) -> set[tuple[str, ...]]:
    result = set()
    for page in matrix.get("pages", []):
        if subflow_id is not None and page.get("subflow_id") != subflow_id:
            continue
        for interaction in page["interactions"]:
            for acceptance_id in interaction["acceptance_ids"]:
                result.add((
                    page["prototype_path"],
                    page["route"],
                    interaction["region_id"],
                    interaction["interaction_id"],
                    acceptance_id,
                ))
    return result


def coverage_key(item: dict) -> tuple[str, ...]:
    return (
        item["prototype_path"],
        item["route"],
        item["region_id"],
        item["interaction_id"],
        item["acceptance_id"],
    )


def selected_flow_ids(loop: dict, subflow: dict | None = None) -> set[str]:
    verification = subflow["verification"] if subflow else loop["routing"]["verification"]
    return set(verification.get("reused_flows", [])) | set(verification.get("new_flows", []))


def evidence_path_errors(root: Path, paths: list[str], label: str) -> list[str]:
    errors = []
    for value in paths:
        path = project_file(root, value)
        if path is None or not path.is_file():
            errors.append(f"{label} does not exist: {value}")
    return errors


def prototype_verification_errors(
    root: Path,
    loop: dict,
    flows: dict[str, dict],
    subflow: dict | None = None,
) -> list[str]:
    requires_prototype = prototype_is_required(loop, subflow)
    errors = []
    subflow_id = subflow["subflow_id"] if subflow else None
    ids = selected_flow_ids(loop, subflow)
    if requires_prototype and not ids:
        return [f"{subflow_id or loop['loop_id']}: prototype verification flow is not selected"]
    selected = []
    for flow_id in sorted(ids):
        flow = flows.get(flow_id)
        if not flow:
            errors.append(f"prototype verification flow is missing: {flow_id}")
            continue
        selected.append(flow)
        if requires_prototype and (flow.get("executor") != "ui" or not flow_requires_visual(flow)):
            errors.append(f"prototype verification flow is not visual UI automation: {flow_id}")
        errors.extend(flow_semantic_errors(root, flow))
    visual_selected = [flow for flow in selected if flow_requires_visual(flow)]
    if not requires_prototype and not visual_selected:
        return errors
    evidence_ids = ids if requires_prototype else {flow["flow_id"] for flow in visual_selected}
    if requires_prototype:
        matrix, matrix_errors = load_prototype_matrix(root, loop)
        errors.extend(matrix_errors)
        if matrix is None:
            return errors
        expected = matrix_keys(matrix, subflow_id)
    else:
        expected = {
            coverage_key(item)
            for flow in visual_selected
            for item in flow.get("coverage", [])
        }
    flow_coverage = {
        coverage_key(item)
        for flow in visual_selected
        for item in flow.get("coverage", [])
    }
    missing_flow = expected - flow_coverage
    if missing_flow:
        errors.append(f"prototype flow coverage is incomplete: {len(missing_flow)} required rows missing")

    evidence_file = loop_dir(root, loop["loop_id"]) / loop.get("files", {}).get("evidence", "evidence.yaml")
    evidence = load_yaml(evidence_file) if evidence_file.is_file() else {"runs": []}
    covered = set()
    for run in evidence.get("runs", []):
        if (
            run.get("flow_id") not in evidence_ids
            or run.get("subflow_id") != subflow_id
            or run.get("requirement_version") != loop["requirement_version"]
            or run.get("validity") != "active"
            or run.get("result") != "passed"
        ):
            continue
        visual = run.get("visual")
        if not visual or visual.get("result") != "passed":
            errors.append(f"evidence {run.get('evidence_id')}: valid visual result is missing")
            continue
        flow = flows[run["flow_id"]]
        if visual.get("viewport") != flow.get("visual_validation", {}).get("viewport"):
            errors.append(f"evidence {run.get('evidence_id')}: viewport differs from visual flow")
        reference_pages = {item["prototype_path"] for item in visual.get("references", [])}
        flow_rows = {coverage_key(item): set(item["automation_steps"]) for item in flow.get("coverage", [])}
        flow_expected_pages = {key[0] for key in expected & set(flow_rows)}
        if not flow_expected_pages.issubset(reference_pages):
            errors.append(f"evidence {run.get('evidence_id')}: page reference/implementation evidence is incomplete")
        for reference in visual.get("references", []):
            errors.extend(evidence_path_errors(
                root,
                [reference["reference_path"], reference["implementation_path"]],
                f"evidence {run.get('evidence_id')} visual artifact",
            ))
        for item in run.get("coverage", []):
            key = coverage_key(item)
            if item["automation_step"] not in flow_rows.get(key, set()):
                errors.append(f"evidence {run.get('evidence_id')}: coverage is not mapped to a declared automation step")
                continue
            errors.extend(evidence_path_errors(
                root, item["evidence_paths"], f"evidence {run.get('evidence_id')} coverage artifact"
            ))
            covered.add(key)
    missing_evidence = expected - covered
    if missing_evidence:
        errors.append(f"prototype evidence coverage is incomplete: {len(missing_evidence)} required rows missing")
    return errors


def prototype_preparation_errors(
    root: Path,
    loop: dict,
    subflow: dict | None = None,
) -> list[str]:
    if not prototype_is_required(loop, subflow):
        return []
    matrix, errors = load_prototype_matrix(root, loop)
    if errors or matrix is None:
        return errors
    if subflow is None:
        return errors
    actual = {
        (page["prototype_path"], page["route"])
        for page in matrix["pages"]
        if page.get("subflow_id") == subflow["subflow_id"]
    }
    declared = {
        (page["prototype_path"], page["route"])
        for page in subflow.get("prototype_pages", [])
    }
    if not actual:
        errors.append(f"subflow {subflow['subflow_id']}: prototype matrix has no owned pages")
    if declared and declared != actual:
        errors.append(f"subflow {subflow['subflow_id']}: prototype_pages do not match matrix ownership")
    return errors


def runtime_semantic_errors(root: Path, loops: list[dict], flows: dict[str, dict]) -> list[str]:
    errors = [
        error
        for flow in flows.values()
        for error in flow_semantic_errors(root, flow)
    ]
    prepared_states = {
        "developing", "ready_for_verification", "verifying", "orchestrating",
        "verified", "done",
    }
    for loop in loops:
        if loop.get("state") in prepared_states:
            errors.extend(prototype_preparation_errors(root, loop))
        if loop.get("state") in {"verified", "done"}:
            errors.extend(prototype_verification_errors(root, loop, flows))
        for subflow in loop.get("subflows", []):
            if subflow.get("state") in {
                "developing", "ready_for_verification", "verifying", "passed"
            }:
                errors.extend(prototype_preparation_errors(root, loop, subflow))
            if subflow.get("state") == "passed":
                errors.extend(prototype_verification_errors(root, loop, flows, subflow))
    return errors


def runtime_flows(root: Path) -> dict[str, dict]:
    return {
        flow["flow_id"]: flow
        for flow in map(load_yaml, (root / ".agentloop" / "flows").glob("*.yaml"))
    }


def loop_dir(root: Path, loop_id: str) -> Path:
    return root / ".agentloop" / "loops" / loop_id


def loop_path(root: Path, loop_id: str) -> Path:
    return loop_dir(root, loop_id) / "loop.yaml"


def load_loop(root: Path, loop_id: str) -> tuple[Path, dict]:
    path = loop_path(root, loop_id)
    if not path.is_file():
        raise ValueError(f"Loop not found: {loop_id}")
    return path, load_yaml(path)


def active_loops(root: Path) -> list[tuple[Path, dict]]:
    result = []
    for path in sorted((root / ".agentloop" / "loops").glob("*/loop.yaml")):
        loop = load_yaml(path)
        if loop.get("state") not in TERMINAL_STATES:
            result.append((path, loop))
    return result


@contextmanager
def loop_lock(root: Path, loop_id: str, actor: str):
    path = root / ".agentloop" / "locks" / f"{loop_id}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"actor": actor, "started_at": now()}) + "\n"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError(f"Loop is already locked: {path}") from error
    try:
        os.write(descriptor, payload.encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def next_loop_ids(root: Path, count: int) -> list[str]:
    date = datetime.now().astimezone().strftime("%Y%m%d")
    used = {
        int(match.group(1))
        for path in (root / ".agentloop" / "loops").glob(f"al-{date}-*/loop.yaml")
        if (match := re.match(rf"al-{date}-(\d{{3}})$", path.parent.name))
    }
    start = max(used, default=0) + 1
    if start + count > 1000:
        raise ValueError("daily Loop sequence exhausted")
    return [f"al-{date}-{value:03d}" for value in range(start, start + count)]


def gate(gate_id: str, status: str, mode: str, confidence: str | None = None) -> dict:
    value = {
        "gate_id": gate_id,
        "status": status,
        "mode": mode,
        "event_id": None,
        "subject_digest": None,
    }
    if confidence is not None:
        value["confidence"] = confidence
    if gate_id == "destructive_action":
        value["operation_digest"] = None
    return value


def base_loop(
    root: Path,
    loop_id: str,
    title: str,
    level: str,
    kind: str,
    parent_loop_id: str | None = None,
) -> dict:
    baseline = run_git(root, "rev-parse", "HEAD")
    branch = run_git(root, "branch", "--show-current") or "HEAD"
    dirty = bool(run_git(root, "status", "--porcelain"))
    main_flow = "quick-change" if level in {"trivial", "standard"} else "architecture"
    policy = {"trivial": "self_check", "standard": "targeted", "composite": "flow"}[level]
    files = {"work": "work.md"} if level == "trivial" else {
        "requirement": "requirement.md",
        "development": "development.md",
        "evidence": "evidence.yaml",
    }
    value = {
        "schema_version": 1,
        "loop_id": loop_id,
        "loop_kind": kind,
        "parent_loop_id": parent_loop_id,
        "title": title,
        "execution_profile": {
            "level": level,
            "status": "provisional",
            "reason": "根据原始请求形成的初始档位，需求确认前必须复核",
        },
        "state": "draft",
        "requirement_version": 1,
        "updated_at": now(),
        "owners": {
            "coordination": "loop-coordinator",
            "requirement": "requirement-agent",
            "development": "development-agent",
            "verification": "verification-agent",
        },
        "classification": {"primary_type": "待确认", "tags": []},
        "prototype": {
            "implementation_basis": False,
            "type": None,
            "fidelity": None,
            "pages": [],
        },
        "scope": {
            "claim": "active",
            "claimed_at": now(),
            "paths": [],
            "interfaces": [],
            "db_objects": [],
            "states": [],
        },
        "gates": {
            "requirement_confirmation": gate(
                "requirement_confirmation", "pending", "manual", "medium"
            ),
            "routing_confirmation": gate(
                "routing_confirmation", "not_required", "manual_on_low_confidence"
            ),
            "completion": gate("completion", "pending", "human_acceptance"),
            "destructive_action": gate(
                "destructive_action", "not_required", "always_manual"
            ),
        },
        "gate_events": [],
        "git": {
            "root": ".",
            "target_branch": branch,
            "branch": branch,
            "worktree": ".",
            "head_commit": baseline,
            "working_tree_status": "dirty" if dirty else "clean",
            "baseline_commit": baseline,
            "last_checkpoint_commit": None,
            "checkpoints": [],
            "integration": {
                "status": "pending",
                "base_commit": baseline,
                "head_commit": None,
                "merges": [],
                "post_merge_checks": [],
                "delivery_commit": None,
            },
        },
        "routing": {
            "status": "pending",
            "confidence": "medium",
            "decided_at": None,
            "decided_by": None,
            "development": {
                "main_flow": main_flow,
                "reason": "待需求确认后根据主要不确定性决定",
                "supporting_flows": [],
                "required_outputs": [],
            },
            "verification": {
                "policy": policy,
                "reason": "初始策略，需求确认和风险检查后重新决定",
                "reused_flows": [],
                "new_flows": [],
                "executors": {},
            },
        },
        "files": files,
        "execution": {
            "execution_id": None,
            "subflow_id": None,
            "step_id": None,
            "status": None,
            "operation": None,
            "inputs": [],
            "expected_outputs": [],
            "check": None,
            "idempotency": None,
            "attempt": 0,
            "max_attempts": 3,
            "last_error": None,
        },
        "verification_control": (
            {"failure_roundtrips": 0, "max_failure_roundtrips": 3}
            if level == "standard"
            else None
        ),
        "subflows": [],
        "child_loops": [],
        "integration_verification": {
            "required": False,
            "reason": "初始值；复合或 epic 进入 orchestrating 前必须明确决定",
            "decided_by": "loop-coordinator",
            "decided_at": now(),
            "dependencies": [],
            "state": "not_required" if level != "composite" else "pending",
            "handoff": {},
            "failure_handoff": {},
            "reused_flows": [],
            "new_flows": [],
            "executors": {},
            "verification_failure_roundtrips": 0,
        },
        "verification_handoff": None,
        "failure_handoff": None,
        "artifacts": [],
        "blocked": None,
        "transitions": [
            {
                "from": None,
                "to": "draft",
                "subflow_id": None,
                "actor": "loop-coordinator",
                "at": now(),
                "requirement_version": 1,
                "git_commit": baseline,
                "evidence": [],
                "reason": "初始化 AgentLoop",
            }
        ],
    }
    return value


def add_subflows(loop: dict, titles: list[str]) -> None:
    for index, title in enumerate(titles, 1):
        loop["subflows"].append(
            {
                "subflow_id": f"sf-{index:02d}-{slug(title)[:24] or 'slice'}",
                "title": title,
                "required": True,
                "acceptance_ids": [f"AC-{index:02d}"],
                "deliverable": title,
                "requirement_version": 1,
                "state": "pending",
                "state_reason": None,
                "skip_reason": None,
                "main_flow": "quick-change",
                "dependencies": [],
                "scope": {
                    "claim": "active",
                    "claimed_at": now(),
                    "paths": [],
                    "interfaces": [],
                    "db_objects": [],
                    "states": [],
                },
                "git": {},
                "verification": {
                    "policy": "targeted",
                    "reason": "待切片准备时决定",
                    "reused_flows": [],
                    "new_flows": [],
                    "executors": {},
                },
                "verification_handoff": None,
                "failure_handoff": None,
                "verification_failure_roundtrips": 0,
            }
        )


def add_child_refs(parent: dict, children: list[dict]) -> None:
    for index, child in enumerate(children, 1):
        parent["child_loops"].append(
            {
                "loop_id": child["loop_id"],
                "required": True,
                "acceptance_ids": [f"AC-{index:02d}"],
                "deliverable": child["title"],
                "requirement_version": 1,
                "dependencies": [],
                "repository_id": "current",
                "project_root": ".",
                "loop_file": f".agentloop/loops/{child['loop_id']}/loop.yaml",
                "loop_uri": None,
                "skip_reason": None,
                "scope": {"paths": []},
            }
        )


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def write_loop_files(root: Path, loop: dict) -> None:
    directory = loop_dir(root, loop["loop_id"])
    directory.mkdir(parents=True, exist_ok=False)
    if loop["execution_profile"]["level"] == "trivial":
        (directory / "work.md").write_text(
            f"# {loop['title']}\n\n"
            "## 需求、范围与验收\n\n"
            "## 事实、分类与自动确认依据\n\n"
            "## 修改位置与不变行为\n\n"
            "## 实现、开发自检与验证结论\n"
        )
    else:
        (directory / "requirement.md").write_text(
            f"# {loop['title']}\n\n"
            "## 原始需求与事实\n\n## 用户、场景与目标\n\n"
            "## 范围、非目标、规则与约束\n\n## 验收标准\n\n"
            "## 分类与复杂度\n\n## 需求原型决定与引用\n\n"
            "## 未解决问题\n\n## 确认记录\n"
        )
        (directory / "development.md").write_text(
            "# 开发记录\n\n## 输入与需求版本\n\n## 主开发流程及依据\n\n"
            "## 现有系统调查\n\n## 编码前产物及检查\n\n## 子流程与依赖\n\n"
            "## 实现和修改文件\n\n## 开发自检\n\n## 测试交接\n"
        )
    errors = schema_validator("loop.schema.json").iter_errors(loop)
    first = next(errors, None)
    if first:
        shutil.rmtree(directory)
        raise ValueError(f"generated Loop invalid at {first.json_path}: {first.message}")
    atomic_yaml(directory / "loop.yaml", loop)


def cmd_init(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    baseline = run_git(root, "rev-parse", "HEAD")
    if not baseline:
        raise ValueError("Git repository has no baseline commit")
    control = root / ".agentloop"
    (control / "locks").mkdir(parents=True, exist_ok=True)
    (control / "loops").mkdir(parents=True, exist_ok=True)
    (control / "flows").mkdir(parents=True, exist_ok=True)
    if not (control / "project.yaml").exists():
        project = load_yaml(EXAMPLE_ROOT / "project.yaml")
        project["project_id"] = slug(root.name) or "project"
        project["paths"]["source"] = [
            name for name in ("src", "app", "lib") if (root / name).exists()
        ]
        project["paths"]["tests"] = [
            name for name in ("tests", "test", "spec") if (root / name).exists()
        ]
        atomic_yaml(control / "project.yaml", project)
    shutil.copytree(SCHEMA_ROOT, control / "schemas", dirs_exist_ok=True)
    shutil.copytree(EXAMPLE_ROOT, control / "examples", dirs_exist_ok=True)
    gitignore = root / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if ".agentloop/locks/" not in existing.splitlines():
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        gitignore.write_text(existing + prefix + ".agentloop/locks/\n")

    child_titles = args.child or []
    if args.kind == "epic" and not child_titles:
        raise ValueError("epic initialization requires at least one --child")
    if args.level == "composite" and args.kind == "delivery" and not args.subflow:
        raise ValueError("composite delivery initialization requires at least one --subflow")
    level = "composite" if args.kind == "epic" else args.level
    ids = next_loop_ids(root, 1 + len(child_titles))
    parent = base_loop(root, ids[0], args.title, level, args.kind)
    children = [
        base_loop(root, loop_id, title, "standard", "delivery", parent["loop_id"])
        for loop_id, title in zip(ids[1:], child_titles)
    ]
    if args.kind == "epic":
        add_child_refs(parent, children)
    elif level == "composite":
        add_subflows(parent, args.subflow)
    for child in children:
        write_loop_files(root, child)
    write_loop_files(root, parent)
    print(parent["loop_id"])
    for child in children:
        print(child["loop_id"])


def cmd_validate(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    control = root / ".agentloop"
    cases = []
    if (control / "project.yaml").exists():
        cases.append((control / "project.yaml", "project.schema.json"))
    loop_paths = list((control / "loops").glob("*/loop.yaml"))
    flow_paths = list((control / "flows").glob("*.yaml"))
    cases.extend((path, "loop.schema.json") for path in loop_paths)
    cases.extend((path, "flow.schema.json") for path in flow_paths)
    cases.extend((path, "evidence.schema.json") for path in (control / "loops").glob("*/evidence.yaml"))
    errors = [error for path, schema in cases for error in validate_file(path, schema)]
    if not errors:
        loops = [load_yaml(path) for path in loop_paths]
        flows = {flow["flow_id"]: flow for flow in map(load_yaml, flow_paths)}
        errors.extend(runtime_semantic_errors(root, loops, flows))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"passed: {len(cases)} AgentLoop files")


def cmd_status(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    loops = active_loops(root)
    if not loops:
        print("no active Loops")
        return
    for _, loop in loops:
        gate_states = ",".join(
            f"{name}={value['status']}"
            for name, value in loop["gates"].items()
            if value["status"] not in {"approved", "not_required"}
        )
        print(
            f"{loop['loop_id']}\t{loop['state']}\t"
            f"{loop['execution_profile']['level']}\t{gate_states or '-'}\t{loop['title']}"
        )


def cmd_route(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    path, loop = load_loop(root, args.loop_id)
    with loop_lock(root, args.loop_id, args.actor):
        loop["routing"].update(
            {
                "status": "decided",
                "confidence": args.confidence,
                "decided_at": now(),
                "decided_by": args.actor,
            }
        )
        loop["routing"]["development"].update(
            {
                "main_flow": args.main_flow,
                "reason": args.reason,
                "supporting_flows": args.supporting_flow or [],
                "required_outputs": args.required_output or [],
            }
        )
        if args.main_flow == "product-prototype":
            loop["files"]["prototype_matrix"] = "prototype-implementation-matrix.yaml"
            if "prototype-implementation-matrix" not in loop["routing"]["development"]["required_outputs"]:
                loop["routing"]["development"]["required_outputs"].append("prototype-implementation-matrix")
        loop["routing"]["verification"].update(
            {
                "policy": args.verification,
                "reason": args.verification_reason,
            }
        )
        if args.confidence == "low":
            loop["gates"]["routing_confirmation"]["status"] = "pending"
        elif loop["gates"]["routing_confirmation"]["status"] == "pending":
            loop["gates"]["routing_confirmation"]["status"] = "not_required"
        loop["updated_at"] = now()
        errors = list(schema_validator("loop.schema.json").iter_errors(loop))
        if errors:
            raise ValueError(f"routing invalid at {errors[0].json_path}: {errors[0].message}")
        atomic_yaml(path, loop)


def manifest_digest(root: Path, subjects: list[str]) -> tuple[list[dict], str]:
    records = []
    payload = bytearray()
    for subject in sorted(subjects):
        path = (root / subject).resolve()
        if root not in path.parents:
            raise ValueError(f"Gate subject escapes project root: {subject}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(root).as_posix()
        records.append({"path": relative, "sha256": digest})
        payload.extend(relative.encode() + b"\0" + digest.encode() + b"\n")
    return records, hashlib.sha256(payload).hexdigest()


def recover_prototype_rejection(root: Path, loop: dict, args: argparse.Namespace) -> None:
    if (
        args.gate_id != "completion"
        or args.decision != "rejected"
        or loop.get("state") != "verified"
        or (
            not prototype_is_required(loop)
            and not any(prototype_is_required(loop, item) for item in loop.get("subflows", []))
        )
    ):
        return
    if not args.reason or not args.affected_page:
        raise ValueError("prototype completion rejection requires --reason and --affected-page")
    matrix, errors = load_prototype_matrix(root, loop)
    if errors or matrix is None:
        raise ValueError("; ".join(errors))
    affected = set(args.affected_page)
    pages = [
        page for page in matrix["pages"]
        if page["prototype_path"] in affected or page["route"] in affected
    ]
    if not pages:
        raise ValueError("affected pages do not match the prototype implementation matrix")
    affected_paths = {page["prototype_path"] for page in pages}
    affected_routes = {page["route"] for page in pages}
    evidence_file = loop_dir(root, loop["loop_id"]) / loop.get("files", {}).get("evidence", "evidence.yaml")
    evidence = load_yaml(evidence_file) if evidence_file.is_file() else {"runs": []}
    stale_ids = []
    for run in evidence.get("runs", []):
        if (
            run.get("executor") != "ui"
            or run.get("requirement_version") != loop["requirement_version"]
            or run.get("validity") != "active"
        ):
            continue
        run_paths = {item.get("prototype_path") for item in run.get("coverage", [])}
        run_paths.update(
            item.get("prototype_path") for item in run.get("visual", {}).get("references", [])
        )
        run_routes = {item.get("route") for item in run.get("coverage", [])}
        if not run_paths or run_paths & affected_paths or run_routes & affected_routes:
            run["validity"] = "stale"
            stale_ids.append(run["evidence_id"])
    if evidence_file.is_file():
        atomic_yaml(evidence_file, evidence)

    failure = {
        "reason": args.reason,
        "affected_pages": sorted(affected_paths),
        "affected_routes": sorted(affected_routes),
        "stale_evidence": stale_ids,
        "revalidation_scope": args.revalidation_scope or sorted(affected),
        "at": now(),
    }
    previous = loop["state"]
    if loop.get("subflows"):
        affected_subflows = {page.get("subflow_id") for page in pages}
        affected_subflows.discard(None)
        if not affected_subflows:
            raise ValueError("affected prototype pages have no subflow owner")
        for subflow in loop["subflows"]:
            if subflow["subflow_id"] not in affected_subflows:
                continue
            subflow["state"] = "development_preparing"
            subflow["state_reason"] = args.reason
            subflow["failure_handoff"] = failure
            subflow["verification_failure_roundtrips"] += 1
        loop["state"] = "orchestrating"
    else:
        loop["state"] = "development_preparing"
        loop["failure_handoff"] = failure
        loop["verification_control"]["failure_roundtrips"] += 1
    loop["transitions"].append({
        "from": previous,
        "to": loop["state"],
        "subflow_id": None,
        "actor": "loop-coordinator",
        "at": now(),
        "requirement_version": loop["requirement_version"],
        "git_commit": run_git(root, "rev-parse", "HEAD"),
        "evidence": stale_ids,
        "reason": f"completion Gate rejected prototype fidelity: {args.reason}",
    })


def cmd_gate(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    path, loop = load_loop(root, args.loop_id)
    if args.gate_id not in loop["gates"]:
        raise ValueError(f"unknown Gate: {args.gate_id}")
    if not args.subject:
        filename = loop["files"].get("requirement") or loop["files"].get("work")
        args.subject = [str(loop_dir(root, args.loop_id).joinpath(filename).relative_to(root))]
    subjects, digest = manifest_digest(root, args.subject)
    with loop_lock(root, args.loop_id, args.actor):
        event_id = f"gate-{len(loop['gate_events']) + 1:03d}"
        event = {
            "event_id": event_id,
            "gate_id": args.gate_id,
            "decision": args.decision,
            "actor": args.actor,
            "source": args.source,
            "source_event_id": args.source_event_id,
            "requirement_version": loop["requirement_version"],
            "digest_algorithm": "sha256-manifest-v1",
            "subject_files": subjects,
            "artifact_digest": digest,
            "at": now(),
            "reason": args.reason,
            "affected_pages": args.affected_page or [],
            "revalidation_scope": args.revalidation_scope or [],
        }
        recover_prototype_rejection(root, loop, args)
        loop["gate_events"].append(event)
        current = loop["gates"][args.gate_id]
        current["status"] = args.decision
        current["event_id"] = event_id
        current["subject_digest"] = digest
        loop["updated_at"] = now()
        errors = list(schema_validator("loop.schema.json").iter_errors(loop))
        if errors:
            raise ValueError(f"Gate update invalid at {errors[0].json_path}: {errors[0].message}")
        atomic_yaml(path, loop)
    print(event_id)


def active_passed_evidence(root: Path, loop: dict) -> bool:
    evidence_path = loop_dir(root, loop["loop_id"]) / "evidence.yaml"
    if not evidence_path.exists():
        return False
    evidence = load_yaml(evidence_path)
    return any(
        run.get("requirement_version") == loop["requirement_version"]
        and run.get("validity") == "active"
        and run.get("result") == "passed"
        for run in evidence.get("runs", [])
    )


def aggregation_errors(root: Path, loop: dict) -> list[str]:
    errors = []
    flows = runtime_flows(root)
    if loop["loop_kind"] == "epic":
        for child in loop["child_loops"]:
            if not child["required"] and child.get("skip_reason"):
                continue
            child_path = root / child["loop_file"] if child.get("loop_file") else None
            if not child_path or not child_path.exists():
                errors.append(f"child Loop unavailable: {child['loop_id']}")
                continue
            child_loop = load_yaml(child_path)
            if child_loop.get("parent_loop_id") != loop["loop_id"]:
                errors.append(f"child parent mismatch: {child['loop_id']}")
            if child_loop.get("state") != "done":
                errors.append(f"child not done: {child['loop_id']}")
            else:
                child_root = (root / child["project_root"]).resolve()
                errors.extend(prototype_verification_errors(
                    child_root, child_loop, runtime_flows(child_root)
                ))
    else:
        for subflow in loop["subflows"]:
            if subflow["state"] == "skipped" and subflow.get("skip_reason"):
                continue
            if subflow["required"] and subflow["state"] != "passed":
                errors.append(f"subflow not passed: {subflow['subflow_id']}")
            if subflow["state"] == "passed":
                errors.extend(prototype_verification_errors(root, loop, flows, subflow))
    if loop["git"]["integration"]["status"] != "verified":
        errors.append("git.integration.status is not verified")
    integration = loop["integration_verification"]
    if integration["state"] not in {"not_required", "passed"}:
        errors.append("integration_verification is not complete")
    return errors


def transition_errors(root: Path, loop: dict, target: str, evidence: list[str]) -> list[str]:
    current = loop["state"]
    allowed = set(TRANSITIONS.get(current, set()))
    if current == "blocked" and loop.get("blocked", {}).get("resume_state"):
        allowed.add(loop["blocked"]["resume_state"])
    errors = [] if target in allowed else [f"illegal transition: {current} -> {target}"]
    if target == "awaiting_requirement_confirmation":
        errors.extend(prototype_declaration_errors(root, loop))
    if target == "ready_for_development":
        if loop["gates"]["requirement_confirmation"]["status"] != "approved":
            errors.append("requirement_confirmation Gate is not approved")
        if loop["execution_profile"]["status"] != "confirmed":
            errors.append("execution_profile is not confirmed")
    if target in {"development_preparing", "orchestrating"}:
        if loop["routing"]["status"] != "decided":
            errors.append("routing is not decided")
        if not loop["git"]["baseline_commit"]:
            errors.append("Git baseline is missing")
        if loop["gates"]["routing_confirmation"]["status"] == "pending":
            errors.append("routing_confirmation Gate is pending")
    if target == "developing":
        errors.extend(prototype_preparation_errors(root, loop))
    if target == "orchestrating":
        if loop["execution_profile"]["level"] != "composite":
            errors.append("only composite/epic Loops enter orchestrating")
        if loop["loop_kind"] == "epic" and not loop["child_loops"]:
            errors.append("epic has no child Loops")
        if loop["loop_kind"] == "delivery" and not loop["subflows"]:
            errors.append("composite delivery has no subflows")
    if target == "ready_for_verification":
        if loop["routing"]["verification"]["policy"] == "self_check":
            errors.append("self_check does not enter ready_for_verification")
        if not loop.get("verification_handoff"):
            errors.append("verification_handoff is missing")
        if not evidence:
            errors.append("development evidence/checkpoint reference is missing")
    if target == "verified":
        if current == "developing":
            if loop["execution_profile"]["level"] != "trivial":
                errors.append("developing -> verified is only allowed for trivial")
            if loop["routing"]["development"]["main_flow"] != "quick-change":
                errors.append("trivial self_check requires quick-change")
            if loop["routing"]["verification"]["policy"] != "self_check":
                errors.append("developing -> verified requires self_check")
            if not evidence:
                errors.append("self_check result reference is missing")
        elif current == "verifying" and not active_passed_evidence(root, loop):
            errors.append("no active passed evidence for the current requirement")
        if current == "verifying":
            errors.extend(prototype_verification_errors(root, loop, runtime_flows(root)))
        elif current == "orchestrating":
            errors.extend(aggregation_errors(root, loop))
    if target == "done":
        if loop["gates"]["completion"]["status"] != "approved":
            errors.append("completion Gate is not approved")
        if loop.get("blocked"):
            errors.append("Loop still has blocked metadata")
        if current != "verified":
            errors.append("Loop must be verified before done")
    if target == "blocked" and not loop.get("_pending_block"):
        errors.append("use --resume-state and --unblock-condition when blocking")
    return errors


def cmd_transition(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    path, loop = load_loop(root, args.loop_id)
    if args.to == "blocked":
        if not args.resume_state or not args.unblock_condition:
            raise ValueError("blocked transition requires --resume-state and --unblock-condition")
        loop["_pending_block"] = True
    errors = transition_errors(root, loop, args.to, args.evidence or [])
    loop.pop("_pending_block", None)
    if errors:
        raise ValueError("; ".join(errors))
    with loop_lock(root, args.loop_id, args.actor):
        previous = loop["state"]
        if previous == "blocked":
            loop["blocked"] = None
        if args.to == "blocked":
            loop["blocked"] = {
                "reason": args.reason,
                "owner": args.actor,
                "unblock_condition": args.unblock_condition,
                "resume_state": args.resume_state,
            }
        if args.to == "done":
            loop["scope"]["claim"] = "released"
        loop["state"] = args.to
        loop["updated_at"] = now()
        loop["transitions"].append(
            {
                "from": previous,
                "to": args.to,
                "subflow_id": args.subflow_id,
                "actor": args.actor,
                "at": now(),
                "requirement_version": loop["requirement_version"],
                "git_commit": args.git_commit or run_git(root, "rev-parse", "HEAD"),
                "evidence": args.evidence or [],
                "reason": args.reason,
            }
        )
        errors = list(schema_validator("loop.schema.json").iter_errors(loop))
        if errors:
            raise ValueError(f"transition invalid at {errors[0].json_path}: {errors[0].message}")
        atomic_yaml(path, loop)


def cmd_evidence(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    _, loop = load_loop(root, args.loop_id)
    command = json.loads(args.command_json)
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("--command-json must be a non-empty JSON string array")
    coverage = json.loads(args.coverage_json) if args.coverage_json else []
    visual = json.loads(args.visual_json) if args.visual_json else None
    if not isinstance(coverage, list):
        raise ValueError("--coverage-json must be a JSON array")
    if visual is not None and not isinstance(visual, dict):
        raise ValueError("--visual-json must be a JSON object")
    path = loop_dir(root, args.loop_id) / "evidence.yaml"
    evidence = load_yaml(path) if path.exists() else {
        "schema_version": 1,
        "loop_id": args.loop_id,
        "runs": [],
    }
    index = len(evidence["runs"]) + 1
    start = args.started_at or now()
    end = args.ended_at or now()
    run = {
        "evidence_id": f"{args.loop_id}-evidence-{index:02d}",
        "flow_id": args.flow_id,
        "check_id": args.check_id,
        "subflow_id": args.subflow_id,
        "requirement_version": loop["requirement_version"],
        "executor": args.executor,
        "command": command,
        "result": args.result,
        "exit_code": args.exit_code,
        "counts": {
            "passed": 1 if args.result == "passed" else 0,
            "failed": 1 if args.result == "failed" else 0,
            "skipped": 0,
        },
        "validity": "active",
        "code_commit": args.code_commit or run_git(root, "rev-parse", "HEAD"),
        "environment": args.environment,
        "started_at": start,
        "ended_at": end,
        "duration_ms": args.duration_ms,
        "stdout_path": args.stdout_path,
        "stderr_path": args.stderr_path,
        "coverage": coverage,
        "artifacts": [],
    }
    if visual is not None:
        run["visual"] = visual
    evidence["runs"].append(run)
    errors = list(schema_validator("evidence.schema.json").iter_errors(evidence))
    if errors:
        raise ValueError(f"evidence invalid at {errors[0].json_path}: {errors[0].message}")
    atomic_yaml(path, evidence)
    print(run["evidence_id"])


def patch_paths(command: str) -> list[str]:
    return re.findall(r"(?m)^\*\*\* (?:Add|Update|Delete) File: (.+)$", command)


def path_in_scope(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or path.startswith(pattern.rstrip("*")) for pattern in patterns)


def read_hook_event() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}


def emit(value: dict | str) -> None:
    print(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value)


def cmd_hook(args: argparse.Namespace) -> None:
    event = read_hook_event()
    try:
        root = git_root(Path(event.get("cwd", ".")).resolve())
    except ValueError:
        return
    loops = active_loops(root)
    if args.event == "session-start":
        if loops:
            summary = ", ".join(
                f"{loop['loop_id']}:{loop['state']}" for _, loop in loops
            )
            emit(
                f"AgentLoop plugin found active Loops: {summary}. "
                "Invoke $agentloop, load loop.yaml as the state source, and use "
                f"`python3 {Path(__file__).resolve()} status` before acting."
            )
        return
    if args.event == "pre-tool":
        command = str(event.get("tool_input", {}).get("command", ""))
        changed = patch_paths(command)
        if not changed:
            return
        if all(
            path.startswith(
                (".agentloop/", "agentloop/", "plugins/development-process-agentloop/")
            )
            for path in changed
        ):
            return
        blocked = [
            loop for _, loop in loops if loop["state"] not in EDITABLE_STATES
        ]
        if blocked:
            states = ", ".join(f"{loop['loop_id']}:{loop['state']}" for loop in blocked)
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"AgentLoop Gate blocks project edits while {states}. "
                            "Advance requirement and routing Gates first."
                        ),
                    }
                }
            )
            return
        scoped = [loop for _, loop in loops if loop["scope"]["paths"]]
        if scoped and not all(
            any(path_in_scope(path, loop["scope"]["paths"]) for loop in scoped)
            for path in changed
        ):
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "One or more edited paths are outside all active AgentLoop scope.paths."
                        ),
                    }
                }
            )
        return
    if args.event == "stop":
        actionable = [
            loop
            for _, loop in loops
            if loop["state"] not in {"blocked", "awaiting_requirement_confirmation"}
        ]
        if actionable and not event.get("stop_hook_active"):
            states = ", ".join(f"{loop['loop_id']}:{loop['state']}" for loop in actionable)
            emit(
                {
                    "decision": "block",
                    "reason": (
                        f"AgentLoop remains non-terminal ({states}). Validate state and evidence, "
                        "perform the next legal transition, or persist an explicit blocked state."
                    ),
                }
            )


def cmd_doctor(_: argparse.Namespace) -> None:
    required = [
        PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
        PLUGIN_ROOT / "skills" / "agentloop" / "SKILL.md",
        PLUGIN_ROOT / "hooks" / "hooks.json",
        REFERENCE_ROOT / "README.md",
        SCHEMA_ROOT / "loop.schema.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError("missing plugin assets: " + ", ".join(missing))
    for name in ("project", "loop", "flow", "evidence", "prototype-matrix"):
        schema_validator(f"{name}.schema.json")
    print("passed: AgentLoop plugin assets and schemas")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="agentloop")
    value.add_argument("--root", default=".")
    commands = value.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--title", required=True)
    init.add_argument("--level", choices=["trivial", "standard", "composite"], default="standard")
    init.add_argument("--kind", choices=["delivery", "epic"], default="delivery")
    init.add_argument("--subflow", action="append")
    init.add_argument("--child", action="append")
    init.set_defaults(func=cmd_init)

    validate = commands.add_parser("validate")
    validate.set_defaults(func=cmd_validate)
    status = commands.add_parser("status")
    status.set_defaults(func=cmd_status)

    route = commands.add_parser("route")
    route.add_argument("loop_id")
    route.add_argument("--actor", required=True)
    route.add_argument("--confidence", choices=["low", "medium", "high"], required=True)
    route.add_argument("--main-flow", choices=[
        "quick-change", "product-prototype", "business-process", "data-contract",
        "domain-model", "architecture", "root-cause", "migration-compatibility",
        "technical-validation",
    ], required=True)
    route.add_argument("--reason", required=True)
    route.add_argument("--supporting-flow", action="append")
    route.add_argument("--required-output", action="append")
    route.add_argument("--verification", choices=["self_check", "targeted", "flow"], required=True)
    route.add_argument("--verification-reason", required=True)
    route.set_defaults(func=cmd_route)

    gate_parser = commands.add_parser("gate")
    gate_parser.add_argument("loop_id")
    gate_parser.add_argument("gate_id")
    gate_parser.add_argument("--decision", choices=["approved", "rejected"], required=True)
    gate_parser.add_argument("--actor", required=True)
    gate_parser.add_argument("--source", required=True)
    gate_parser.add_argument("--source-event-id", required=True)
    gate_parser.add_argument("--subject", action="append")
    gate_parser.add_argument("--reason")
    gate_parser.add_argument("--affected-page", action="append")
    gate_parser.add_argument("--revalidation-scope", action="append")
    gate_parser.set_defaults(func=cmd_gate)

    transition = commands.add_parser("transition")
    transition.add_argument("loop_id")
    transition.add_argument("to")
    transition.add_argument("--actor", required=True)
    transition.add_argument("--reason", required=True)
    transition.add_argument("--evidence", action="append")
    transition.add_argument("--git-commit")
    transition.add_argument("--subflow-id")
    transition.add_argument("--resume-state")
    transition.add_argument("--unblock-condition")
    transition.set_defaults(func=cmd_transition)

    evidence = commands.add_parser("evidence")
    evidence.add_argument("loop_id")
    identity = evidence.add_mutually_exclusive_group(required=True)
    identity.add_argument("--flow-id")
    identity.add_argument("--check-id")
    evidence.add_argument("--subflow-id")
    evidence.add_argument("--executor", choices=["code", "ui", "command"], required=True)
    evidence.add_argument("--result", choices=["passed", "failed", "blocked"], required=True)
    evidence.add_argument("--command-json", required=True)
    evidence.add_argument("--exit-code", type=int, required=True)
    evidence.add_argument("--duration-ms", type=int, default=0)
    evidence.add_argument("--environment", default="local")
    evidence.add_argument("--code-commit")
    evidence.add_argument("--started-at")
    evidence.add_argument("--ended-at")
    evidence.add_argument("--stdout-path")
    evidence.add_argument("--stderr-path")
    evidence.add_argument("--coverage-json")
    evidence.add_argument("--visual-json")
    evidence.set_defaults(func=cmd_evidence)

    hook = commands.add_parser("hook")
    hook.add_argument("event", choices=["session-start", "pre-tool", "stop"])
    hook.set_defaults(func=cmd_hook)
    doctor = commands.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)
    return value


def main() -> None:
    args = parser().parse_args()
    try:
        args.func(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
