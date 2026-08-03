#!/usr/bin/env python3
"""Deterministic gates and projections for Markdown Workloop artifacts."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path


STATES = ("clarifying", "specified", "executing", "reviewing", "done", "blocked", "cancelled")
RANK = {name: index for index, name in enumerate(STATES[:5])}
TRANSITIONS = {
    "clarifying": {"specified", "blocked", "cancelled"},
    "specified": {"clarifying", "executing", "blocked", "cancelled"},
    "executing": {"clarifying", "reviewing", "blocked", "cancelled"},
    "reviewing": {"clarifying", "executing", "done", "blocked", "cancelled"},
    "blocked": {"clarifying", "specified", "executing", "reviewing", "cancelled"},
    "done": set(),
    "cancelled": set(),
}
SPEC_SECTIONS = ("Intent", "Facts and assumptions", "Maximum risk", "Acceptance criteria")
PLAN_SECTIONS = ("Risk coverage", "Contracts", "Work items", "Evidence index")
PLACEHOLDER = re.compile(r"<[^>]+>|\bTBD\b", re.I)


class WorkloopError(Exception):
    pass


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WorkloopError(f"missing artifact: {path}") from exc


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.S)
    if not match:
        raise WorkloopError("spec.md needs YAML frontmatter")
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def section(text: str, title: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(title)}\s*$\n(.*?)(?=^## |\Z)", text)
    return match.group(1).strip() if match else ""


def split_ids(value: str, prefix: str) -> list[str]:
    if value.strip().lower() in {"", "none", "pending"}:
        return []
    return re.findall(rf"\b{prefix}\d+\b", value)


def block_fields(block: str) -> dict[str, str]:
    return {
        key.strip().lower(): value.strip()
        for key, value in re.findall(r"(?m)^- ([A-Za-z ]+):\s*(.*)$", block)
    }


def parse_spec(text: str) -> dict:
    meta = frontmatter(text)
    assumptions = {}
    for row in re.findall(r"(?m)^\|\s*(A\d+)\s*\|(.+)$", section(text, "Facts and assumptions")):
        cells = [cell.strip() for cell in row[1].split("|")]
        if len(cells) >= 4:
            assumptions[row[0]] = {
                "statement": cells[0], "impact": cells[1].lower(),
                "status": cells[2].lower(), "evidence": cells[3],
            }
    acceptance = {}
    pattern = re.compile(
        r"(?ms)^- \[([ xX])\] `?(AC\d+)`?\s+[—-]\s+(.+?)\n"
        r"\s+- Verification:\s*(.+?)(?=\n- \[|\n## |\Z)"
    )
    for checked, item_id, statement, verification in pattern.findall(section(text, "Acceptance criteria")):
        acceptance[item_id] = {
            "checked": checked.lower() == "x", "statement": statement.strip(),
            "verification": verification.strip(),
        }
    return {"meta": meta, "assumptions": assumptions, "acceptance": acceptance, "text": text}


def named_blocks(body: str, prefix: str) -> dict[str, dict]:
    matches = list(re.finditer(rf"(?m)^### ({prefix}\d+)\s+[—-]\s+(.+)$", body))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[match.group(1)] = {
            "title": match.group(2).strip(),
            "fields": block_fields(body[match.end():end]),
        }
    return result


def parse_plan(text: str) -> dict:
    items = named_blocks(section(text, "Work items"), "T")
    contracts = named_blocks(section(text, "Contracts"), "CT")
    evidence = {}
    for item_id, rest in re.findall(r"(?m)^\|\s*(EV\d+)\s*\|(.+)$", section(text, "Evidence index")):
        cells = [cell.strip().strip("`") for cell in rest.split("|")]
        if len(cells) >= 4:
            evidence[item_id] = {
                "result": cells[0].lower(), "observed_at": cells[1],
                "source": cells[2], "covers": re.findall(r"\b(?:AC|CT)\d+\b", cells[3]),
            }
    return {"items": items, "contracts": contracts, "evidence": evidence, "text": text}


def require_text(value: str | None, label: str, errors: list[str]) -> None:
    if not value or PLACEHOLDER.search(value):
        errors.append(f"{label} is missing or still a placeholder")


def validate(loop_dir: Path, target: str | None = None) -> tuple[list[str], dict, dict | None]:
    errors: list[str] = []
    spec_text = read(loop_dir / "spec.md")
    spec = parse_spec(spec_text)
    state = spec["meta"].get("status")
    target = target or state
    if state not in STATES:
        errors.append(f"invalid status: {state!r}")
    if target not in STATES:
        errors.append(f"invalid target: {target!r}")
    for key in ("loop", "title", "created", "base_commit"):
        require_text(spec["meta"].get(key), f"spec frontmatter {key}", errors)
    for heading in SPEC_SECTIONS:
        require_text(section(spec_text, heading), f"spec section {heading}", errors)
    if not spec["acceptance"]:
        errors.append("spec needs at least one acceptance criterion")
    for item_id, item in spec["acceptance"].items():
        require_text(item["statement"], f"{item_id} statement", errors)
        require_text(item["verification"], f"{item_id} verification", errors)
    for item_id, item in spec["assumptions"].items():
        if item["impact"] not in {"scope", "acceptance", "implementation", "non-blocking"}:
            errors.append(f"{item_id} has invalid impact {item['impact']!r}")
        if item["status"] not in {"open", "confirmed", "rejected"}:
            errors.append(f"{item_id} has invalid status {item['status']!r}")
        if item["status"] != "open":
            require_text(item["evidence"], f"{item_id} closing evidence", errors)
    if target in RANK and RANK[target] >= RANK["specified"]:
        for item_id, item in spec["assumptions"].items():
            if item["impact"] in {"scope", "acceptance"} and item["status"] == "open":
                errors.append(f"{item_id} blocks {target}: {item['impact']} assumption is open")

    plan = None
    if target in RANK and RANK[target] >= RANK["executing"]:
        try:
            plan_text = read(loop_dir / "plan.md")
            plan = parse_plan(plan_text)
        except WorkloopError as exc:
            errors.append(str(exc))
            return errors, spec, plan
        for heading in PLAN_SECTIONS:
            require_text(section(plan_text, heading), f"plan section {heading}", errors)
        if not plan["items"]:
            errors.append("plan needs at least one work item")
        covered = set()
        active = []
        for item_id, item in plan["items"].items():
            fields = item["fields"]
            status_value = fields.get("status", "").lower()
            if status_value not in {"pending", "active", "done", "blocked"}:
                errors.append(f"{item_id} has invalid Status")
            if status_value == "active":
                active.append(item_id)
            ac_ids = split_ids(fields.get("covers", ""), "AC")
            covered.update(ac_ids)
            for ac_id in ac_ids:
                if ac_id not in spec["acceptance"]:
                    errors.append(f"{item_id} references missing {ac_id}")
            for assumption_id in split_ids(fields.get("assumptions", ""), "A"):
                if assumption_id not in spec["assumptions"]:
                    errors.append(f"{item_id} references missing {assumption_id}")
                elif spec["assumptions"][assumption_id]["impact"] == "implementation" and spec["assumptions"][assumption_id]["status"] == "open" and status_value == "active":
                    errors.append(f"{assumption_id} blocks active work item {item_id}")
            for dependency in split_ids(fields.get("depends on", ""), "T"):
                if dependency not in plan["items"]:
                    errors.append(f"{item_id} references missing dependency {dependency}")
            for field in ("scope", "output", "verification"):
                require_text(fields.get(field), f"{item_id} {field}", errors)
        for ac_id in spec["acceptance"]:
            if ac_id not in covered:
                errors.append(f"{ac_id} is not covered by any work item")
        if target == "executing" and len(active) != 1:
            errors.append("executing requires exactly one active work item")

        for contract_id, contract in plan["contracts"].items():
            fields = contract["fields"]
            for field in ("statement", "providers", "consumers", "work items", "verification"):
                require_text(fields.get(field), f"{contract_id} {field}", errors)
            if fields.get("providers", "").strip() == fields.get("consumers", "").strip():
                errors.append(f"{contract_id} providers and consumers must differ")
            linked = split_ids(fields.get("work items", ""), "T")
            if not linked:
                errors.append(f"{contract_id} needs linked work items")
            for item_id in linked:
                if item_id not in plan["items"]:
                    errors.append(f"{contract_id} references missing {item_id}")
                elif contract_id not in split_ids(plan["items"][item_id]["fields"].get("contracts", ""), "CT"):
                    errors.append(f"{contract_id} is not referenced back by {item_id}")

        if target in {"reviewing", "done"}:
            for item_id, item in plan["items"].items():
                if item["fields"].get("status", "").lower() != "done":
                    errors.append(f"{item_id} must be done before {target}")
            passed = {covered_id for ev in plan["evidence"].values() if ev["result"] == "pass" for covered_id in ev["covers"]}
            for needed in [*spec["acceptance"], *plan["contracts"]]:
                if needed not in passed:
                    errors.append(f"{needed} lacks passed Evidence")
            for evidence_id, evidence in plan["evidence"].items():
                if evidence["result"] not in {"pass", "fail", "stale"}:
                    errors.append(f"{evidence_id} has invalid Result")
                require_text(evidence["observed_at"], f"{evidence_id} observed_at", errors)
                require_text(evidence["source"], f"{evidence_id} source", errors)

    if target == "done":
        for item_id, item in spec["acceptance"].items():
            if not item["checked"]:
                errors.append(f"{item_id} is not checked by the reviewer")
        try:
            review = read(loop_dir / "review.md")
            anchor = re.search(r"(?m)^- Reviewer anchor:\s*(.+)$", review)
            require_text(anchor.group(1) if anchor else None, "reviewer anchor", errors)
            rows = {number: result.lower() for number, result in re.findall(r"(?m)^\|\s*([1-6])\s*\|.*?\|\s*(pass|fail)\s*\|", review, re.I)}
            for number in "123456":
                if rows.get(number) != "pass":
                    errors.append(f"review check {number} is not pass")
            conclusion = section(review, "Conclusion")
            if not re.search(r"\*\*pass\*\*", conclusion, re.I):
                errors.append("review conclusion is not pass")
            require_text(section(review, "Independent sample"), "independent sample", errors)
        except WorkloopError as exc:
            errors.append(str(exc))
    return errors, spec, plan


def command_check(args: argparse.Namespace) -> int:
    errors, _, _ = validate(Path(args.loop_dir), args.target)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: valid for {args.target or 'current status'}")
    return 0


def command_transition(args: argparse.Namespace) -> int:
    loop_dir = Path(args.loop_dir)
    text = read(loop_dir / "spec.md")
    current = frontmatter(text).get("status")
    if args.to not in TRANSITIONS.get(current, set()):
        raise WorkloopError(f"illegal transition: {current} -> {args.to}")
    errors, _, _ = validate(loop_dir, args.to)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    updated, count = re.subn(r"(?m)^status:\s*\S+\s*$", f"status: {args.to}", text, count=1)
    if count != 1:
        raise WorkloopError("spec.md needs exactly one frontmatter status")
    (loop_dir / "spec.md").write_text(updated, encoding="utf-8")
    print(f"OK: {current} -> {args.to}")
    return 0


def memory_entries(loop_dir: Path) -> dict[str, list[str]]:
    path = loop_dir.parent.parent / "memory.md"
    if not path.exists():
        return {}
    result = {}
    for item_id, rest in re.findall(r"(?m)^\|\s*(M\d+)\s*\|(.+)$", read(path)):
        result[item_id] = [cell.strip() for cell in rest.split("|")]
    return result


def command_project(args: argparse.Namespace) -> int:
    loop_dir = Path(args.loop_dir)
    errors, spec, plan = validate(loop_dir, "executing")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    assert plan is not None
    item = plan["items"].get(args.work_item)
    if not item:
        raise WorkloopError(f"unknown work item: {args.work_item}")
    fields = item["fields"]
    ac_ids = split_ids(fields.get("covers", ""), "AC")
    assumption_ids = split_ids(fields.get("assumptions", ""), "A")
    contract_ids = split_ids(fields.get("contracts", ""), "CT")
    dependency_ids = split_ids(fields.get("depends on", ""), "T")
    memory_ids = split_ids(fields.get("memory", ""), "M")
    evidence_ids = split_ids(fields.get("evidence", ""), "EV")
    projection = {
        "loop": {**spec["meta"], "intent": section(spec["text"], "Intent")},
        "work_item": {"id": args.work_item, **item},
        "dependencies": {item_id: plan["items"][item_id] for item_id in dependency_ids},
        "acceptance": {item_id: spec["acceptance"][item_id] for item_id in ac_ids},
        "assumptions": {item_id: spec["assumptions"][item_id] for item_id in assumption_ids},
        "contracts": {item_id: plan["contracts"][item_id] for item_id in contract_ids},
        "evidence": {item_id: plan["evidence"][item_id] for item_id in evidence_ids if item_id in plan["evidence"]},
        "memory": {item_id: memory_entries(loop_dir)[item_id] for item_id in memory_ids if item_id in memory_entries(loop_dir)},
    }
    print(json.dumps(projection, ensure_ascii=False, indent=2))
    return 0


def patch_paths(command: str) -> list[str]:
    return re.findall(r"(?m)^\*\*\* (?:Add|Update|Delete) File: (.+)$", command)


def relative_path(root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix().removeprefix("./")


def emit_deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))


def project_root(start: Path) -> Path | None:
    for path in (start, *start.parents):
        if (path / ".workloop").is_dir() or (path / ".git").exists():
            return path
    return None


def active_loops(root: Path) -> list[tuple[Path, dict]]:
    result = []
    for path in (root / ".workloop" / "loops").glob("*/spec.md"):
        try:
            meta = frontmatter(read(path))
        except WorkloopError:
            continue
        if meta.get("status") not in {"done", "cancelled"}:
            result.append((path.parent, meta))
    return result


def command_hook(args: argparse.Namespace) -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        event = {}
    root = project_root(Path(event.get("cwd", ".")).resolve())
    if not root:
        return 0
    loops = active_loops(root)
    if args.event == "session-start":
        if loops:
            summary = ", ".join(f"{meta.get('loop')}:{meta.get('status')}" for _, meta in loops)
            print(f"Workloop active: {summary}. Load $workloop and run the current Gate before acting.")
        return 0
    command = str(event.get("tool_input", {}).get("command", ""))
    paths = patch_paths(command)
    if not paths or not loops:
        return 0
    if re.search(r"(?m)^\+status:\s*", command):
        emit_deny("Change Workloop status through the checked transition command.")
        return 0
    normalized = [relative_path(root, path) for path in paths]
    if all(path.startswith(".workloop/") for path in normalized):
        return 0
    if len(loops) != 1 or loops[0][1].get("status") != "executing":
        emit_deny("Project edits require exactly one Workloop in executing status.")
        return 0
    try:
        plan = parse_plan(read(loops[0][0] / "plan.md"))
    except WorkloopError as exc:
        emit_deny(str(exc))
        return 0
    active = [item for item in plan["items"].values() if item["fields"].get("status", "").lower() == "active"]
    if len(active) != 1:
        emit_deny("Project edits require exactly one active work item.")
        return 0
    scopes = [value.strip().strip("`") for value in active[0]["fields"].get("scope", "").split(",") if value.strip()]
    if not all(any(fnmatch.fnmatch(path, scope) or path.startswith(scope.rstrip("*")) for scope in scopes) for path in normalized):
        emit_deny("One or more edited paths are outside the active work item's Scope.")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("--loop-dir", required=True)
    check.add_argument("--target", choices=STATES)
    check.set_defaults(handler=command_check)
    transition = commands.add_parser("transition")
    transition.add_argument("--loop-dir", required=True)
    transition.add_argument("--to", required=True, choices=STATES)
    transition.set_defaults(handler=command_transition)
    project = commands.add_parser("project")
    project.add_argument("--loop-dir", required=True)
    project.add_argument("--work-item", required=True)
    project.set_defaults(handler=command_project)
    hook = commands.add_parser("hook")
    hook.add_argument("event", choices=("session-start", "pre-tool"))
    hook.set_defaults(handler=command_hook)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.handler(args)
    except WorkloopError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
