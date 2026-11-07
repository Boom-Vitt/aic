"""The sandbox pipeline smoke is an offline stub, not a model result."""
from pathlib import Path
from contextlib import redirect_stderr
import io
import json
import os
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.aicbench.catalog import load_catalog
from benchmarks.aicbench.runner import EXIT_USAGE, UNOFFICIAL_WARNING, RunnerError, main, require_official

STUB = ROOT / 'benchmarks' / 'aicbench' / 'stub' / 'agent.py'
RESULTS = ROOT / 'benchmarks' / 'aicbench' / 'RESULTS.md'
MODEL_KEYS = ('pass_at_1', 'tokens', 'cost_usd', 'arms', 'usage', 'total_cost_usd', 'samples')


def _oracle_bytes():
    task = next(item for item in load_catalog() if item.id == 'bugfix-ledger-signs')
    return task.oracle.read_bytes()


class PipelineSmokeTests(unittest.TestCase):
    def setUp(self):
        self.oracle_before = _oracle_bytes()
        self.addCleanup(self._restore_oracle)

    def _restore_oracle(self):
        task = next(item for item in load_catalog() if item.id == 'bugfix-ledger-signs')
        if task.oracle.read_bytes() != self.oracle_before:
            task.oracle.write_bytes(self.oracle_before)

    def _environ(self):
        env = os.environ.copy()
        env.pop('ANTHROPIC_API_KEY', None)
        env['ANTHROPIC_API_KEY'] = 'sk-ant-pipeline-smoke-sentinel'
        env['PYTHONPATH'] = str(ROOT)
        env['AICBENCH_REPO'] = str(ROOT)
        return env

    def _run(self, sandbox):
        target = Path(os.environ.get('TMPDIR', '/tmp')) / f'aicbench-{sandbox}-{os.getpid()}.json'
        self.addCleanup(lambda: target.unlink(missing_ok=True))
        errors = io.StringIO()
        with redirect_stderr(errors):
            code = main(
                ['--pipeline-smoke', '--sandbox', sandbox, '--output', str(target)],
                self._environ(),
            )
        return code, target, errors.getvalue()

    def _assert_smoke_shape(self, report, text):
        self.assertEqual(report['kind'], 'pipeline-smoke')
        self.assertEqual(report['label'], 'pipeline smoke test')
        self.assertIs(report['measured'], False)
        self.assertIs(report['invokes_model'], False)
        self.assertIs(report['model_result'], False)
        self.assertEqual(report['agent'], 'benchmarks/aicbench/stub/agent.py')
        self.assertIs(report['ok'], True)
        self.assertNotIn('sk-ant-pipeline-smoke-sentinel', text)
        self.assertIs(report['checks']['api_key_forwarded'], False)
        self.assertIs(report['checks']['tamper_detected'], True)
        self.assertIs(report['checks']['grading_works'], True)
        self.assertEqual(report['task_graded'], 'bugfix-ledger-signs')
        for key in MODEL_KEYS:
            self.assertNotIn(key, report)
        self.assertEqual(_oracle_bytes(), self.oracle_before)

    def test_stub_refuses_to_run_as_a_model(self):
        completed = subprocess.run(
            [sys.executable, str(STUB)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn('pipeline smoke test', completed.stderr)
        self.assertIn('not a model', completed.stderr)
        self.assertEqual(completed.stdout, '')

    def test_unsandboxed_smoke_can_read_hidden_files_and_is_not_official(self):
        code, target, errors = self._run('none')
        self.assertEqual(code, 0, errors)
        text = target.read_text(encoding='utf-8')
        report = json.loads(text)
        self._assert_smoke_shape(report, text)
        self.assertEqual(report['sandbox'], 'none')
        self.assertIs(report['official'], False)
        self.assertEqual(report['publication_warning'], UNOFFICIAL_WARNING)
        self.assertIs(report['checks']['reference_unreadable'], False)
        self.assertIs(report['checks']['oracle_unreadable'], False)
        self.assertIn('not a model result', errors)
        self.assertIn('NOT AN OFFICIAL RESULT', errors)
        with self.assertRaises(RunnerError):
            require_official(report)
        checked_errors = io.StringIO()
        with redirect_stderr(checked_errors):
            checked = main(['--require-official', str(target)], self._environ())
        self.assertEqual(checked, EXIT_USAGE)
        self.assertIn('NOT AN OFFICIAL RESULT', checked_errors.getvalue())

    def test_official_flag_does_not_turn_the_smoke_into_a_model_result(self):
        errors = io.StringIO()
        with redirect_stderr(errors):
            code = main(['--pipeline-smoke', '--sandbox', 'container', '--official'], self._environ())
        self.assertEqual(code, EXIT_USAGE)
        self.assertIn('not a model result', errors.getvalue())
        self.assertEqual(_oracle_bytes(), self.oracle_before)

    def test_results_file_does_not_tabulate_the_stub(self):
        text = RESULTS.read_text(encoding='utf-8')
        self.assertIn('pipeline smoke test', text)
        self.assertIn('not a model result', text)
        for line in text.splitlines():
            if line.startswith('|') and ('stub/agent.py' in line or 'pipeline smoke' in line):
                self.fail(f'stub entered a results table: {line}')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap is not installed')
    def test_container_hides_reference_and_oracle_and_is_official(self):
        code, target, errors = self._run('container')
        self.assertEqual(code, 0, errors)
        text = target.read_text(encoding='utf-8')
        report = json.loads(text)
        self._assert_smoke_shape(report, text)
        self.assertEqual(report['sandbox'], 'container')
        self.assertIs(report['official'], True)
        self.assertIsNone(report['publication_warning'])
        self.assertIs(report['checks']['reference_unreadable'], True)
        self.assertIs(report['checks']['oracle_unreadable'], True)
        require_official(report)
        forged = dict(report)
        forged['measured'] = True
        with self.assertRaises(RunnerError):
            require_official(forged)
        checked_errors = io.StringIO()
        with redirect_stderr(checked_errors):
            checked = main(['--require-official', str(target)], {})
        self.assertEqual(checked, 0, checked_errors.getvalue())
        self.assertIn('pipeline smoke test, not a model result', checked_errors.getvalue())


if __name__ == '__main__':
    unittest.main()
