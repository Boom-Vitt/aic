"""Consumer-facing CLI checks in isolated destinations, without inference or services."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts/aic.py'


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

    def run_cli(self, *args, entry=CLI):
        return subprocess.run([sys.executable, '-B', str(entry), *map(str, args)], cwd=self.base,
                              env=self.env, capture_output=True, text=True, timeout=30, check=False)

    def test_each_documented_adapter_installs_runs_and_uninstalls_in_isolation(self):
        registry = json.loads((ROOT / 'skills/aic/assets/harnesses.json').read_text())
        for index, agent in enumerate(registry['agents']):
            for scope in ('project', 'user'):
                if agent.get(scope) is None:
                    continue
                with self.subTest(agent=agent['id'], scope=scope):
                    base = self.base / f'{index}-{scope}'
                    base.mkdir()
                    selectors = ['--agent', agent['id'], '--scope', scope,
                                 '--project' if scope == 'project' else '--home', base]
                    first = self.run_cli('install', *selectors)
                    self.assertEqual(first.returncode, 0, first.stderr)
                    report = json.loads(first.stdout)
                    target = base / agent[scope] / 'aic'
                    self.assertEqual(Path(report['path']), target)
                    self.assertEqual(report['status'], 'installed')
                    installed = self.run_cli('--version', entry=target / 'scripts/aic.py')
                    self.assertEqual(installed.returncode, 0, installed.stderr)
                    self.assertEqual(json.loads(self.run_cli('install', *selectors).stdout)['status'], 'unchanged')
                    removal = self.run_cli('uninstall', *selectors)
                    self.assertEqual(removal.returncode, 0, removal.stderr)
                    self.assertEqual(json.loads(removal.stdout)['status'], 'uninstalled')
                    self.assertFalse(target.exists())

    def test_modified_install_is_preserved_at_the_cli_boundary(self):
        dest = self.base / 'project'
        dest.mkdir()
        args = ['--agent', 'codex', '--project', dest]
        self.assertEqual(self.run_cli('install', *args).returncode, 0)
        skill = dest / '.agents/skills/aic/SKILL.md'
        skill.write_text(skill.read_text() + '\nLocal user modification.\n')
        result = self.run_cli('uninstall', *args)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(skill.read_text().endswith('Local user modification.\n'))

    def test_unknown_harness_has_no_guessed_destination(self):
        result = self.run_cli('install', '--agent', 'deepseek', '--project', self.base)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_deep_json_is_a_clean_input_error_without_state(self):
        path = self.base / 'nested.json'
        path.write_text('{"nested":' + '[' * 2000 + '0' + ']' * 2000 + '}')
        result = self.run_cli('check-plan', path)
        self.assertEqual(result.returncode, 2)
        self.assertIn('AIC:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.base / '.aic').exists())

    def test_cli_launch_preview_and_wrong_approval_never_create_the_project(self):
        source = self.base / 'recommendation.json'
        source.write_bytes((ROOT / 'skills/aic/assets/example-plan.json').read_bytes())
        project = self.base / 'new-project'
        result = self.run_cli('orca-plan', source, '--project', project, '--name', 'readme')
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['project'], str(project))
        self.assertEqual(plan['recommendation']['workflow'], 'implementation')
        self.assertFalse(project.exists())
        approved = self.base / 'handoff.json'
        approved.write_text(json.dumps(plan))
        denied = self.run_cli('orca-apply', approved, '--approval', 'wrong', '--orca-binary', '/not-installed/orca')
        self.assertEqual(denied.returncode, 2)
        self.assertFalse(project.exists())

    def test_hello_world_is_the_install_check(self):
        result = self.run_cli('hello-world')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        payload = json.loads(result.stdout)
        version = self.run_cli('--version')
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(payload['hello'], 'world')
        self.assertEqual(payload['distribution'], 'aiculture-skills')
        self.assertEqual(payload['version'], version.stdout.removeprefix('AIC ').strip())
        self.assertEqual(payload['channels'], ['skill', 'claude-code-plugin', 'local-mcp'])
        self.assertEqual(list(self.base.iterdir()), [])

    def test_hello_world_rejects_extra_arguments(self):
        result = self.run_cli('hello-world', '--project', self.base)
        self.assertEqual(result.returncode, 2)
        self.assertIn('AIC:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_help_lists_hello_world_and_agents_still_runs(self):
        help_result = self.run_cli('--help')
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn('hello-world', help_result.stdout)
        agents = self.run_cli('agents')
        self.assertEqual(agents.returncode, 0, agents.stderr)
        listed = json.loads(agents.stdout)
        self.assertEqual(listed['schema_version'], 1)
        self.assertIn('claude-code', [item['id'] for item in listed['agents']])


if __name__ == '__main__':
    unittest.main()
