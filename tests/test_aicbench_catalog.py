"""Catalog contract for the original aicbench tasks."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.aicbench.catalog import CATEGORIES, load_catalog

EXPECTED = (
    'bugfix-csv-roundtrip',
    'bugfix-config-layers',
    'bugfix-interval-merge',
    'bugfix-ledger-signs',
    'bugfix-path-allowlist',
    'bugfix-retry-budget',
    'bugfix-session-expiry',
    'docs-api-inventory',
    'docs-cli-reference',
    'docs-rate-limiter',
    'docs-state-machine',
    'feature-cursor-page',
    'feature-duration',
    'feature-redact',
    'feature-ring-buffer',
    'feature-semver',
    'feature-slug',
    'refactor-billing-package',
    'refactor-discount-registry',
    'refactor-shared-email',
    'refactor-typed-errors',
)


class CatalogTests(unittest.TestCase):
    def test_catalog_covers_the_four_kinds_of_aic_work(self):
        tasks = load_catalog()
        self.assertEqual([task.id for task in tasks], sorted(EXPECTED))
        self.assertEqual(len(tasks), len(set(EXPECTED)))
        self.assertGreaterEqual(len(tasks), 20)
        counts = {category: 0 for category in CATEGORIES}
        for task in tasks:
            counts[task.category] += 1
            self.assertGreaterEqual(task.instruction.find('Acceptance'), 0)
            self.assertNotIn('AICBENCH_ORACLE', task.instruction)
            self.assertNotIn('oracle/', task.instruction)
            self.assertNotIn('reference/', task.instruction)
            oracle = task.oracle.read_text(encoding='utf-8')
            self.assertIn('AICBENCH_ORACLE', oracle)
            ast.parse(oracle)
            for tree in (task.workspace, task.reference):
                for path in tree.rglob('*'):
                    if '__pycache__' in path.parts:
                        continue
                    self.assertFalse(path.is_symlink(), path)
                    if path.suffix == '.py':
                        ast.parse(path.read_text(encoding='utf-8'))
                    if path.is_file():
                        self.assertNotIn('AICBENCH_ORACLE', path.read_text(encoding='utf-8', errors='replace'))
        self.assertGreaterEqual(counts['bugfix'], 4)
        self.assertGreaterEqual(counts['feature'], 4)
        self.assertGreaterEqual(counts['refactor'], 4)
        self.assertGreaterEqual(counts['docs'], 4)


if __name__ == '__main__':
    unittest.main()
