"""Prove every aicbench task fails unsolved, passes when solved, and hides the oracle."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.aicbench.catalog import load_catalog
from benchmarks.aicbench.grading import grade, grade_env, prepare_workspace


def _files(directory: Path) -> set[str]:
    files = set()
    for path in directory.rglob('*'):
        if '__pycache__' in path.parts or not path.is_file():
            continue
        files.add(path.relative_to(directory).as_posix())
    return files


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_reference_passes_and_the_starting_tree_fails(self):
        previous = os.environ.get('ANTHROPIC_API_KEY')
        os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-should-not-reach-the-oracle'

        def restore_key():
            if previous is None:
                os.environ.pop('ANTHROPIC_API_KEY', None)
            else:
                os.environ['ANTHROPIC_API_KEY'] = previous

        self.addCleanup(restore_key)
        for task in load_catalog():
            with self.subTest(task=task.id):
                start = self.base / task.id / 'start'
                solved = self.base / task.id / 'solved'
                prepare_workspace(task, start, solution=False)
                prepare_workspace(task, solved, solution=True)
                self.assertNotIn('ANTHROPIC_API_KEY', grade_env(start))
                self.assertEqual(_files(start), _files(task.workspace))
                self.assertFalse(any('oracle' in path.parts for path in start.rglob('*')))
                self.assertIn(task.oracle.name, {'test_oracle.py'})
                self.assertFalse(str(task.oracle).startswith(str(start)))
                unsolved = grade(task, start)
                reference = grade(task, solved)
                self.assertFalse(unsolved.passed, unsolved.detail)
                self.assertTrue(reference.passed, reference.detail)
                self.assertFalse(reference.timed_out)
                self.assertEqual(reference.returncode, 0)
                self.assertNotIn('ERROR', reference.detail)

    def test_a_partial_ledger_fix_still_fails(self):
        task = next(item for item in load_catalog() if item.id == 'bugfix-ledger-signs')
        workspace = self.base / 'partial'
        prepare_workspace(task, workspace, solution=True)
        shutil.copyfile(task.workspace / 'ledger' / 'totals.py', workspace / 'ledger' / 'totals.py')
        result = grade(task, workspace)
        self.assertFalse(result.passed, result.detail)


if __name__ == '__main__':
    unittest.main()
