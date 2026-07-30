#!/usr/bin/env python3
"""Repository-backed control plane for the AgentLoop Codex plugin."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
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
SUBFLOW_TRANSITIONS = {
    "pending": {"development_preparing", "skipped", "blocked"},
    "development_preparing": {"developing", "blocked"},
    "developing": {"ready_for_verification", "failed", "blocked"},
    "ready_for_verification": {"verifying", "developing", "blocked"},
    "verifying": {"passed", "failed", "developing", "blocked"},
    "failed": {"developing", "blocked"},
    "blocked": {"development_preparing", "developing", "verifying"},
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


def controlled_payload(root: Path, loop: dict) -> dict:
    evidence_path = loop_dir(root, loop["loop_id"]) / loop.get("files", {}).get("evidence", "evidence.yaml")
    evidence = load_yaml(evidence_path) if evidence_path.is_file() else {"runs": []}
    return {
        "state": loop["state"],
        "gates": {
            key: {
                "status": value["status"],
                "event_id": value.get("event_id"),
                "subject_digest": value.get("subject_digest"),
            }
            for key, value in loop["gates"].items()
        },
        "subflows": {
            item["subflow_id"]: item["state"] for item in loop.get("subflows", [])
        },
        "evidence_validity": {
            item["evidence_id"]: item["validity"] for item in evidence.get("runs", [])
        },
    }


def control_snapshot_path(root: Path, loop_id: str) -> Path:
    return root / ".agentloop" / "control" / f"{loop_id}.json"


def write_control_snapshot(root: Path, loop: dict) -> None:
    payload = controlled_payload(root, loop)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    path = control_snapshot_path(root, loop["loop_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "algorithm": "sha256-control-v1",
        "digest": hashlib.sha256(encoded).hexdigest(),
        "payload": payload,
    }, ensure_ascii=False, indent=2) + "\n")


def verify_control_snapshot(root: Path, loop_path_value: Path, loop: dict) -> None:
    path = control_snapshot_path(root, loop["loop_id"])
    if not path.is_file():
        write_control_snapshot(root, loop)
        return
    snapshot = json.loads(path.read_text())
    expected = snapshot["payload"]
    encoded = json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()
    if snapshot.get("digest") != hashlib.sha256(encoded).hexdigest():
        raise ValueError(f"control snapshot is corrupt: {path}")
    actual = controlled_payload(root, loop)
    if actual == expected:
        return
    loop["state"] = expected["state"]
    for key, value in expected["gates"].items():
        loop["gates"][key].update(value)
    states = expected["subflows"]
    for subflow in loop.get("subflows", []):
        if subflow["subflow_id"] in states:
            subflow["state"] = states[subflow["subflow_id"]]
    atomic_yaml(loop_path_value, loop)
    evidence_path = loop_dir(root, loop["loop_id"]) / loop.get("files", {}).get("evidence", "evidence.yaml")
    if evidence_path.is_file():
        evidence = load_yaml(evidence_path)
        validities = expected["evidence_validity"]
        for run in evidence.get("runs", []):
            if run["evidence_id"] in validities:
                run["validity"] = validities[run["evidence_id"]]
        atomic_yaml(evidence_path, evidence)
    raise ValueError("unauthorized state/Gate/subflow/evidence modification detected and restored")


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


def integration_data_declaration_errors(loop: dict) -> list[str]:
    if "integration_data" not in loop:
        return ["integration_data decision must be explicitly declared before requirement confirmation"]
    return []


def integration_data_verification_errors(
    root: Path,
    loop: dict,
    flows: dict[str, dict],
) -> list[str]:
    declaration = loop.get("integration_data")
    if not declaration or not declaration.get("required"):
        return []
    flow_id = declaration["verification_flow_id"]
    flow = flows.get(flow_id)
    if not flow:
        return [f"integration data verification flow is missing: {flow_id}"]
    errors = flow_semantic_errors(root, flow)
    if flow.get("executor") != "ui":
        errors.append(f"integration data flow must use the UI executor: {flow_id}")
    if "data_lineage" not in flow.get("checks", []):
        errors.append(f"integration data flow does not check data_lineage: {flow_id}")
    evidence_file = loop_dir(root, loop["loop_id"]) / loop.get("files", {}).get("evidence", "evidence.yaml")
    evidence = load_yaml(evidence_file) if evidence_file.is_file() else {"runs": []}
    candidates = [
        run for run in evidence.get("runs", [])
        if run.get("flow_id") == flow_id
        and run.get("subflow_id") is None
        and run.get("requirement_version") == loop["requirement_version"]
        and run.get("validity") == "active"
        and run.get("result") == "passed"
    ]
    if not candidates:
        return errors + ["no active passed integration data evidence for the current requirement"]
    candidate_errors = []
    for run in candidates:
        run_errors = []
        lineage = run.get("data_lineage")
        if not lineage:
            candidate_errors.append(f"evidence {run.get('evidence_id')}: data_lineage is missing")
            continue
        sentinel = lineage["sentinel"]
        observed = [
            lineage["database"]["observed_sentinel"],
            lineage["backend"]["observed_sentinel"],
            lineage["frontend"]["observed_sentinel"],
        ]
        if any(value != sentinel for value in observed):
            candidate_errors.append(f"evidence {run.get('evidence_id')}: database/API/UI sentinel mismatch")
            continue
        expected = (
            ("database objects", set(declaration["database_objects"]), set(lineage["database"]["objects"])),
            ("backend endpoints", set(declaration["backend_endpoints"]), set(lineage["backend"]["endpoints"])),
            ("frontend routes", set(declaration["frontend_routes"]), set(lineage["frontend"]["routes"])),
        )
        missing = [label for label, wanted, actual in expected if not wanted.issubset(actual)]
        if missing:
            candidate_errors.append(f"evidence {run.get('evidence_id')}: integration data coverage is incomplete: {', '.join(missing)}")
            continue
        for layer in ("database", "backend", "frontend"):
            run_errors.extend(evidence_path_errors(
                root,
                lineage[layer]["evidence_paths"],
                f"evidence {run.get('evidence_id')} {layer} artifact",
            ))
        if not run_errors:
            return errors
        candidate_errors.extend(run_errors)
    return errors + candidate_errors


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


def openapi_operation_ids(root: Path, values: list[str]) -> tuple[set[str], list[str]]:
    operations = set()
    errors = []
    for value in values:
        path = project_file(root, value)
        if path is None or not path.is_file():
            errors.append(f"API contract does not exist: {value}")
            continue
        try:
            document = load_yaml(path)
        except Exception as error:
            errors.append(f"API contract cannot be parsed: {value}: {error}")
            continue
        if not (document.get("openapi") or document.get("swagger")):
            errors.append(f"API contract is not OpenAPI: {value}")
            continue
        for methods in document.get("paths", {}).values():
            if not isinstance(methods, dict):
                continue
            for operation in methods.values():
                if isinstance(operation, dict) and operation.get("operationId"):
                    operations.add(operation["operationId"])
    return operations, errors


def prototype_business_preparation_errors(
    root: Path,
    loop: dict,
    subflow: dict | None = None,
) -> list[str]:
    if not prototype_is_required(loop, subflow):
        return []
    matrix, errors = load_prototype_matrix(root, loop)
    if matrix is None:
        return errors
    subflow_id = subflow["subflow_id"] if subflow else None
    pages = [
        page for page in matrix["pages"]
        if subflow_id is None or page.get("subflow_id") == subflow_id
    ]
    interactions = [
        interaction for page in pages for interaction in page["interactions"]
    ]
    server_interactions = [
        item for item in interactions if item["effect"] != "client_only_exempt"
    ]
    files = loop.get("files", {})
    slices_value = files.get("user_flow_slices")
    if not slices_value:
        errors.append("files.user_flow_slices is required for product-prototype")
    else:
        slices_path = loop_dir(root, loop["loop_id"]) / slices_value
        if not slices_path.is_file():
            errors.append(f"user flow slices are missing: {slices_path}")
        else:
            try:
                slices = load_yaml(slices_path)
                journeys = slices.get("journeys", [])
                required_steps = {
                    "create", "edit", "save", "refresh", "relogin", "query", "downstream", "audit"
                }
                if not any(required_steps.issubset(set(item.get("steps", []))) for item in journeys):
                    errors.append("user flow slices have no complete production journey")
                mapped = {
                    interaction_id
                    for item in journeys
                    for interaction_id in item.get("interaction_ids", [])
                }
                missing = {
                    item["interaction_id"] for item in server_interactions
                } - mapped
                if missing:
                    errors.append(f"user flow slices do not map server interactions: {sorted(missing)}")
            except Exception as error:
                errors.append(f"user flow slices cannot be parsed: {error}")
    if server_interactions:
        values = files.get("api_contract", [])
        if not values:
            errors.append("files.api_contract is required for server-backed prototype interactions")
        operations, contract_errors = openapi_operation_ids(root, values)
        errors.extend(contract_errors)
        for item in server_interactions:
            for field in ("operation_id", "readback_operation_id"):
                value = item.get(field)
                if value and value not in operations:
                    errors.append(
                        f"prototype interaction {item['interaction_id']}: OpenAPI operation does not exist: {value}"
                    )
            if item["effect"] == "server_mutation" and not item.get("readback_operation_id"):
                errors.append(
                    f"prototype interaction {item['interaction_id']}: mutation has no readback operation"
                )
    return errors


def prototype_business_verification_errors(
    root: Path,
    loop: dict,
    subflow: dict | None = None,
) -> list[str]:
    if not prototype_is_required(loop, subflow):
        return []
    matrix, errors = load_prototype_matrix(root, loop)
    if matrix is None:
        return errors
    subflow_id = subflow["subflow_id"] if subflow else None
    expected = {
        interaction["interaction_id"]
        for page in matrix["pages"]
        if subflow_id is None or page.get("subflow_id") == subflow_id
        for interaction in page["interactions"]
        if interaction["effect"] != "client_only_exempt"
    }
    if not expected:
        return errors
    evidence_file = loop_dir(root, loop["loop_id"]) / loop.get("files", {}).get("evidence", "evidence.yaml")
    evidence = load_yaml(evidence_file) if evidence_file.is_file() else {"runs": []}
    tested_commit = loop.get("git", {}).get("integration", {}).get("delivery_commit") or loop.get("git", {}).get("head_commit")
    covered = set()
    complete_journey = False
    for run in evidence.get("runs", []):
        if (
            run.get("subflow_id") != subflow_id
            or run.get("executor") != "ui"
            or run.get("requirement_version") != loop["requirement_version"]
            or run.get("validity") != "active"
            or run.get("result") != "passed"
        ):
            continue
        report = run.get("test_report")
        business = run.get("business_function")
        if not report or not business:
            errors.append(f"evidence {run.get('evidence_id')}: trusted business test report is missing")
            continue
        if report["code_commit"] != run["code_commit"] or (tested_commit and run["code_commit"] != tested_commit):
            errors.append(f"evidence {run.get('evidence_id')}: test report is not bound to the tested commit")
            continue
        errors.extend(evidence_path_errors(root, [report["path"]], f"evidence {run.get('evidence_id')} test report"))
        for item in business["interactions"]:
            errors.extend(evidence_path_errors(
                root, item["evidence_paths"], f"evidence {run.get('evidence_id')} business interaction"
            ))
            covered.add(item["interaction_id"])
        for journey in business["journeys"]:
            errors.extend(evidence_path_errors(
                root, journey["evidence_paths"], f"evidence {run.get('evidence_id')} production journey"
            ))
            complete_journey = complete_journey or set(journey["steps"]) == {
                "create", "edit", "save", "refresh", "relogin", "query", "downstream", "audit"
            }
    missing = expected - covered
    if missing:
        errors.append(f"business interaction evidence is incomplete: {sorted(missing)}")
    if not complete_journey:
        errors.append("no complete create/edit/save/refresh/relogin/query/downstream/audit journey evidence")
    return errors


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
            errors.extend(prototype_business_preparation_errors(root, loop))
        if loop.get("state") in {"verified", "done"}:
            errors.extend(prototype_verification_errors(root, loop, flows))
            errors.extend(prototype_business_verification_errors(root, loop))
            errors.extend(integration_data_verification_errors(root, loop, flows))
        for subflow in loop.get("subflows", []):
            if subflow.get("state") in {
                "developing", "ready_for_verification", "verifying", "passed"
            }:
                errors.extend(prototype_preparation_errors(root, loop, subflow))
                errors.extend(prototype_business_preparation_errors(root, loop, subflow))
            if subflow.get("state") == "passed":
                errors.extend(prototype_verification_errors(root, loop, flows, subflow))
                errors.extend(prototype_business_verification_errors(root, loop, subflow))
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
    loop = load_yaml(path)
    verify_control_snapshot(root, path, loop)
    return path, loop


def active_loops(root: Path) -> list[tuple[Path, dict]]:
    result = []
    for path in sorted((root / ".agentloop" / "loops").glob("*/loop.yaml")):
        loop = load_yaml(path)
        verify_control_snapshot(root, path, loop)
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
        "integration_data": {
            "required": False,
            "reason": "待需求确认；仅前后端对接且业务数据应来自数据库时启用",
            "frontend_routes": [],
            "backend_endpoints": [],
            "database_objects": [],
            "verification_flow_id": None,
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
    write_control_snapshot(root, loop)


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
        loops = []
        for path in loop_paths:
            loop = load_yaml(path)
            try:
                verify_control_snapshot(root, path, loop)
            except ValueError as error:
                errors.append(str(error))
                continue
            loops.append(loop)
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
            loop["files"]["user_flow_slices"] = "user-flow-slices.yaml"
            loop["files"]["api_contract"] = ["api/openapi.yaml"]
            for output in ("prototype-implementation-matrix", "user-flow-slices", "api-contract"):
                if output not in loop["routing"]["development"]["required_outputs"]:
                    loop["routing"]["development"]["required_outputs"].append(output)
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
        write_control_snapshot(root, loop)


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
        write_control_snapshot(root, loop)
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
                errors.extend(integration_data_verification_errors(
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
                errors.extend(prototype_business_verification_errors(root, loop, subflow))
    if loop["git"]["integration"]["status"] != "verified":
        errors.append("git.integration.status is not verified")
    integration = loop["integration_verification"]
    if integration["state"] not in {"not_required", "passed"}:
        errors.append("integration_verification is not complete")
    errors.extend(integration_data_verification_errors(root, loop, flows))
    return errors


def transition_errors(root: Path, loop: dict, target: str, evidence: list[str]) -> list[str]:
    current = loop["state"]
    allowed = set(TRANSITIONS.get(current, set()))
    if current == "blocked" and loop.get("blocked", {}).get("resume_state"):
        allowed.add(loop["blocked"]["resume_state"])
    errors = [] if target in allowed else [f"illegal transition: {current} -> {target}"]
    if target == "awaiting_requirement_confirmation":
        errors.extend(prototype_declaration_errors(root, loop))
        errors.extend(integration_data_declaration_errors(loop))
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
        errors.extend(prototype_business_preparation_errors(root, loop))
        errors.extend(integration_data_declaration_errors(loop))
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
            errors.extend(prototype_business_verification_errors(root, loop))
            errors.extend(integration_data_verification_errors(root, loop, runtime_flows(root)))
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


def subflow_transition_errors(root: Path, loop: dict, subflow: dict, target: str) -> list[str]:
    current = subflow["state"]
    errors = [] if target in SUBFLOW_TRANSITIONS.get(current, set()) else [
        f"illegal subflow transition: {current} -> {target}"
    ]
    if loop["state"] != "orchestrating":
        errors.append("subflow transitions require parent state orchestrating")
    if target == "developing":
        errors.extend(prototype_preparation_errors(root, loop, subflow))
        errors.extend(prototype_business_preparation_errors(root, loop, subflow))
    if target == "passed":
        errors.extend(prototype_verification_errors(root, loop, runtime_flows(root), subflow))
        errors.extend(prototype_business_verification_errors(root, loop, subflow))
    return errors


def cmd_transition(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    path, loop = load_loop(root, args.loop_id)
    if args.subflow_id:
        subflow = next(
            (item for item in loop.get("subflows", []) if item["subflow_id"] == args.subflow_id),
            None,
        )
        if not subflow:
            raise ValueError(f"unknown subflow: {args.subflow_id}")
        errors = subflow_transition_errors(root, loop, subflow, args.to)
        if errors:
            raise ValueError("; ".join(errors))
        with loop_lock(root, args.loop_id, args.actor):
            previous = subflow["state"]
            subflow["state"] = args.to
            subflow["state_reason"] = args.reason
            loop["updated_at"] = now()
            loop["transitions"].append({
                "from": previous,
                "to": args.to,
                "subflow_id": args.subflow_id,
                "actor": args.actor,
                "at": now(),
                "requirement_version": loop["requirement_version"],
                "git_commit": args.git_commit or run_git(root, "rev-parse", "HEAD"),
                "evidence": args.evidence or [],
                "reason": args.reason,
            })
            schema_errors = list(schema_validator("loop.schema.json").iter_errors(loop))
            if schema_errors:
                raise ValueError(
                    f"subflow transition invalid at {schema_errors[0].json_path}: {schema_errors[0].message}"
                )
            atomic_yaml(path, loop)
            write_control_snapshot(root, loop)
        return
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
        write_control_snapshot(root, loop)


def cmd_evidence(args: argparse.Namespace) -> None:
    root = git_root(Path(args.root).resolve())
    _, loop = load_loop(root, args.loop_id)
    command = json.loads(args.command_json)
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("--command-json must be a non-empty JSON string array")
    if args.coverage_json or args.visual_json or args.data_lineage_json:
        raise ValueError("coverage/visual/data_lineage must be generated by the executed test report")
    if loop["state"] not in {"verifying", "orchestrating"}:
        raise ValueError("evidence can only be recorded while verifying or orchestrating")
    code_commit = run_git(root, "rev-parse", "HEAD")
    if args.code_commit and args.code_commit != code_commit:
        raise ValueError("--code-commit does not match current HEAD")
    report_path = project_file(root, args.report_path) if args.report_path else None
    if args.executor == "ui" and report_path is None:
        raise ValueError("UI evidence requires --report-path generated by the test runner")
    if report_path:
        report_path.unlink(missing_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["AGENTLOOP_CODE_COMMIT"] = code_commit
    run_nonce = secrets.token_hex(16)
    environment["AGENTLOOP_RUN_NONCE"] = run_nonce
    if report_path:
        environment["AGENTLOOP_REPORT_PATH"] = str(report_path)
    started = now()
    start_clock = time.monotonic()
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, env=environment)
    duration_ms = int((time.monotonic() - start_clock) * 1000)
    ended = now()
    report = None
    if report_path and report_path.is_file():
        try:
            report = json.loads(report_path.read_text())
        except (json.JSONDecodeError, OSError) as error:
            raise ValueError(f"test report is not valid JSON: {error}") from error
        if report.get("code_commit") != code_commit:
            raise ValueError("test report code_commit does not match current HEAD")
        if report.get("run_nonce") != run_nonce:
            raise ValueError("test report was not generated by the current execution")
        if report.get("assertions", 0) < 1:
            raise ValueError("test report has no assertions")
        if report.get("skipped_required", 0) != 0:
            raise ValueError("test report skipped required interactions")
        flow = runtime_flows(root).get(args.flow_id) if args.flow_id else None
        required_steps = {
            item["step_id"] for item in (flow or {}).get("steps", []) if item.get("step_id")
        }
        executed_steps = set(report.get("executed_steps", []))
        assertions_by_step = report.get("assertions_by_step", {})
        if required_steps - executed_steps:
            raise ValueError(f"test report did not execute required steps: {sorted(required_steps - executed_steps)}")
        if any(assertions_by_step.get(step, 0) < 1 for step in required_steps):
            raise ValueError("one or more required automation steps have no assertions")
    if result.returncode == 0 and args.executor == "ui" and report is None:
        raise ValueError("passed UI command did not generate a test report")
    if args.stdout_path:
        stdout_file = project_file(root, args.stdout_path)
        if stdout_file is None:
            raise ValueError("--stdout-path escapes project root")
        stdout_file.parent.mkdir(parents=True, exist_ok=True)
        stdout_file.write_text(result.stdout)
    if args.stderr_path:
        stderr_file = project_file(root, args.stderr_path)
        if stderr_file is None:
            raise ValueError("--stderr-path escapes project root")
        stderr_file.parent.mkdir(parents=True, exist_ok=True)
        stderr_file.write_text(result.stderr)
    path = loop_dir(root, args.loop_id) / "evidence.yaml"
    evidence = load_yaml(path) if path.exists() else {
        "schema_version": 1,
        "loop_id": args.loop_id,
        "runs": [],
    }
    index = len(evidence["runs"]) + 1
    outcome = "passed" if result.returncode == 0 else "failed"
    run = {
        "evidence_id": f"{args.loop_id}-evidence-{index:02d}",
        "flow_id": args.flow_id,
        "check_id": args.check_id,
        "subflow_id": args.subflow_id,
        "requirement_version": loop["requirement_version"],
        "executor": args.executor,
        "command": command,
        "result": outcome,
        "exit_code": result.returncode,
        "counts": {
            "passed": 1 if outcome == "passed" else 0,
            "failed": 1 if outcome == "failed" else 0,
            "skipped": report.get("skipped_required", 0) if report else 0,
        },
        "validity": "active",
        "code_commit": code_commit,
        "environment": args.environment,
        "started_at": started,
        "ended_at": ended,
        "duration_ms": duration_ms,
        "stdout_path": args.stdout_path,
        "stderr_path": args.stderr_path,
        "coverage": report.get("coverage", []) if report else [],
        "artifacts": [],
    }
    if report:
        run["test_report"] = {
            "path": args.report_path,
            "format": "agentloop-json",
            "code_commit": code_commit,
            "run_nonce": run_nonce,
            "assertions": report["assertions"],
            "executed_steps": report["executed_steps"],
            "skipped_required": report["skipped_required"],
        }
        for key in ("visual", "data_lineage", "business_function"):
            if report.get(key) is not None:
                run[key] = report[key]
    evidence["runs"].append(run)
    errors = list(schema_validator("evidence.schema.json").iter_errors(evidence))
    if errors:
        raise ValueError(f"evidence invalid at {errors[0].json_path}: {errors[0].message}")
    atomic_yaml(path, evidence)
    write_control_snapshot(root, loop)
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
    evidence.add_argument("--result", choices=["passed", "failed", "blocked"])
    evidence.add_argument("--command-json", required=True)
    evidence.add_argument("--exit-code", type=int)
    evidence.add_argument("--duration-ms", type=int, default=0)
    evidence.add_argument("--environment", default="local")
    evidence.add_argument("--code-commit")
    evidence.add_argument("--started-at")
    evidence.add_argument("--ended-at")
    evidence.add_argument("--stdout-path")
    evidence.add_argument("--stderr-path")
    evidence.add_argument("--report-path")
    evidence.add_argument("--coverage-json")
    evidence.add_argument("--visual-json")
    evidence.add_argument("--data-lineage-json")
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
