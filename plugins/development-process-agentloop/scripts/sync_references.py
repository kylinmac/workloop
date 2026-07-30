#!/usr/bin/env python3

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
REFERENCE_ROOT = PLUGIN_ROOT / "references"
SOURCES = ("README.md", "agentloop", "requirements", "development", "verification", "rules")
MANIFEST = "_generated.json"


def source_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for name in SOURCES:
        source = REPO_ROOT / name
        if not source.exists():
            raise ValueError(f"missing canonical source: {source}")
        candidates = [source] if source.is_file() else source.rglob("*")
        for path in candidates:
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(REPO_ROOT).as_posix()] = path
    return files


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_manifest() -> dict:
    return {
        "schema_version": 1,
        "notice": "Generated from the repository process sources; do not edit references directly.",
        "files": {name: digest(path) for name, path in sorted(source_files().items())},
    }


def snapshot_manifest() -> dict:
    path = REFERENCE_ROOT / MANIFEST
    if not path.exists():
        raise ValueError(f"missing generated manifest: {path}")
    return json.loads(path.read_text())


def verify() -> None:
    manifest = snapshot_manifest()
    declared = manifest.get("files", {})
    actual = {
        path.relative_to(REFERENCE_ROOT).as_posix(): digest(path)
        for path in REFERENCE_ROOT.rglob("*")
        if path.is_file() and path.name != MANIFEST
    }
    if actual != declared:
        raise ValueError("plugin references do not match their generated manifest")


def check() -> None:
    verify()
    if snapshot_manifest() != expected_manifest():
        raise ValueError("plugin references are stale; run sync_references.py sync")


def sync() -> None:
    manifest = expected_manifest()
    try:
        check()
        print("up to date: plugin references")
        return
    except (ValueError, json.JSONDecodeError):
        pass

    with tempfile.TemporaryDirectory(prefix=".references-", dir=PLUGIN_ROOT) as directory:
        generated = Path(directory) / "references"
        for name, source in source_files().items():
            destination = generated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        (generated / MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        shutil.rmtree(REFERENCE_ROOT, ignore_errors=True)
        shutil.copytree(generated, REFERENCE_ROOT)
    print("synced: canonical process sources -> plugin references")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync", "check", "verify"))
    args = parser.parse_args()
    try:
        {"sync": sync, "check": check, "verify": verify}[args.command]()
    except (ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    if args.command != "sync":
        print(f"passed: plugin references {args.command}")


if __name__ == "__main__":
    main()
