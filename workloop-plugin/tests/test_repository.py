import re
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).parents[2]
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
METHOD_SKILLS = (
    "workloop",
    "workloop-spec",
    "workloop-plan",
    "workloop-execute",
    "workloop-review",
    "workloop-memory",
)


def human_facing_sources():
    yield Path("README.md")
    yield from sorted(path.relative_to(REPOSITORY) for path in (REPOSITORY / "docs").rglob("*.md"))
    for suffix in ("*.md", "*.yaml"):
        yield from sorted(path.relative_to(REPOSITORY) for path in (REPOSITORY / "workloop-skills").rglob(suffix))
        yield from sorted(
            path.relative_to(REPOSITORY)
            for path in (REPOSITORY / "workloop-plugin" / "skills" / "workloop-controls").rglob(suffix)
        )


class RepositoryContractTest(unittest.TestCase):
    def test_canonical_human_facing_sources_are_english(self):
        offenders = []
        for relative in human_facing_sources():
            if CJK.search((REPOSITORY / relative).read_text(encoding="utf-8")):
                offenders.append(relative.as_posix())
        self.assertEqual(offenders, [])

    def test_chinese_companion_is_complete_and_chinese(self):
        missing = []
        untranslated = []
        for relative in human_facing_sources():
            companion = REPOSITORY / "workloop-cn" / relative
            if not companion.is_file():
                missing.append(relative.as_posix())
            elif not CJK.search(companion.read_text(encoding="utf-8")):
                untranslated.append(relative.as_posix())
        self.assertEqual(missing, [])
        self.assertEqual(untranslated, [])

    def test_plugin_packages_all_canonical_method_skills_without_drift(self):
        mismatches = []
        for skill in METHOD_SKILLS:
            source = REPOSITORY / "workloop-skills" / skill
            packaged = REPOSITORY / "workloop-plugin" / "skills" / skill
            source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
            packaged_files = sorted(path.relative_to(packaged) for path in packaged.rglob("*") if path.is_file())
            if source_files != packaged_files:
                mismatches.append(f"{skill}: file set")
                continue
            for relative in source_files:
                if (source / relative).read_bytes() != (packaged / relative).read_bytes():
                    mismatches.append(f"{skill}/{relative.as_posix()}")
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
