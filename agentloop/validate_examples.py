from copy import deepcopy
from json import loads
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).parent
try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    scripts = ROOT.parent / "plugins" / "development-process-agentloop" / "scripts"
    sys.path.insert(0, str(scripts))
    from schema_validation import Validator as Draft202012Validator
    FormatChecker = None

CASES = {
    "project.schema.json": ["project.yaml"],
    "flow.schema.json": ["flow.yaml", "ui-visual.flow.yaml"],
    "evidence.schema.json": ["evidence.yaml", "ui-visual.evidence.yaml"],
    "prototype-matrix.schema.json": ["prototype-matrix.yaml"],
    "development-assurance.schema.json": ["development-assurance.yaml"],
    "development-contract.schema.json": ["development-contract.yaml"],
    "loop.schema.json": [
        "trivial.loop.yaml",
        "standard.loop.yaml",
        "composite.loop.yaml",
        "epic.loop.yaml",
    ],
}


def main() -> None:
    loaded = {}
    for schema_name, examples in CASES.items():
        schema = loads((ROOT / "schemas" / schema_name).read_text())
        Draft202012Validator.check_schema(schema)
        validator = (
            Draft202012Validator(schema, format_checker=FormatChecker())
            if FormatChecker else Draft202012Validator(schema)
        )
        for example in examples:
            data = yaml.safe_load((ROOT / "examples" / example).read_text())
            errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
            assert not errors, f"{example}: {errors[0].json_path}: {errors[0].message}"
            loaded[example] = (validator, data)
            print(f"passed: {example}")

    invalid = deepcopy(loaded["epic.loop.yaml"][1])
    invalid["execution_profile"]["level"] = "standard"
    assert list(loaded["epic.loop.yaml"][0].iter_errors(invalid))

    invalid = deepcopy(loaded["trivial.loop.yaml"][1])
    invalid["routing"]["development"]["main_flow"] = "root-cause"
    assert list(loaded["trivial.loop.yaml"][0].iter_errors(invalid))

    invalid = deepcopy(loaded["flow.yaml"][1])
    invalid["id"] = invalid.pop("flow_id")
    assert list(loaded["flow.yaml"][0].iter_errors(invalid))
    print("passed: invalid cases rejected")


if __name__ == "__main__":
    main()
