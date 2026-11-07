"""Consumer checks for the offline skill-lint metric."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.skill_lint import LintError, lint_path, parse_skill_text
from benchmarks.skill_lint.corpus import LicenseError, assert_permissive_license


DESCRIPTION = "Extract notes from a repository. Use when the user asks for a summary of the notes."


def _skill(root: Path, name: str, description: str = DESCRIPTION, extra: str = "", body: str = "# Notes\n") -> Path:
    skill = root / name
    skill.mkdir(parents=True, exist_ok=True)
    text = f"---\nname: {name}\ndescription: {description}\n{extra}---\n{body}"
    (skill / "SKILL.md").write_text(text, encoding="utf-8")
    return skill


class SkillLintTests(unittest.TestCase):
    def setUp(self):
        self._work = ROOT / ".work"
        self._work.mkdir(exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=self._work)
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_skill_scores_100_and_a_direct_skill_file_selects_its_directory(self):
        skill = _skill(self.root, "alpha")
        (skill / "references").mkdir()
        (skill / "references" / "notes.md").write_text("# Notes\n", encoding="utf-8")
        entry = skill / "SKILL.md"
        entry.write_text(
            entry.read_text(encoding="utf-8") + "\nSee [notes](references/notes.md).\n",
            encoding="utf-8",
        )
        report = lint_path(entry)
        self.assertEqual([item.path for item in report.skills], ["."])
        skill_report = report.skills[0]
        self.assertEqual(skill_report.name, "alpha")
        self.assertEqual(skill_report.findings, ())
        self.assertTrue(skill_report.format_pass)
        self.assertEqual(skill_report.score, 100)
        self.assertEqual(report.mean_score, "100.00")
        self.assertEqual(report.to_dict(summary=True)["format_pass_rate"], "1.0000")

    def test_folded_description_preserves_trigger_text_and_literal_clip_keeps_one_newline(self):
        folded = parse_skill_text(
            "---\n"
            "name: alpha\n"
            "description: >-\n"
            "  Extract notes from a repository and list the open questions.\n"
            "  Use when the user asks for a summary.\n"
            "---\n"
            "# Alpha\n"
        )
        self.assertEqual(
            folded.fields["description"],
            "Extract notes from a repository and list the open questions. Use when the user asks for a summary.",
        )
        literal = parse_skill_text(
            "---\n"
            "name: alpha\n"
            "description: |\n"
            "  Extract notes.\n"
            "  Use when the user asks.\n"
            "---\n"
        )
        self.assertEqual(literal.fields["description"], "Extract notes.\nUse when the user asks.\n")

    def test_frontmatter_contract_rejects_names_fields_and_description_limits(self):
        skill = self.root / "actual"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\n"
            "name: other\n"
            "description: <file> Extract notes. Use when the user asks for notes about the repository.\n"
            "version: \"1\"\n"
            "compatibility: \"\"\n"
            "allowed-tools: [Read]\n"
            "metadata:\n"
            "  tags: [one, two]\n"
            "---\n"
            "# Actual\n",
            encoding="utf-8",
        )
        rules = {finding.rule for finding in lint_path(skill).skills[0].findings}
        self.assertIn("name-directory", rules)
        self.assertIn("xml-tag", rules)
        self.assertIn("field-unknown", rules)
        self.assertIn("compatibility-length", rules)
        self.assertIn("allowed-tools-type", rules)
        self.assertIn("metadata-value", rules)

        long_name = "n" * 65
        long_skill = _skill(self.root, long_name, description="x" * 1025)
        long_rules = {finding.rule for finding in lint_path(long_skill).skills[0].findings}
        self.assertIn("name-length", long_rules)
        self.assertIn("description-length", long_rules)

        hyphen = _skill(self.root, "bad--name")
        self.assertTrue(
            any(finding.rule == "name-consecutive-hyphens" for finding in lint_path(hyphen).skills[0].findings)
        )
        reserved = _skill(self.root, "claude-helper")
        self.assertTrue(
            any(finding.rule == "name-reserved" for finding in lint_path(reserved).skills[0].findings)
        )
        broken = self.root / "plain"
        broken.mkdir()
        (broken / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")
        self.assertTrue(
            any(finding.rule == "frontmatter-invalid" for finding in lint_path(broken).skills[0].findings)
        )

    def test_trigger_person_and_terse_descriptions_are_warnings(self):
        terse = _skill(self.root, "terse", description="Helps with PDFs.")
        terse_rules = {finding.rule for finding in lint_path(terse).skills[0].findings}
        self.assertIn("description-terse", terse_rules)
        self.assertIn("description-trigger", terse_rules)
        self.assertNotIn("description-length", terse_rules)

        person = _skill(
            self.root,
            "person",
            description="You should use this when reviewing pull requests from the team.",
        )
        person_report = lint_path(person).skills[0]
        self.assertEqual(
            [finding.rule for finding in person_report.findings],
            ["description-person"],
        )
        self.assertTrue(person_report.format_pass)
        self.assertEqual(person_report.score, 95)

    def test_relative_references_escape_and_non_paths_are_distinguished(self):
        skill = _skill(self.root, "alpha")
        (skill / "references").mkdir()
        (skill / "references" / "ok.md").write_text("# OK\n", encoding="utf-8")
        outside = self.root / "outside.md"
        outside.write_text("OUTSIDE-MARKER\n", encoding="utf-8")
        (skill / "linked.md").symlink_to(outside)
        entry = skill / "SKILL.md"
        entry.write_text(
            entry.read_text(encoding="utf-8")
            + "\n".join(
                [
                    "See [ok](references/ok.md) and [missing](references/missing.md).",
                    "Run `scripts/missing.py` after reading [Widget.propertyName](Widget.propertyName).",
                    "See [out](../outside.md) and [abs](/tmp/outside.md) and [link](linked.md).",
                    "```",
                    "[fenced](scripts/not-real.py)",
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        report = lint_path(skill)
        blob = json.dumps(report.to_dict(summary=False))
        rules = [finding.rule for finding in report.skills[0].findings]
        self.assertIn("missing-reference", rules)
        self.assertIn("link-escapes", rules)
        self.assertIn("symlink-reference", rules)
        self.assertIn("absolute-reference", rules)
        self.assertNotIn("scripts/not-real.py", blob)
        self.assertNotIn("Widget.propertyName", blob)
        self.assertNotIn("OUTSIDE-MARKER", blob)
        self.assertNotIn("references/ok.md", " ".join(finding.message for finding in report.skills[0].findings))

    def test_secret_findings_do_not_echo_material_or_leave_the_skill(self):
        skill = _skill(self.root, "alpha")
        token = "AKIA" + "0123456789ABCDEF"
        material = "THISMATERIAL"
        placeholder = "AKIAIOSFODNN7EXAMPLE"
        (skill / "notes.md").write_text(f"token {token}\n", encoding="utf-8")
        (skill / "key.pem").write_text(
            f"-----BEGIN PRIVATE KEY-----\n{material}\n-----END PRIVATE KEY-----\n",
            encoding="utf-8",
        )
        (skill / "docs.md").write_text(f"example {placeholder}\n", encoding="utf-8")
        (skill / ".env").write_text("MODE=demo\n", encoding="utf-8")
        sibling = self.root / "notes"
        sibling.mkdir()
        sibling_token = "AKIA" + "FEDCBA9876543210"
        (sibling / "leak.txt").write_text(sibling_token + "\n", encoding="utf-8")
        report = lint_path(self.root)
        messages = [finding.message for finding in report.skills[0].findings]
        blob = json.dumps(report.to_dict(summary=False))
        self.assertTrue(any("aws-access-key-id" in message for message in messages))
        self.assertTrue(any("private-key" in message for message in messages))
        self.assertTrue(any(finding.rule == "secret-filename" for finding in report.skills[0].findings))
        self.assertNotIn(token, blob)
        self.assertNotIn(material, blob)
        self.assertNotIn(placeholder, blob)
        self.assertNotIn(sibling_token, blob)
        self.assertNotIn("example", " ".join(message for message in messages if "aws-access-key-id" in message))

    def test_disclosure_limits_warn_on_the_published_boundaries(self):
        header = (
            "---\n"
            f"name: alpha\n"
            f"description: {DESCRIPTION}\n"
            "---\n"
        )
        short = self.root / "short"
        short.mkdir()
        (short / "SKILL.md").write_text(header + ("x\n" * 495), encoding="utf-8")
        self.assertEqual(len((short / "SKILL.md").read_text(encoding="utf-8").splitlines()), 499)
        self.assertFalse(
            any(finding.rule == "skill-line-limit" for finding in lint_path(short).skills[0].findings)
        )
        long = self.root / "long"
        long.mkdir()
        (long / "SKILL.md").write_text(header + ("x\n" * 496), encoding="utf-8")
        self.assertEqual(len((long / "SKILL.md").read_text(encoding="utf-8").splitlines()), 500)
        self.assertTrue(
            any(finding.rule == "skill-line-limit" for finding in lint_path(long).skills[0].findings)
        )
        wide = self.root / "wide"
        wide.mkdir()
        (wide / "SKILL.md").write_text(header + ("a" * 20004) + "\n", encoding="utf-8")
        wide_rules = {finding.rule for finding in lint_path(wide).skills[0].findings}
        self.assertIn("instruction-size", wide_rules)
        self.assertNotIn("skill-line-limit", wide_rules)

    def test_discovery_skips_dependency_copies_and_symlink_duplicates(self):
        _skill(self.root / "skills", "alpha")
        _skill(self.root / ".github" / "skills", "gamma")
        alias = self.root / "skills" / "beta"
        alias.symlink_to(self.root / "skills" / "alpha", target_is_directory=True)
        hidden = self.root / "node_modules" / "hidden"
        _skill(hidden, "hidden")
        git_skill = self.root / ".git" / "skills"
        _skill(git_skill, "nope")
        report = lint_path(self.root)
        self.assertEqual([item.path for item in report.skills], [".github/skills/gamma", "skills/alpha"])

    def test_repository_mean_rounds_half_up_and_lint_does_not_modify_files(self):
        _skill(self.root / "skills", "clean-a")
        _skill(self.root / "skills", "clean-b")
        broken = _skill(self.root / "skills", "broken")
        entry = broken / "SKILL.md"
        entry.write_text(
            entry.read_text(encoding="utf-8")
            + "\n".join(f"See [m{index}](missing-{index}.md)." for index in range(5))
            + "\n",
            encoding="utf-8",
        )
        before = {
            path: path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        report = lint_path(self.root)
        after = {
            path: path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        self.assertEqual(before, after)
        by_path = {item.path: item.score for item in report.skills}
        self.assertEqual(by_path["skills/clean-a"], 100)
        self.assertEqual(by_path["skills/clean-b"], 100)
        self.assertEqual(by_path["skills/broken"], 0)
        self.assertEqual(report.mean_score, "66.67")

    def test_cli_json_is_deterministic_and_exits_from_the_error_count(self):
        skill = _skill(self.root, "alpha")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-B", "-m", "benchmarks.skill_lint", str(skill), "--format", "json"]
        first = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["skill_count"], 1)
        self.assertEqual(payload["mean_score"], "100.00")
        self.assertEqual(payload["spec_revision"], "83021e2be457a9b6679148719c1f6074f0ad975e")
        entry = skill / "SKILL.md"
        entry.write_text(entry.read_text(encoding="utf-8") + "See [missing](references/missing.md).\n", encoding="utf-8")
        failed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(failed.returncode, 1)
        missing = self.root / "missing-root"
        refused = subprocess.run(
            [sys.executable, "-B", "-m", "benchmarks.skill_lint", str(missing)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(refused.returncode, 2)
        link = self.root / "alias"
        link.symlink_to(skill, target_is_directory=True)
        with self.assertRaises(LintError):
            lint_path(link)

    def test_license_gate_requires_a_regular_root_license_file(self):
        licensed = self.root / "licensed"
        licensed.mkdir()
        (licensed / "LICENSE").write_text("MIT License\nCopyright (c) Example.\n", encoding="utf-8")
        self.assertEqual(assert_permissive_license(licensed, "MIT License"), "LICENSE")
        unmarked = self.root / "unmarked"
        unmarked.mkdir()
        (unmarked / "LICENSE").write_text("All rights reserved.\n", encoding="utf-8")
        with self.assertRaises(LicenseError):
            assert_permissive_license(unmarked, "MIT License")
        linked = self.root / "linked"
        linked.mkdir()
        (linked / "LICENSE").symlink_to(licensed / "LICENSE")
        with self.assertRaises(LicenseError):
            assert_permissive_license(linked, "MIT License")

    def test_packaged_aic_skill_passes_the_format_contract(self):
        report = lint_path(ROOT)
        packaged = next(skill for skill in report.skills if skill.path == "skills/aic")
        self.assertEqual(packaged.name, "aic")
        self.assertTrue(packaged.format_pass)
        self.assertEqual(packaged.error_count, 0)
        self.assertEqual([finding.rule for finding in packaged.findings], ["nested-reference"])
        self.assertEqual(packaged.score, 95)


if __name__ == "__main__":
    unittest.main()
