#!/usr/bin/env python3
"""Checks that every SKILL.md frontmatter will parse as YAML in strict loaders (e.g. Antigravity's)."""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_FILES = sorted(REPO.glob("skills/*/SKILL.md")) + sorted(REPO.glob("extras/*/SKILL.md"))

# A plain (unquoted) YAML scalar may not contain ": " or " #", and may not start with an indicator.
PLAIN_SCALAR_BREAKERS = (": ", " #")
INDICATOR_STARTS = ("@", "`", "%", "*", "&", "!", ",", "?", "-", ":")


def frontmatter_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    end = lines.index("---", 1)
    return lines[1:end]


class TestSkillFrontmatter(unittest.TestCase):
    def test_skill_files_found(self):
        self.assertGreater(len(SKILL_FILES), 20)

    def test_frontmatter_is_strict_yaml_safe(self):
        for path in SKILL_FILES:
            rel = path.relative_to(REPO)
            with self.subTest(skill=str(rel)):
                lines = frontmatter_lines(path)
                self.assertTrue(lines, f"{rel}: missing '---' frontmatter block")
                keys = {}
                for line in lines:
                    m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
                    if not m:
                        continue  # continuation line of a block scalar
                    key, value = m.groups()
                    keys[key] = value
                    if not value or value[0] in "\"'>|[{":
                        continue
                    for breaker in PLAIN_SCALAR_BREAKERS:
                        self.assertNotIn(breaker, value, f"{rel}: unquoted `{key}` contains {breaker!r}; quote it")
                    self.assertFalse(value.startswith(INDICATOR_STARTS), f"{rel}: unquoted `{key}` starts with an indicator")
                self.assertEqual(keys.get("name"), path.parent.name, f"{rel}: `name` must match the folder name")
                self.assertTrue(keys.get("description"), f"{rel}: missing `description`")

    def test_core_descriptions_state_when_to_use(self):
        # Descriptions decide when a skill loads: triggering situations only, no workflow summary.
        for path in sorted(REPO.glob("skills/*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                line = next(l for l in frontmatter_lines(path) if l.startswith("description:"))
                description = line.split(":", 1)[1].strip().strip("\"'")
                self.assertTrue(description.startswith(("Use when", "Use before")), description[:60])
                self.assertLessEqual(len(description), 300)


if __name__ == "__main__":
    unittest.main()
