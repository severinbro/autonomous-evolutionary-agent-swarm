#!/usr/bin/env python3
"""Checks that skill texts keep the behaviour the design in docs/designs/skill-pack-v3.md relies on."""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


class InvokeSwarmModesTest(unittest.TestCase):
    def setUp(self):
        self.text = read("skills/invoke-swarm/SKILL.md")

    def test_no_argument_never_maps_to_full_mode(self):
        self.assertIsNone(re.search(r"Full Mode \(`/invoke-swarm`(?! full)", self.text))
        self.assertIn("No argument means Lite", self.text)
        self.assertIn("**`lite` (default)**", self.text)
        self.assertIn("`/invoke-swarm full`", self.text)

    def test_init_swarm_examples_default_to_lite(self):
        self.assertIn("--init-swarm --full", self.text)
        self.assertNotIn("--init-swarm --lite", self.text)

    def test_release_level_audit_is_defined(self):
        self.assertIn("Release-level audit", self.text)
        self.assertIn("CRITICAL_GAP", self.text)
        self.assertIn("AUDIT-<n>", self.text)

    def test_step_0_1_keeps_its_instructions(self):
        self.assertIn("Step 0.1", self.text)
        self.assertIn("add every executable acceptance check", self.text)

    def test_quality_validator_is_called_with_a_binary(self):
        self.assertNotIn("quality_validator.py\" --workspace", self.text)

    def test_best_of_3_is_opt_in_and_python_only(self):
        section = self.text.split("## Best-of-3 Mode", 1)[1].split("\n## ", 1)[0]
        self.assertIn("never chosen automatically", section)
        self.assertIn("Python", section)
        self.assertIn("--delete-branch", section)
        self.assertIn("--timeout 900", section)

    def test_audit_skills_no_longer_say_they_are_skipped_in_lite(self):
        for rel in ("skills/triad-audit/SKILL.md", "skills/sota-web-scout/SKILL.md", "rules/ORCHESTRATOR.md"):
            with self.subTest(file=rel):
                text = read(rel)
                self.assertNotIn("skipped in `/invoke-swarm lite` mode", text)
                self.assertNotIn("skipped in Lite Mode", text)


class ReviewerContractTest(unittest.TestCase):
    def setUp(self):
        self.text = read("skills/discriminator-gate/SKILL.md")

    def test_restatement_comes_before_the_verdicts(self):
        restate = self.text.find("## Step 1.5: Restate the Requirement")
        verdict = self.text.find("Verdict Part 1")
        self.assertGreater(restate, 0)
        self.assertLess(restate, verdict)

    def test_reviewer_never_writes_to_the_workspace(self):
        self.assertIn("NEVER CREATES, COPIES OR CHANGES FILES IN THE WORKSPACE", self.text)

    def test_reviewer_gets_the_spec_path(self):
        self.assertIn("the spec it judges against", self.text)
        self.assertNotIn("The exact task specification", self.text)


class ReadmeSkillsTest(unittest.TestCase):
    def setUp(self):
        lines = read("README.md").splitlines()
        catalogue = [l for l in lines if re.match(r"^### \d+\.\d+[a-z]? `/", l) or l.startswith("| **`/")]
        self.named = set(re.findall(r"`/([a-z0-9-]+)`", "\n".join(catalogue)))

    def test_every_skill_folder_is_in_the_readme(self):
        folders = {p.parent.name for p in REPO.glob("skills/*/SKILL.md")}
        self.assertEqual(folders - self.named, set())

    def test_every_skill_in_the_readme_exists(self):
        existing = {p.parent.name for p in REPO.glob("skills/*/SKILL.md")} | {p.parent.name for p in REPO.glob("extras/*/SKILL.md")}
        self.assertEqual(self.named - existing, set())

    def test_readme_no_longer_calls_full_mode_the_default(self):
        text = read("README.md")
        self.assertNotIn("**Full Mode (`/invoke-swarm`):**", text)
        self.assertIn("Elephant-Goldfish Model", text)


PERSONA_MODES = {
    "zoom-out": ("REVIEW", "BRAINSTORM"),
    "comprehension": ("REVIEW", "BRAINSTORM"),
    "design-critic": ("REVIEW", "BRAINSTORM"),
    "style": ("REVIEW",),
    "implementation-readiness": ("REVIEW", "BRAINSTORM"),
    "codebase-details": ("REVIEW", "BRAINSTORM"),
    "maintainability": ("BRAINSTORM",),
}
EDIT_INSTRUCTION_RE = re.compile(r"^\s*(?:[-*]|\d+\.)?\s*(?:\*\*)?(Edit|Write|Modify|Fix|Create|Delete)\b")


class GoldfishPersonaTest(unittest.TestCase):
    def test_personas_have_their_modes_and_start_with_the_rules(self):
        for name, modes in PERSONA_MODES.items():
            with self.subTest(persona=name):
                text = read(f"skills/goldfish-review/personas/{name}.md")
                self.assertTrue(text.startswith("Read `_rules.md` in this folder first."))
                headings = set(re.findall(r"^## (REVIEW|BRAINSTORM)\s*$", text, re.MULTILINE))
                self.assertEqual(headings, set(modes))

    def test_no_persona_tells_the_reviewer_to_edit_files(self):
        folder = REPO / "skills" / "goldfish-review" / "personas"
        for path in sorted(folder.glob("*.md")):
            for line in path.read_text(encoding="utf-8").splitlines():
                with self.subTest(file=path.name, line=line[:40]):
                    self.assertIsNone(EDIT_INSTRUCTION_RE.match(line))

    def test_comprehension_restatement_headings(self):
        text = read("skills/goldfish-review/personas/comprehension.md")
        self.assertIn("**What this proposes**", text)
        self.assertIn("**How the existing system works, per this document**", text)

    def test_standards_exist(self):
        for name in ("zoom-out", "feature-spec", "implementation-readiness"):
            with self.subTest(standard=name):
                self.assertTrue((REPO / "skills" / "goldfish-review" / "standards" / f"{name}.md").is_file())

    def test_review_skill_names_only_existing_personas_and_standards(self):
        text = read("skills/goldfish-review/SKILL.md")
        personas = set(re.findall(r"`([a-z-]+)` → ", text))
        standards = set(re.findall(r" → `([a-z-]+)`", text))
        self.assertEqual(personas, {"zoom-out", "comprehension", "design-critic", "style", "implementation-readiness", "codebase-details"})
        for name in personas | {"maintainability"}:
            self.assertTrue((REPO / "skills" / "goldfish-review" / "personas" / f"{name}.md").is_file(), name)
        for name in standards:
            self.assertTrue((REPO / "skills" / "goldfish-review" / "standards" / f"{name}.md").is_file(), name)

    def test_review_skill_keeps_its_safeguards(self):
        text = read("skills/goldfish-review/SKILL.md")
        self.assertIn("no reading list", text)
        self.assertIn("skipped: no plan", text)
        self.assertIn("No edit to the document happens before that answer", text)
        self.assertIn("enable_write_tools=False", text)

    def test_design_template_imports_cleanly(self):
        import sys
        import tempfile

        sys.path.insert(0, str(REPO / "scripts"))
        import goal_loop

        with tempfile.TemporaryDirectory() as tmp:
            res = goal_loop.import_design(str(REPO / "skills/design-draft/template.md"), cwd=tmp, dry_run=True)
        self.assertEqual(res["status"], "OK", res["errors"])
        self.assertEqual([t["id"] for t in res["tasks"]], ["DEMO-1"])

    def test_design_draft_waits_for_the_user(self):
        text = read("skills/design-draft/SKILL.md")
        self.assertIn("Change nothing on your own", text)
        self.assertIn("--dry-run", text)
        self.assertIn("confirm them", text)

    def test_planning_skills_take_tasks_from_the_design(self):
        coop = read("skills/coop-brainstorm/SKILL.md")
        discovery = read("skills/product-discovery/SKILL.md")
        for text in (coop, discovery):
            self.assertIn("--import-design", text)
            self.assertNotIn("docs/ARCHITECTURE.md", text)
            self.assertNotIn("--add-task", text)
        for persona in ("zoom-out", "comprehension", "design-critic", "implementation-readiness", "codebase-details", "maintainability"):
            self.assertIn(f"`{persona}`", coop)
        self.assertNotIn("--verify-blueprint", coop)

    def test_goldfish_agent_is_read_only(self):
        text = read("agents/goldfish.md")
        tools = re.search(r"^tools:\s*(.+)$", text, re.MULTILINE).group(1)
        self.assertEqual({t.strip() for t in tools.split(",")}, {"Read", "Grep", "Glob"})


if __name__ == "__main__":
    unittest.main()
