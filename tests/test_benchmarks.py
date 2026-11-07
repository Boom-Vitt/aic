"""The benchmark skeleton records local exit codes and does not invent scores."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from aicbench.protocol import BenchError, same_conditions, validate_suite
from aicbench.runner import execute_suite, plan, run_smoke


def catalog():
    return json.loads((ROOT / 'benchmarks' / 'catalog.json').read_text(encoding='utf-8'))


class BenchmarkHarnessTests(unittest.TestCase):
    def test_public_suites_are_blocked_and_the_doc_claims_no_score(self):
        data = catalog()
        blocked = [item['id'] for item in data['suites'] if item['id'] != 'smoke']
        self.assertEqual(
            blocked,
            ['swe-bench-lite', 'swe-bench-verified', 'terminal-bench', 'aider-polyglot', 'real-task'],
        )
        for item in data['suites']:
            if item['id'] == 'smoke':
                self.assertTrue(item['executable'])
                self.assertFalse(item['invokes_model'])
            else:
                self.assertFalse(item['executable'])
                self.assertTrue(plan(data, item['id'])['public_benchmark_scores'] is None)
        doc = (ROOT / 'docs' / 'BENCHMARKS.md').read_text(encoding='utf-8')
        self.assertIn('No public benchmark score is claimed.', doc)
        self.assertNotIn('%', doc)

    def test_different_seeds_are_not_the_same_comparison(self):
        base = json.loads((ROOT / 'benchmarks' / 'smoke' / 'suite.json').read_text(encoding='utf-8'))
        other = json.loads(json.dumps(base))
        other['seed'] = 1
        self.assertTrue(same_conditions(base, json.loads(json.dumps(base))))
        self.assertFalse(same_conditions(base, other))

    def test_smoke_run_records_exit_codes_without_a_public_score(self):
        receipt = run_smoke(catalog(), 'smoke')
        self.assertTrue(receipt['executed'])
        self.assertFalse(receipt['invokes_model'])
        self.assertIsNone(receipt['public_benchmark_scores'])
        self.assertEqual(receipt['recorded_runs'], 2)
        self.assertEqual(receipt['exit_zero_runs'], 2)
        self.assertEqual(receipt['model'], 'none')
        self.assertEqual(receipt['seed'], 0)
        self.assertTrue(all(item['workflow_loaded'] is False for item in receipt['runs']))
        self.assertTrue(all(item['exit_code'] == 0 for item in receipt['runs']))

    def test_a_failing_local_command_is_recorded_and_not_scored(self):
        (ROOT / '.work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / '.work') as temp:
            root = Path(temp)
            task = root / 'tasks' / 'fails'
            task.mkdir(parents=True)
            (task / 'check.py').write_text('raise SystemExit(1)\n', encoding='utf-8')
            suite = {
                'schema_version': 1,
                'id': 'local-fail',
                'executable': True,
                'invokes_model': False,
                'public_benchmark': False,
                'benchmark_revision': 'local-fail-1',
                'model': 'none',
                'seed': 0,
                'budget': {'max_turns': 0, 'timeout_sec': 10, 'max_usd': 0},
                'arms': ['plain-claude-code', 'aic'],
                'tasks': [{'id': 'fails', 'cwd': 'tasks/fails', 'argv': [sys.executable, 'check.py']}],
            }
            receipt = execute_suite(suite, root)
        self.assertEqual(receipt['recorded_runs'], 2)
        self.assertEqual(receipt['exit_zero_runs'], 0)
        self.assertTrue(all(item['exit_code'] == 1 for item in receipt['runs']))
        self.assertIsNone(receipt['public_benchmark_scores'])
        self.assertNotIn('score', receipt)

    def test_model_execution_and_escaping_paths_are_rejected(self):
        suite = json.loads((ROOT / 'benchmarks' / 'smoke' / 'suite.json').read_text(encoding='utf-8'))
        suite['invokes_model'] = True
        with self.assertRaises(BenchError):
            validate_suite(suite)
        escaped = json.loads((ROOT / 'benchmarks' / 'smoke' / 'suite.json').read_text(encoding='utf-8'))
        escaped['tasks'][0]['cwd'] = '../outside'
        with self.assertRaises(BenchError):
            validate_suite(escaped)

    def test_public_cli_smoke_and_blocked_plan(self):
        (ROOT / '.work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / '.work') as temp:
            out = Path(temp) / 'receipt.json'
            ran = subprocess.run(
                [str(ROOT / 'scripts' / 'benchmark-run.sh'), 'run', '--suite', 'smoke', '--output', str(out)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stderr)
            receipt = json.loads(out.read_text(encoding='utf-8'))
            self.assertIsNone(receipt['public_benchmark_scores'])
            self.assertEqual(receipt['exit_zero_runs'], 2)
            blocked = subprocess.run(
                [str(ROOT / 'scripts' / 'benchmark-run.sh'), 'plan', '--suite', 'aider-polyglot'],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(blocked.returncode, 3)
            body = json.loads(blocked.stdout)
            self.assertFalse(body['executed'])
            self.assertIsNone(body['public_benchmark_scores'])
