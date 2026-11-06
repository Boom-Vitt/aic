"""Validate the published and installed skill format as a consumer contract."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/aic'
sys.path.insert(0, str(SKILL / 'scripts'))
from aiclib.memory import validate_handoff
from aiclib.routing import validate_plan


class PackageTests(unittest.TestCase):
    def test_skill_metadata_and_resources_form_a_portable_self_contained_package(self):
        text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\n'))
        frontmatter, body = text[4:].split('\n---\n', 1)
        name = re.search(r'^name: (.+)$', frontmatter, re.M).group(1)
        description = re.search(r'^description: (.+)$', frontmatter, re.M).group(1)
        self.assertEqual(name, SKILL.name)
        self.assertRegex(name, r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
        self.assertLessEqual(len(name), 64)
        self.assertTrue(1 <= len(description) <= 1024)
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', body):
            if '://' not in target:
                resolved = (SKILL / target.split('#', 1)[0]).resolve()
                self.assertTrue(resolved.is_relative_to(SKILL.resolve()), target)
                self.assertTrue(resolved.is_file(), target)
        self.assertTrue((SKILL / 'LICENSE.txt').is_file())
        self.assertEqual((SKILL / 'LICENSE.txt').read_bytes(), (ROOT / 'LICENSE').read_bytes())

    def test_published_examples_validate_as_read_only_recommendations_and_handoffs(self):
        plan = json.loads((SKILL / 'assets/example-plan.json').read_text())
        checked = validate_plan(plan)
        self.assertEqual(checked['next_action'], 'recommend')
        self.assertIs(checked['approval_required'], True)
        handoff = json.loads((SKILL / 'assets/example-handoff.json').read_text())
        self.assertEqual(validate_handoff(handoff)['uncertain_actions'], [])

    def test_documentation_relative_links_resolve_within_the_distribution(self):
        files = [ROOT / name for name in ('README.md', 'CONTRIBUTING.md', 'SECURITY.md')]
        files += list((ROOT / 'docs').glob('*.md'))
        files += list((SKILL / 'references').rglob('*.md'))
        for file in files:
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', file.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):
                    continue
                path = (file.parent / target.split('#', 1)[0]).resolve()
                with self.subTest(file=file.name, target=target):
                    self.assertTrue(path.is_relative_to(ROOT.resolve()))
                    self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
