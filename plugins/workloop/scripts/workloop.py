#!/usr/bin/env python3
"""Minimal, dependency-free controller for Workloop v0.1 JSON artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


FILES = ("brief.json", "plan.json", "evidence.json", "failures.json")
NORMAL_STATES = ("draft", "ready", "executing", "verifying", "done")
ALL_STATES = set(NORMAL_STATES) | {"blocked", "revise"}
STATE_ORDER = {name: index for index, name in enumerate(NORMAL_STATES)}
TRANSITIONS = {
    "draft": {"ready", "blocked"},
    "ready": {"executing", "blocked", "revise"},
    "executing": {"verifying", "blocked", "revise"},
    "verifying": {"done", "blocked", "revise"},
    "blocked": {"draft", "ready", "executing", "verifying", "revise"},
    "revise": {"draft", "ready", "executing", "blocked"},
    "done": set(),
}
COGNITION_TYPES = {"fact", "assumption", "unknown", "conflict", "decision"}
COGNITION_STATES = {"unverified", "confirmed", "rejected", "conflicted", "resolved"}
RESOLVED_COGNITION = {"confirmed", "rejected", "resolved"}
WORK_STATES = {"pending", "ready", "executing", "done", "blocked"}
RESULTS = {"passed", "failed"}
VALIDITY = {"active", "stale"}
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{1,63}$")


class ProtocolError(Exception):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProtocolError(f"missing artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError(f"artifact root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_task(task_dir: Path) -> dict[str, dict[str, Any]]:
    return {name[:-5]: read_json(task_dir / name) for name in FILES}


def as_list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    return value


def text_required(value: Any, path: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return ""
    return value.strip()


def collect_by_id(items: list[Any], path: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        prefix = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = text_required(item.get("id"), f"{prefix}.id", errors)
        if item_id and not ID_PATTERN.match(item_id):
            errors.append(f"{prefix}.id must use stable upper-case ID syntax")
        if item_id in result:
            errors.append(f"duplicate ID {item_id} in {path}")
        elif item_id:
            result[item_id] = item
    return result


def validate_task(data: dict[str, dict[str, Any]], target: str | None = None) -> list[str]:
    errors: list[str] = []
    brief, plan = data["brief"], data["plan"]
    evidence, failures = data["evidence"], data["failures"]

    task_id = text_required(brief.get("task_id"), "brief.task_id", errors)
    for name, artifact in data.items():
        if artifact.get("task_id") != task_id:
            errors.append(f"{name}.task_id must equal {task_id!r}")

    state = brief.get("state")
    if state not in ALL_STATES:
        errors.append(f"brief.state must be one of {sorted(ALL_STATES)}")
    target_state = target or state
    if target_state not in ALL_STATES:
        errors.append(f"unknown target state: {target_state}")

    intent = brief.get("intent")
    if not isinstance(intent, dict):
        errors.append("brief.intent must be an object")
        intent = {}
    text_required(intent.get("goal"), "brief.intent.goal", errors)
    for field in ("in_scope", "out_of_scope", "constraints"):
        as_list(intent.get(field), f"brief.intent.{field}", errors)

    acceptance = collect_by_id(as_list(brief.get("acceptance"), "brief.acceptance", errors), "brief.acceptance", errors)
    for item_id, item in acceptance.items():
        text_required(item.get("statement"), f"acceptance[{item_id}].statement", errors)

    cognition = collect_by_id(as_list(brief.get("cognition"), "brief.cognition", errors), "brief.cognition", errors)
    evidence_items = collect_by_id(as_list(evidence.get("items"), "evidence.items", errors), "evidence.items", errors)
    for item_id, item in cognition.items():
        prefix = f"cognition[{item_id}]"
        text_required(item.get("statement"), f"{prefix}.statement", errors)
        if item.get("type") not in COGNITION_TYPES:
            errors.append(f"{prefix}.type must be one of {sorted(COGNITION_TYPES)}")
        if item.get("status") not in COGNITION_STATES:
            errors.append(f"{prefix}.status must be one of {sorted(COGNITION_STATES)}")
        blocks = as_list(item.get("blocks", []), f"{prefix}.blocks", errors)
        for block in blocks:
            if block not in STATE_ORDER:
                errors.append(f"{prefix}.blocks contains unknown normal state {block!r}")
        evidence_ids = as_list(item.get("evidence_ids", []), f"{prefix}.evidence_ids", errors)
        for evidence_id in evidence_ids:
            if evidence_id not in evidence_items:
                errors.append(f"{prefix} references missing Evidence {evidence_id}")
        has_active_proof = any(
            evidence_items.get(evidence_id, {}).get("result") == "passed"
            and evidence_items.get(evidence_id, {}).get("validity") == "active"
            for evidence_id in evidence_ids
        )
        if item.get("status") in RESOLVED_COGNITION and not has_active_proof and not item.get("source"):
            errors.append(f"{prefix} is resolved without active passed Evidence or a source")
        if item.get("type") == "fact" and not has_active_proof and not item.get("source"):
            errors.append(f"{prefix} fact requires active passed Evidence or a source")
        if item.get("type") == "decision":
            options = as_list(item.get("options"), f"{prefix}.options", errors)
            if item.get("selected") not in options:
                errors.append(f"{prefix}.selected must be one of options")
            text_required(item.get("rationale"), f"{prefix}.rationale", errors)
            for based_on in as_list(item.get("based_on", []), f"{prefix}.based_on", errors):
                if based_on not in cognition:
                    errors.append(f"{prefix} references missing cognition {based_on}")

    for risk_id, risk in collect_by_id(as_list(brief.get("risks"), "brief.risks", errors), "brief.risks", errors).items():
        text_required(risk.get("obligation"), f"risks[{risk_id}].obligation", errors)

    work_items = collect_by_id(as_list(plan.get("work_items"), "plan.work_items", errors), "plan.work_items", errors)
    contracts = collect_by_id(as_list(plan.get("contracts"), "plan.contracts", errors), "plan.contracts", errors)

    for item_id, item in work_items.items():
        prefix = f"work_items[{item_id}]"
        text_required(item.get("title"), f"{prefix}.title", errors)
        if item.get("status") not in WORK_STATES:
            errors.append(f"{prefix}.status must be one of {sorted(WORK_STATES)}")
        scope = item.get("scope")
        if not isinstance(scope, dict):
            errors.append(f"{prefix}.scope must be an object")
            scope = {}
        if not as_list(scope.get("paths"), f"{prefix}.scope.paths", errors):
            errors.append(f"{prefix}.scope.paths must not be empty")
        if not as_list(item.get("outputs"), f"{prefix}.outputs", errors):
            errors.append(f"{prefix}.outputs must not be empty")
        if not as_list(item.get("verification"), f"{prefix}.verification", errors):
            errors.append(f"{prefix}.verification must not be empty")
        for dependency in as_list(item.get("depends_on", []), f"{prefix}.depends_on", errors):
            if dependency not in work_items:
                errors.append(f"{prefix} references missing dependency {dependency}")
            if dependency == item_id:
                errors.append(f"{prefix} cannot depend on itself")
        for ref in as_list(item.get("acceptance_ids", []), f"{prefix}.acceptance_ids", errors):
            if ref not in acceptance:
                errors.append(f"{prefix} references missing acceptance {ref}")
        for ref in as_list(item.get("cognition_ids", []), f"{prefix}.cognition_ids", errors):
            if ref not in cognition:
                errors.append(f"{prefix} references missing cognition {ref}")
        for ref in as_list(item.get("contract_ids", []), f"{prefix}.contract_ids", errors):
            if ref not in contracts:
                errors.append(f"{prefix} references missing contract {ref}")

    detect_dependency_cycles(work_items, errors)

    for contract_id, contract in contracts.items():
        prefix = f"contracts[{contract_id}]"
        if contract.get("kind") not in {"api", "data", "behavior", "acceptance"}:
            errors.append(f"{prefix}.kind is invalid")
        text_required(contract.get("statement"), f"{prefix}.statement", errors)
        providers = as_list(contract.get("providers"), f"{prefix}.providers", errors)
        consumers = as_list(contract.get("consumers"), f"{prefix}.consumers", errors)
        if not providers or not consumers:
            errors.append(f"{prefix} requires providers and consumers")
        if set(providers) & set(consumers):
            errors.append(f"{prefix} providers and consumers must be distinct")
        contract_work_items = as_list(contract.get("work_item_ids"), f"{prefix}.work_item_ids", errors)
        if not contract_work_items:
            errors.append(f"{prefix}.work_item_ids must not be empty")
        for ref in contract_work_items:
            if ref not in work_items:
                errors.append(f"{prefix} references missing work item {ref}")
            elif contract_id not in work_items[ref].get("contract_ids", []):
                errors.append(f"{prefix} is not referenced back by work item {ref}")

    for evidence_id, item in evidence_items.items():
        prefix = f"evidence[{evidence_id}]"
        text_required(item.get("kind"), f"{prefix}.kind", errors)
        if item.get("result") not in RESULTS:
            errors.append(f"{prefix}.result must be passed or failed")
        if item.get("validity") not in VALIDITY:
            errors.append(f"{prefix}.validity must be active or stale")
        text_required(item.get("method"), f"{prefix}.method", errors)
        text_required(item.get("source"), f"{prefix}.source", errors)
        for field, known in (("acceptance_ids", acceptance), ("cognition_ids", cognition), ("contract_ids", contracts)):
            for ref in as_list(item.get(field, []), f"{prefix}.{field}", errors):
                if ref not in known:
                    errors.append(f"{prefix} references missing {field[:-4]} {ref}")

    failure_items = collect_by_id(as_list(failures.get("items"), "failures.items", errors), "failures.items", errors)
    failure_by_evidence: dict[str, dict[str, Any]] = {}
    for failure_id, item in failure_items.items():
        prefix = f"failures[{failure_id}]"
        failed_id = text_required(item.get("failed_evidence_id"), f"{prefix}.failed_evidence_id", errors)
        failed_item = evidence_items.get(failed_id)
        if not failed_item or failed_item.get("result") != "failed":
            errors.append(f"{prefix} must reference failed Evidence")
        elif failed_id in failure_by_evidence:
            errors.append(f"multiple failure cards reference {failed_id}")
        else:
            failure_by_evidence[failed_id] = item
        text_required(item.get("mistake"), f"{prefix}.mistake", errors)
        text_required(item.get("actual_reason"), f"{prefix}.actual_reason", errors)
        text_required(item.get("prevention"), f"{prefix}.prevention", errors)
        linked = as_list(item.get("cognition_ids", []), f"{prefix}.cognition_ids", errors)
        for ref in linked:
            if ref not in cognition:
                errors.append(f"{prefix} references missing cognition {ref}")
        if not linked and not item.get("unlinked_reason"):
            errors.append(f"{prefix} needs cognition_ids or unlinked_reason")
        if item.get("status") not in {"open", "prevention_verified"}:
            errors.append(f"{prefix}.status is invalid")
        reverify = as_list(item.get("reverification_evidence_ids", []), f"{prefix}.reverification_evidence_ids", errors)
        for ref in reverify:
            if ref not in evidence_items:
                errors.append(f"{prefix} references missing re-verification Evidence {ref}")
        if item.get("status") == "prevention_verified" and not any(
            evidence_items.get(ref, {}).get("result") == "passed"
            and evidence_items.get(ref, {}).get("validity") == "active"
            for ref in reverify
        ):
            errors.append(f"{prefix} is prevention_verified without active passed re-verification")

    if target_state in STATE_ORDER and STATE_ORDER[target_state] >= STATE_ORDER["ready"]:
        if not acceptance:
            errors.append("ready requires at least one acceptance item")
        if not work_items:
            errors.append("ready requires at least one work item")
        covered = {ref for item in work_items.values() for ref in item.get("acceptance_ids", [])}
        for acceptance_id in acceptance:
            if acceptance_id not in covered:
                errors.append(f"acceptance {acceptance_id} is not covered by any work item")

    if target_state in STATE_ORDER:
        target_rank = STATE_ORDER[target_state]
        for cognition_id, item in cognition.items():
            if any(STATE_ORDER.get(block, 999) <= target_rank for block in item.get("blocks", [])):
                if item.get("status") not in RESOLVED_COGNITION:
                    errors.append(f"cognition {cognition_id} blocks target state {target_state}")

    if target_state in {"verifying", "done"}:
        for work_id, item in work_items.items():
            if item.get("status") != "done":
                errors.append(f"work item {work_id} must be done before {target_state}")

    if target_state == "done":
        active_passed_acceptance = covered_ids(evidence_items, "acceptance_ids")
        active_passed_contracts = covered_ids(evidence_items, "contract_ids")
        for acceptance_id in acceptance:
            if acceptance_id not in active_passed_acceptance:
                errors.append(f"acceptance {acceptance_id} lacks active passed Evidence")
        for contract_id in contracts:
            if contract_id not in active_passed_contracts:
                errors.append(f"contract {contract_id} lacks active passed Evidence")
        for evidence_id, item in evidence_items.items():
            if item.get("result") == "failed" and evidence_id not in failure_by_evidence:
                errors.append(f"failed Evidence {evidence_id} lacks a failure card")
        for failure_id, item in failure_items.items():
            if item.get("status") != "prevention_verified":
                errors.append(f"failure card {failure_id} is not prevention_verified")

    return errors


def detect_dependency_cycles(work_items: dict[str, dict[str, Any]], errors: list[str]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str) -> None:
        if item_id in visiting:
            errors.append(f"work item dependency cycle includes {item_id}")
            return
        if item_id in visited:
            return
        visiting.add(item_id)
        for dependency in work_items[item_id].get("depends_on", []):
            if dependency in work_items:
                visit(dependency)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in work_items:
        visit(item_id)


def covered_ids(evidence_items: dict[str, dict[str, Any]], field: str) -> set[str]:
    return {
        ref
        for item in evidence_items.values()
        if item.get("result") == "passed" and item.get("validity") == "active"
        for ref in item.get(field, [])
    }


def command_init(args: argparse.Namespace) -> int:
    if not ID_PATTERN.match(args.task_id):
        raise ProtocolError("task ID must use upper-case letters, digits, and hyphens")
    task_dir = Path(args.root).resolve() / ".workloop" / "tasks" / args.task_id
    if task_dir.exists() and any(task_dir.iterdir()):
        raise ProtocolError(f"task already exists: {task_dir}")
    base = {"task_id": args.task_id}
    write_json(task_dir / "brief.json", {
        "protocol_version": "0.1",
        **base,
        "title": args.title,
        "state": "draft",
        "intent": {"goal": args.title, "in_scope": [], "out_of_scope": [], "constraints": []},
        "acceptance": [],
        "cognition": [],
        "risks": [],
    })
    write_json(task_dir / "plan.json", {**base, "work_items": [], "contracts": []})
    write_json(task_dir / "evidence.json", {**base, "items": []})
    write_json(task_dir / "failures.json", {**base, "items": []})
    print(task_dir)
    return 0


def command_check(args: argparse.Namespace) -> int:
    errors = validate_task(load_task(Path(args.task_dir)), args.target)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: task is valid for {args.target or 'current state'}")
    return 0


def command_transition(args: argparse.Namespace) -> int:
    task_dir = Path(args.task_dir)
    data = load_task(task_dir)
    current = data["brief"].get("state")
    if args.to not in TRANSITIONS.get(current, set()):
        raise ProtocolError(f"illegal transition: {current} -> {args.to}")
    errors = validate_task(data, args.to)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    data["brief"]["state"] = args.to
    write_json(task_dir / "brief.json", data["brief"])
    print(f"OK: {current} -> {args.to}")
    return 0


def command_project(args: argparse.Namespace) -> int:
    data = load_task(Path(args.task_dir))
    errors = validate_task(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    work_items = {item["id"]: item for item in data["plan"]["work_items"]}
    selected = work_items.get(args.work_item)
    if not selected:
        raise ProtocolError(f"unknown work item: {args.work_item}")
    dependency_status = {ref: work_items[ref]["status"] for ref in selected.get("depends_on", [])}
    if any(status != "done" for status in dependency_status.values()):
        raise ProtocolError(f"work item dependencies are not done: {dependency_status}")
    cognition_ids = set(selected.get("cognition_ids", []))
    acceptance_ids = set(selected.get("acceptance_ids", []))
    contract_ids = set(selected.get("contract_ids", []))
    selected_cognition = [item for item in data["brief"]["cognition"] if item["id"] in cognition_ids]
    unresolved = [
        item["id"] for item in selected_cognition
        if "executing" in item.get("blocks", []) and item.get("status") not in RESOLVED_COGNITION
    ]
    if unresolved:
        raise ProtocolError(f"work item has unresolved execution cognition: {unresolved}")
    projection = {
        "task": {
            "task_id": data["brief"]["task_id"],
            "title": data["brief"].get("title"),
            "goal": data["brief"]["intent"]["goal"],
            "constraints": data["brief"]["intent"].get("constraints", []),
        },
        "work_item": selected,
        "dependency_status": dependency_status,
        "acceptance": [item for item in data["brief"]["acceptance"] if item["id"] in acceptance_ids],
        "cognition": selected_cognition,
        "contracts": [item for item in data["plan"]["contracts"] if item["id"] in contract_ids],
        "evidence": [
            item for item in data["evidence"]["items"]
            if acceptance_ids.intersection(item.get("acceptance_ids", []))
            or cognition_ids.intersection(item.get("cognition_ids", []))
            or contract_ids.intersection(item.get("contract_ids", []))
        ],
    }
    print(json.dumps(projection, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create the four core artifacts")
    init_parser.add_argument("--root", default=".")
    init_parser.add_argument("--task-id", required=True)
    init_parser.add_argument("--title", required=True)
    init_parser.set_defaults(handler=command_init)

    check_parser = subparsers.add_parser("check", help="validate artifacts for a target state")
    check_parser.add_argument("--task-dir", required=True)
    check_parser.add_argument("--target", choices=sorted(ALL_STATES))
    check_parser.set_defaults(handler=command_check)

    transition_parser = subparsers.add_parser("transition", help="validate and update task state")
    transition_parser.add_argument("--task-dir", required=True)
    transition_parser.add_argument("--to", required=True, choices=sorted(ALL_STATES))
    transition_parser.set_defaults(handler=command_transition)

    project_parser = subparsers.add_parser("project", help="print one isolated work package")
    project_parser.add_argument("--task-dir", required=True)
    project_parser.add_argument("--work-item", required=True)
    project_parser.set_defaults(handler=command_project)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except ProtocolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
