#!/usr/bin/env python3

import copy
import importlib.util
import sys
import tempfile
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPTS.parent
sys.path[:0] = [str(SCRIPTS), str(PLUGIN_ROOT / "vendor")]
spec = importlib.util.spec_from_file_location("agentloop_engine", SCRIPTS / "agentloop.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def project(root: Path, base: dict, state: str) -> dict:
    loop = copy.deepcopy(base)
    loop["state"] = state
    if state == "blocked":
        loop["blocked"] = {
            "reason": "dependency unavailable",
            "owner": "loop-coordinator",
            "unblock_condition": "dependency restored",
            "resume_state": "developing",
        }
    path = root / "loop.yaml"
    engine.atomic_yaml(path, loop)
    return engine.context_projection(root, path, loop)


def main() -> None:
    base = engine.load_yaml(PLUGIN_ROOT / "references" / "agentloop" / "examples" / "composite.loop.yaml")
    cases = {
        "clarifying": ("requirements", {"git", "routing", "evidence", "transitions", "gate_events"}),
        "developing": ("development", {"classification", "evidence", "transitions", "gate_events"}),
        "verifying": ("verification", {"classification", "transitions", "gate_events", "subflows"}),
        "orchestrating": ("integration", {"classification", "transitions", "gate_events", "execution"}),
        "verified": ("completion", {"classification", "routing", "transitions", "gate_events", "execution"}),
        "blocked": ("recovery", {"classification", "routing", "acceptance_obligations", "gate_events"}),
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for state, (phase, forbidden) in cases.items():
            context = project(root, base, state)
            assert context["phase"] == phase
            assert context["phase_skill"] == f"development-process-agentloop:agentloop-{phase}"
            assert not forbidden & context.keys(), (state, forbidden & context.keys())

        path = root / "loop.yaml"
        engine.atomic_yaml(path, base)
        focused = engine.context_projection(root, path, base, "sf-01-refund")
        assert focused["phase"] == "development"
        assert focused["focus"]["subflow_id"] == "sf-01-refund"
        assert [item["acceptance_id"] for item in focused["acceptance_obligations"]] == ["AC-01"]
        assert "subflows" not in focused

        passed = copy.deepcopy(base)
        passed["subflows"][0]["state"] = "passed"
        engine.atomic_yaml(path, passed)
        passed_focus = engine.context_projection(root, path, passed, "sf-01-refund")
        assert passed_focus["phase"] == "integration"
        assert "subflows" not in passed_focus and "child_loops" not in passed_focus

        requirement = project(root, base, "clarifying")
        assert len(engine.yaml.safe_dump(requirement, allow_unicode=True)) < len(
            engine.yaml.safe_dump(base, allow_unicode=True)
        ) * 0.7
    print("passed: phase context projections")


if __name__ == "__main__":
    main()
