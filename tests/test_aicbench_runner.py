"""Runner metrics, the missing-key exit, and a stubbed Claude Code comparison."""
from pathlib import Path
from contextlib import redirect_stderr
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.aicbench.catalog import load_catalog
from benchmarks.aicbench.metrics import cost_from_payload, pass_at_k, usage_from_payload
from benchmarks.aicbench.runner import (
    EXIT_NO_KEY,
    EXIT_USAGE,
    UNOFFICIAL_WARNING,
    RunnerError,
    _api_key,
    _command,
    build_report,
    container_command,
    main,
    require_official,
)

STUB = '''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, "__REPO__")
from benchmarks.aicbench.catalog import load_catalog
from benchmarks.aicbench.grading import overlay_reference

args = sys.argv
add_dirs = [args[index + 1] for index, arg in enumerate(args) if arg == "--add-dir"]
prompt = next(arg for arg in args if "Task id:" in arg)
task_id = prompt.split("Task id:", 1)[1].splitlines()[0].strip()
record = {
    "add_dirs": add_dirs,
    "skill": [(Path(directory) / ".claude" / "skills" / "aic" / "SKILL.md").is_file() for directory in add_dirs],
    "names_skill": "SKILL.md" in prompt,
    "task": task_id,
    "cwd": os.getcwd(),
    "repo_env": os.environ.get("AICBENCH_REPO"),
}
with Path("__LOG__").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\\n")
catalog = {item.id: item for item in load_catalog()}
overlay_reference(catalog[task_id], Path.cwd())
print(json.dumps({
    "result": "edited",
    "total_cost_usd": 0.125,
    "usage": {"input_tokens": 1000, "output_tokens": 250, "cache_read_input_tokens": 20},
    "session_id": "stub-session",
}))
'''


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def _environ(self, key):
        env = os.environ.copy()
        if key is None:
            env.pop('ANTHROPIC_API_KEY', None)
        else:
            env['ANTHROPIC_API_KEY'] = key
        env['AICBENCH_REPO'] = str(ROOT)
        env['AICBENCH_ARGV_LOG'] = str(self.base / 'argv.jsonl')
        return env

    def _stub(self, body=None):
        script = (body or STUB).replace('__LOG__', str(self.base / 'argv.jsonl')).replace('__REPO__', str(ROOT))
        path = self.base / 'claude'
        path.write_text(script, encoding='utf-8')
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def test_pass_at_1_and_reported_usage_are_not_invented(self):
        self.assertEqual(pass_at_k(1, 1, 1), 1.0)
        self.assertEqual(pass_at_k(1, 0, 1), 0.0)
        self.assertEqual(pass_at_k(5, 2, 1), 0.4)
        self.assertIsNone(cost_from_payload({'usage': {'input_tokens': 10, 'output_tokens': 2}}))
        self.assertIsNone(usage_from_payload({'total_cost_usd': 1}))
        self.assertEqual(usage_from_payload({'usage': {'input_tokens': 3, 'output_tokens': 4}})['input_tokens'], 3)
        self.assertIsNone(_api_key({'ANTHROPIC_API_KEY': '   '}))

    def test_baseline_argv_omits_the_skill_directory(self):
        baseline = _command('claude', 'Task id: example', max_turns=4, model=None, skill_root=None)
        treated = _command('claude', 'Task id: example', max_turns=4, model=None, skill_root=self.base)
        self.assertIn('--bare', baseline)
        self.assertIn('--output-format', baseline)
        self.assertIn('json', baseline)
        self.assertNotIn('--add-dir', baseline)
        self.assertEqual(treated[treated.index('--add-dir') + 1], str(self.base))

    def test_missing_key_exits_3_without_starting_a_process(self):
        stub = self._stub()
        marker = self.base / 'argv.jsonl'
        code = main(['--claude-bin', str(stub), '--tasks', 'bugfix-ledger-signs', '--output', str(self.base / 'out.json')], self._environ(None))
        self.assertEqual(code, EXIT_NO_KEY)
        self.assertFalse(marker.exists())
        self.assertFalse((self.base / 'out.json').exists())
        blank = main(['--claude-bin', str(stub), '--output', str(self.base / 'blank.json')], self._environ('  \n'))
        self.assertEqual(blank, EXIT_NO_KEY)

    def test_stubbed_comparison_records_pass_rate_tokens_cost_and_time(self):
        stub = self._stub()
        key = 'sk-ant-aicbench-sentinel'
        output = self.base / 'report.json'
        code = main(
            ['--claude-bin', str(stub), '--tasks', 'bugfix-ledger-signs', '--samples', '1', '--output', str(output)],
            self._environ(key),
        )
        self.assertEqual(code, 0, output.read_text(encoding='utf-8') if output.exists() else 'no report')
        report = json.loads(output.read_text(encoding='utf-8'))
        self.assertNotIn(key, output.read_text(encoding='utf-8'))
        self.assertEqual(report['benchmark'], 'aicbench')
        self.assertTrue(report['measured'])
        self.assertEqual(report['sandbox'], 'none')
        self.assertIs(report['official'], False)
        self.assertEqual(report['publication_warning'], UNOFFICIAL_WARNING)
        with self.assertRaises(RunnerError):
            require_official(report)
        forged = dict(report)
        forged['official'] = True
        forged['publication_warning'] = None
        with self.assertRaises(RunnerError):
            require_official(forged)
        for arm in ('baseline', 'claude_code_plus_aic'):
            summary = report['arms'][arm]
            self.assertEqual(summary['pass_at_1'], 1.0)
            self.assertEqual(summary['tokens']['input_tokens'], 1000)
            self.assertEqual(summary['tokens']['output_tokens'], 250)
            self.assertEqual(summary['tokens']['cache_read_input_tokens'], 20)
            self.assertIsNone(summary['tokens']['cache_creation_input_tokens'])
            self.assertEqual(summary['cost_usd'], '0.125')
            self.assertGreaterEqual(summary['wall_time_seconds'], 0)
            self.assertEqual(report['tasks'][0][arm]['samples'][0]['session_id'], 'stub-session')
        lines = [json.loads(line) for line in (self.base / 'argv.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([line['names_skill'] for line in lines], [False, True])
        self.assertEqual(lines[0]['add_dirs'], [])
        self.assertEqual(lines[1]['skill'], [True])
        self.assertIsNone(lines[0]['repo_env'])
        self.assertIsNone(lines[1]['repo_env'])
        for line in lines:
            cwd = Path(line['cwd']).resolve()
            self.assertFalse(cwd.is_relative_to(ROOT.resolve()))
            self.assertNotIn('reference', cwd.parts)
            self.assertNotIn('oracle', cwd.parts)
            for directory in line['add_dirs']:
                self.assertFalse(Path(directory).resolve().is_relative_to(ROOT.resolve()))

    def test_symlinked_process_temp_does_not_block_the_managed_install(self):
        real = self.base / 'real-temp'
        real.mkdir()
        link = self.base / 'link-temp'
        link.symlink_to(real, target_is_directory=True)
        stub = self._stub()
        output = self.base / 'linked-temp.json'
        errors = io.StringIO()
        with patch('benchmarks.aicbench.runner.tempfile.tempdir', str(link)), redirect_stderr(errors):
            code = main(
                ['--claude-bin', str(stub), '--tasks', 'bugfix-ledger-signs', '--output', str(output)],
                self._environ('sk-ant-present'),
            )
        self.assertEqual(code, 0, errors.getvalue() or 'no diagnostic')
        self.assertTrue(output.is_file())

    def test_tampered_oracle_marks_the_run_invalid(self):
        task = next(item for item in load_catalog() if item.id == 'bugfix-ledger-signs')
        original = task.oracle.read_bytes()
        oracle = repr(str(task.oracle))
        script = '\n'.join([
            '#!/usr/bin/env python3',
            'import json',
            'from pathlib import Path',
            f'Path({oracle}).write_text("import sys\\nsys.exit(0)\\n", encoding="utf-8")',
            'print(json.dumps({"result": "tampered", "total_cost_usd": 0.01, '
            '"usage": {"input_tokens": 1, "output_tokens": 1}, "session_id": "tamper"}))',
            '',
        ])
        stub = self._stub(script)
        output = self.base / 'tamper.json'
        try:
            code = main(
                ['--claude-bin', str(stub), '--tasks', 'bugfix-ledger-signs', '--output', str(output)],
                self._environ('sk-ant-present'),
            )
            self.assertEqual(code, 0, output.read_text(encoding='utf-8') if output.exists() else 'no report')
            report = json.loads(output.read_text(encoding='utf-8'))
            for arm in ('baseline', 'claude_code_plus_aic'):
                arm_report = report['tasks'][0][arm]
                self.assertTrue(arm_report['invalid'])
                self.assertFalse(arm_report['passed'])
                self.assertEqual(arm_report['pass_at_1'], 0.0)
                sample = arm_report['samples'][0]
                self.assertTrue(sample['invalid'])
                self.assertFalse(sample['passed'])
                self.assertFalse(sample['grade_passed'])
                self.assertIn('integrity', sample['harness_error'])
        finally:
            task.oracle.write_bytes(original)

    def test_container_command_does_not_mount_the_repository(self):
        workspace = Path('/tmp/aicbench-ws')
        argv = container_command(
            ['claude', '-p', 'hi'],
            workspace=workspace,
            skill_root=Path('/tmp/aicbench-skill'),
            home=Path('/tmp/aicbench-home'),
            config=Path('/tmp/aicbench-config'),
            binary=Path('/usr/bin/claude'),
            repo=ROOT,
        )
        self.assertNotIn(str(ROOT.resolve()), argv)
        self.assertIn(str(workspace.resolve()), argv)
        self.assertIn('--ro-bind', argv)
        if shutil.which('bwrap') is None:
            code = main(
                ['--sandbox', 'container', '--claude-bin', '/bin/true', '--tasks', 'bugfix-ledger-signs',
                 '--output', str(self.base / 'sand.json')],
                self._environ('sk-ant-present'),
            )
            self.assertEqual(code, EXIT_USAGE)
            self.assertFalse((self.base / 'sand.json').exists())

    def test_only_container_runs_can_be_official(self):
        unofficial = build_report((), (), {}, samples=1, sandbox='none')
        self.assertIs(unofficial['official'], False)
        self.assertIn('NOT AN OFFICIAL RESULT', unofficial['publication_warning'])
        with self.assertRaises(RunnerError):
            require_official(unofficial)
        official = build_report((), (), {}, samples=1, sandbox='container')
        self.assertIs(official['official'], True)
        self.assertIsNone(official['publication_warning'])
        self.assertEqual(official['sandbox'], 'container')
        require_official(official)
        stub = self._stub()
        output = self.base / 'official.json'
        errors = io.StringIO()
        with redirect_stderr(errors):
            refused = main(
                ['--official', '--claude-bin', str(stub), '--tasks', 'bugfix-ledger-signs', '--output', str(output)],
                self._environ('sk-ant-present'),
            )
        self.assertEqual(refused, EXIT_USAGE)
        self.assertIn('NOT AN OFFICIAL RESULT', errors.getvalue())
        self.assertIn('--sandbox container', errors.getvalue())
        self.assertFalse(output.exists())
        self.assertFalse((self.base / 'argv.jsonl').exists())
        missing_key = main(
            ['--official', '--claude-bin', str(stub), '--output', str(self.base / 'no-key.json')],
            self._environ(None),
        )
        self.assertEqual(missing_key, EXIT_NO_KEY)
        saved = self.base / 'saved.json'
        saved.write_text(json.dumps(unofficial), encoding='utf-8')
        checked = main(['--require-official', str(saved)], self._environ(None))
        self.assertEqual(checked, EXIT_USAGE)

    def test_unknown_task_is_a_usage_error(self):
        code = main(
            ['--claude-bin', '/bin/true', '--tasks', 'not-a-task', '--output', str(self.base / 'bad.json')],
            self._environ('sk-ant-present'),
        )
        self.assertEqual(code, EXIT_USAGE)


if __name__ == '__main__':
    unittest.main()
