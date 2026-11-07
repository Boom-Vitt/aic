"""Consumer-visible checks for the Orca plus Claude Code template scripts."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from orca_claude.bootstrap import BootstrapError, copy_template
from orca_claude.loop import LoopError, accept_plan, select_budget
from orca_claude.plan import plan_hash, validate_plan
from orca_claude.policy import PolicyError, build_claude_argv, decide_tool, interpret_claude_result
from orca_claude.review import assess_readiness
from orca_claude.worktree import WorktreeError, run_in


def plan(**overrides):
    value = {
        'version': 1,
        'title': 'Example',
        'status': 'draft',
        'goal': 'Show the command.',
        'streams': [{
            'slug': 'docs',
            'role': 'claude-code',
            'paths': ['README.md'],
            'acceptance': ['The README names the command.'],
        }],
    }
    value.update(overrides)
    return value


def passed_result(**extra):
    value = {
        'type': 'result',
        'subtype': 'success',
        'is_error': False,
        'result': 'ok',
        'structured_output': {
            'status': 'passed',
            'streams': ['docs'],
            'evidence': ['verify exited 0'],
            'push_performed': False,
            'delete_performed': False,
        },
        'permission_denials': [],
    }
    value.update(extra)
    return value


class OrcaClaudeTemplateTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_plan_hash_matches_the_orca_v04_algorithm(self):
        sample = {
            'goal': 'g',
            'base': 'main',
            'streams': [{
                'slug': 'docs',
                'role': 'claude-code',
                'paths': ['README.md'],
                'acceptance': ['ok'],
            }],
        }
        self.assertEqual(plan_hash(sample), 'eb7960faae36b590')

    def test_invalid_cyclic_and_unowned_overlap_plans_are_rejected(self):
        cyclic = plan(streams=[
            {'slug': 'a', 'role': 'claude-code', 'paths': ['a.txt'], 'dependsOn': ['b'], 'acceptance': ['pytest']},
            {'slug': 'b', 'role': 'claude-code', 'paths': ['b.txt'], 'dependsOn': ['a'], 'acceptance': ['pytest']},
        ])
        overlap = plan(streams=[
            {'slug': 'a', 'role': 'claude-code', 'paths': ['src/'], 'acceptance': ['pytest']},
            {'slug': 'b', 'role': 'codex', 'paths': ['src/app.py'], 'acceptance': ['pytest']},
        ])
        self.assertFalse(validate_plan(cyclic).ok)
        self.assertTrue(any('cycle' in item for item in validate_plan(cyclic).errors))
        self.assertFalse(validate_plan(overlap).ok)
        self.assertTrue(any('both own' in item for item in validate_plan(overlap).errors))

    def test_ordered_overlap_is_a_warning_and_examples_stay_valid(self):
        ordered = plan(streams=[
            {'slug': 'api', 'role': 'claude-code', 'paths': ['src/api/'], 'acceptance': ['pytest']},
            {'slug': 'ui', 'role': 'claude-code', 'paths': ['src/'], 'dependsOn': ['api'], 'acceptance': ['pytest']},
        ])
        report = validate_plan(ordered)
        self.assertTrue(report.ok)
        self.assertTrue(report.warnings)
        for name in ('plan.example.json', 'plan.bug.example.json'):
            sample = json.loads((ROOT / 'templates' / 'orca-claude' / name).read_text(encoding='utf-8'))
            self.assertTrue(validate_plan(sample).ok, name)

    def test_unsafe_paths_roles_and_absolute_paths_are_rejected(self):
        escaped = plan()
        escaped['streams'][0]['paths'] = ['../secret.txt']
        absolute = plan()
        absolute['streams'][0]['paths'] = ['/tmp/out.txt']
        role = plan()
        role['streams'][0]['role'] = 'hermes'
        self.assertFalse(validate_plan(escaped).ok)
        self.assertFalse(validate_plan(absolute).ok)
        self.assertFalse(validate_plan(role).ok)
        for left, right in (('./src/', 'src/app.py'), ('./src/', './src/app.py')):
            overlap = plan(streams=[
                {'slug': 'a', 'role': 'claude-code', 'paths': [left], 'acceptance': ['pytest']},
                {'slug': 'b', 'role': 'claude-code', 'paths': [right], 'acceptance': ['pytest']},
            ])
            report = validate_plan(overlap)
            self.assertFalse(report.ok, (left, right, report.errors))
            self.assertTrue(any('both own' in item for item in report.errors))

    def test_permissions_deny_push_secrets_and_unrecognized_headless_tools(self):
        code, _ = decide_tool('Bash', {'command': 'git push origin main'}, headless=False,
                              active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(code, 2)
        code, _ = decide_tool('Read', {'file_path': '.env'}, headless=False,
                              active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(code, 2)
        code, _ = decide_tool('Bash', {'command': 'pytest -q'}, headless=True,
                              active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(code, 2)
        code, _ = decide_tool('NewTool', {}, headless=True,
                              active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(code, 2)
        code, _ = decide_tool('NewTool', {}, headless=False,
                              active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(code, 0)
        accepted = plan(status='accepted')
        code, _ = decide_tool('Write', {'file_path': 'src/other.py'}, headless=True, active_stream='docs',
                              active_worktree=None, resolved_toplevel=None, plan=accepted)
        self.assertEqual(code, 2)
        code, _ = decide_tool('Write', {'file_path': 'README.md'}, headless=True, active_stream='docs',
                              active_worktree=None, resolved_toplevel=None, plan=accepted)
        self.assertEqual(code, 0)
        code, _ = decide_tool('Bash', {'command': 'pytest -q'}, headless=True, active_stream=None,
                              active_worktree='/tmp/feature', resolved_toplevel='/tmp/main', plan=None)
        self.assertEqual(code, 2)
        denied = (
            'git -C /tmp/repo push origin main',
            "python3 -c 'exec(\"git push\")'",
            'node -e \'require("child_process").execSync("git push")\'',
            "bash -c 'git push origin main'",
            "sh -c 'git -C /tmp/repo push origin main'",
            'git --git-dir=/tmp/repo/.git push',
            'git branch -D feature',
            "sed 's/a/b/e'",
            "sed 'w /tmp/out'",
        )
        for command in denied:
            code, _message = decide_tool('Bash', {'command': command}, headless=True, active_stream=None,
                                         active_worktree=None, resolved_toplevel=None, plan=None)
            self.assertEqual(code, 2, command)
        allowed, _message = decide_tool('Bash', {'command': 'git diff --stat'}, headless=True, active_stream=None,
                                        active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(allowed, 0)
        exact, _message = decide_tool('Bash', {'command': './gate.sh'}, headless=True, active_stream=None,
                                      active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(exact, 0)

    def test_headless_denies_reviewer_bypasses(self):
        secret = self.root / 'id_rsa'
        secret.write_text('secret\n', encoding='utf-8')
        repo = self.root / 'repo'
        repo.mkdir()
        options = dict(active_stream=None, active_worktree=None, resolved_toplevel=str(repo), plan=None, cwd=str(repo))
        denied = (
            f'git diff --no-index /dev/null {secret}',
            "sed -e '1e echo hi'",
            "sed -e '1e /usr/bin/git -C /tmp push'",
            'python3 evil.py',
            'python3 -m pip',
            'node -p process.version',
            'node --require ./preload.js app.js',
            'git show HEAD:.env',
            'git log -p -- README.md',
            f'git diff -- {secret}',
        )
        for command in denied:
            code, _message = decide_tool('Bash', {'command': command}, headless=True, **options)
            self.assertEqual(code, 2, command)
        code, _message = decide_tool('Bash', {'command': 'command git -C x push'}, headless=False,
                                     active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
        self.assertEqual(code, 2)
        for wrapper in ('env git push', 'exec git push', 'xargs git branch -D feature'):
            code, _message = decide_tool('Bash', {'command': wrapper}, headless=False,
                                         active_stream=None, active_worktree=None, resolved_toplevel=None, plan=None)
            self.assertEqual(code, 2, wrapper)

    def test_hook_blocks_git_push_with_exit_2(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / '.claude' / 'hooks' / 'guard.py')],
            input='{"tool_name":"Bash","tool_input":{"command":"git push"},"cwd":"/tmp"}\n',
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn('denied', result.stderr)

    def test_claude_argv_never_uses_bare_or_bypass(self):
        older = build_claude_argv(executable='claude', prompt='plan', max_turns=10, settings='settings.json',
                                  schema='{}', version=(2, 1, 258))
        newer = build_claude_argv(executable='claude', prompt='plan', max_turns=10, settings='settings.json',
                                  schema='{}', version=(2, 1, 259))
        self.assertNotIn('--bare', older + newer)
        self.assertNotIn('--dangerously-skip-permissions', older + newer)
        self.assertIn('dontAsk', older)
        self.assertNotIn('--permission-prompts', older)
        self.assertEqual(newer[-2:], ['--permission-prompts', 'none'])
        with self.assertRaises(PolicyError):
            build_claude_argv(executable='claude', prompt='plan', max_turns=61, settings='s', schema='{}', version=None)

    def test_result_interpreter_requires_structure_and_ready_mcp(self):
        self.assertEqual(interpret_claude_result(passed_result()), [])
        missing = passed_result()
        del missing['structured_output']
        self.assertTrue(interpret_claude_result(missing))
        denied = passed_result(permission_denials=[{'tool': 'Bash'}])
        self.assertTrue(any('permission' in item for item in interpret_claude_result(denied)))
        self.assertTrue(any('plugin' in item for item in interpret_claude_result(passed_result(), 'Error loading plugin boom')))
        optional = passed_result(mcp_servers=[{'name': 'perplexity', 'status': 'needs-auth'}])
        self.assertEqual(interpret_claude_result(optional), [])
        required = passed_result(mcp_servers=[{'name': 'docs', 'required': True, 'status': 'failed'}])
        self.assertTrue(interpret_claude_result(required))

    def test_missing_gate_and_stale_review_fail_readiness(self):
        missing = assess_readiness(head='abc', patch_id='patch', gate=None, review=None)
        self.assertEqual(missing['code'], 1)
        stale = assess_readiness(
            head='abc', patch_id='patch',
            gate={'result': 'pass', 'head': 'abc'},
            review={'verdict': 'APPROVE', 'head': 'old', 'patch_id': 'patch'},
        )
        self.assertEqual(stale['code'], 5)
        ready = assess_readiness(
            head='abc', patch_id='patch',
            gate={'result': 'pass', 'head': 'abc'},
            review={'verdict': 'APPROVE', 'head': 'abc', 'patch_id': 'patch'},
        )
        self.assertEqual(ready['code'], 0)

    def test_commands_run_in_the_named_worktree(self):
        main = self.root / 'main'
        main.mkdir()
        self.git(main, 'init')
        self.git(main, 'config', 'user.email', 'test@example.invalid')
        self.git(main, 'config', 'user.name', 'AIC Test')
        (main / 'README.md').write_text('start\n', encoding='utf-8')
        self.git(main, 'add', 'README.md')
        self.git(main, 'commit', '-m', 'init')
        worktree = self.root / 'feature'
        self.git(main, 'worktree', 'add', str(worktree), '-b', 'feature/docs')
        result = run_in(worktree, [sys.executable, '-c', 'open("marker.txt","w").write("ok")'], expected=worktree)
        self.assertEqual(result.returncode, 0)
        self.assertEqual((worktree / 'marker.txt').read_text(encoding='utf-8'), 'ok')
        self.assertFalse((main / 'marker.txt').exists())
        with self.assertRaises(WorktreeError):
            run_in(main, [sys.executable, '-c', 'open("nope.txt","w").write("x")'], expected=worktree)

    def test_bootstrap_refuses_existing_relative_and_symlinked_paths(self):
        existing = self.root / 'exists'
        existing.mkdir()
        with self.assertRaises(BootstrapError):
            copy_template(existing)
        with self.assertRaises(BootstrapError):
            copy_template(Path('relative/new-project'))
        real = self.root / 'private-tmp'
        real.mkdir()
        alias = self.root / 'tmp-alias'
        alias.symlink_to(real, target_is_directory=True)
        copy_template(alias / 'proj')
        self.assertTrue((real / 'proj' / 'gate.sh').is_file())
        as_link = self.root / 'as-link'
        as_link.symlink_to(self.root / 'missing-target')
        with self.assertRaises(BootstrapError):
            copy_template(as_link)
        partial = self.root / 'partial'
        with patch('orca_claude.bootstrap._copy_file', side_effect=BootstrapError('stop')):
            with self.assertRaises(BootstrapError):
                copy_template(partial)
        self.assertFalse(partial.exists())
        inside = ROOT / 'not-a-real-child'
        with self.assertRaises(BootstrapError):
            copy_template(inside)

    def test_bootstrap_installs_a_gate_that_exits_2_without_a_project_check(self):
        dest = self.root / 'fresh'
        written = copy_template(dest)
        self.assertIn('.orca/gate.sh', written)
        self.assertIn('scripts/orca-headless.sh', written)
        gate = subprocess.run([str(dest / 'gate.sh')], capture_output=True, text=True, check=False)
        self.assertEqual(gate.returncode, 2)
        again = subprocess.run([str(ROOT / 'scripts' / 'bootstrap-orca-project.sh'), str(dest)], capture_output=True, text=True, check=False)
        self.assertEqual(again.returncode, 3)

    def test_headless_apply_records_budget_timeout_and_does_not_push(self):
        project = self.root / 'repo'
        project.mkdir()
        self.git(project, 'init')
        sample = plan()
        path = project / 'plan.json'
        path.write_text(json.dumps(sample), encoding='utf-8')
        env = os.environ.copy()
        env['AIC_ORCA_FREE_KB'] = '1000'
        env['AIC_ORCA_CLAUDE'] = str(self.fake_claude(sleep=False))
        refused = self.run_loop(['--project', str(project), '--plan', str(path), '--apply'], env)
        self.assertEqual(refused.returncode, 3)
        self.assertFalse((self.root / 'claude-called').exists())
        wide = plan(streams=[
            {'slug': 'one', 'role': 'claude-code', 'paths': ['one.txt'], 'acceptance': ['pytest']},
            {'slug': 'two', 'role': 'claude-code', 'paths': ['two.txt'], 'acceptance': ['pytest']},
        ])
        path.write_text(json.dumps(wide), encoding='utf-8')
        env['AIC_ORCA_FREE_KB'] = '20000000'
        budget = self.run_loop(['--project', str(project), '--plan', str(path), '--apply', '--max-agents', '1'], env)
        self.assertEqual(budget.returncode, 1)
        self.assertFalse((self.root / 'claude-called').exists())
        path.write_text(json.dumps(sample), encoding='utf-8')
        accept = self.run_loop(['--project', str(project), '--plan', str(path), '--accept'], env)
        self.assertEqual(accept.returncode, 0, accept.stderr)
        env['AIC_ORCA_CLAUDE'] = str(self.fake_claude(sleep=True))
        timed = self.run_loop(
            ['--project', str(project), '--plan', str(path), '--apply', '--timeout', '1',
             '--settings', str(ROOT / '.claude' / 'settings.headless.json')],
            env,
        )
        self.assertEqual(timed.returncode, 124, timed.stdout + timed.stderr)
        ledger = project / '.git' / 'orca' / 'aic-headless.jsonl'
        self.assertTrue(ledger.is_file())
        self.assertIn('timeout', ledger.read_text(encoding='utf-8'))
        env['AIC_ORCA_CLAUDE'] = str(self.fake_claude(sleep=False))
        ran = self.run_loop(
            ['--project', str(project), '--plan', str(path), '--apply',
             '--settings', str(ROOT / '.claude' / 'settings.headless.json')],
            env,
        )
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        body = json.loads(ran.stdout)
        self.assertTrue(body['invoked_claude'])
        self.assertFalse(body['push'])
        self.assertFalse(body['delete'])
        recorded = (self.root / 'claude-args').read_text(encoding='utf-8').splitlines()
        self.assertNotIn('--bare', recorded)
        self.assertFalse(any('dangerously-skip-permissions' in item for item in recorded))
        self.assertIn('dontAsk', recorded)
        recorded_env = (self.root / 'claude-env').read_text(encoding='utf-8')
        self.assertIn('ORCA_HEADLESS=1', recorded_env)
        self.assertIn('ORCA_PLAN=', recorded_env)
        self.assertIn('ORCA_ACTIVE_STREAM=docs', recorded_env)

    def test_accept_is_idempotent_until_the_plan_changes(self):
        path = self.root / 'plan.json'
        path.write_text(json.dumps(plan()), encoding='utf-8')
        first = accept_plan(path)
        second = accept_plan(path)
        self.assertEqual(first['planHash'], second['planHash'])
        self.assertRegex(first['acceptedAt'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
        changed = json.loads(path.read_text(encoding='utf-8'))
        changed['goal'] = 'A different goal.'
        path.write_text(json.dumps(changed), encoding='utf-8')
        with self.assertRaises(LoopError):
            accept_plan(path)

    def test_budgets_cap_low_disk_and_reject_the_ceiling(self):
        agents, trees, notes = select_budget(4, 6, 3 * 1024 * 1024, enforce_floor=False)
        self.assertEqual((agents, trees), (1, 1))
        self.assertTrue(notes)
        with self.assertRaises(LoopError):
            select_budget(4, 6, 1024, enforce_floor=True)
        with self.assertRaises(LoopError):
            select_budget(5, 1, None, enforce_floor=False)
        unknown, trees, notes = select_budget(4, 6, None, enforce_floor=False)
        self.assertEqual((unknown, trees), (1, 1))
        self.assertTrue(notes)

    def test_repository_harness_stays_free_of_bypass_and_plugin_hooks(self):
        for relative in ('.claude/settings.json', '.claude/settings.headless.json'):
            text = (ROOT / relative).read_text(encoding='utf-8')
            self.assertNotIn('bypassPermissions', text)
            self.assertNotIn('dangerously-skip-permissions', text)
            self.assertNotIn('--bare', text)
            self.assertEqual(text, (ROOT / 'templates' / 'orca-claude' / relative).read_text(encoding='utf-8'))
            self.assertNotIn('Bash(python3 *)', text)
            self.assertNotIn('Bash(pytest *)', text)
            if relative.endswith('settings.headless.json'):
                self.assertNotIn('Bash(git diff *)', text)
                self.assertNotIn('Bash(git log *)', text)
                self.assertNotIn('Bash(git show *)', text)
        def tree(root):
            return {path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob('*') if path.is_file() and '__pycache__' not in path.parts}

        root_claude = tree(ROOT / '.claude')
        template_claude = tree(ROOT / 'templates' / 'orca-claude' / '.claude')
        self.assertEqual(root_claude, template_claude)
        plugin = json.loads((ROOT / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        marketplace = json.loads((ROOT / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
        self.assertNotIn('hooks', plugin)
        self.assertNotIn('hooks', json.dumps(marketplace))
        workflow = (ROOT / 'templates' / 'orca-claude' / '.github' / 'workflows' / 'template-gate.yml').read_text(encoding='utf-8')
        self.assertIn('contents: read', workflow)
        self.assertNotIn('pull_request_target', workflow)
        for base in (ROOT / 'scripts', ROOT / 'templates', ROOT / '.claude'):
            for path in base.rglob('*'):
                if not path.is_file():
                    continue
                text = path.read_text(encoding='utf-8', errors='ignore')
                self.assertNotIn('BEGIN OPENSSH PRIVATE KEY', text, path)
                self.assertNotIn('sk-ant-api', text, path)

    def test_macos_setup_dry_run_is_idempotent_and_apply_refuses_overrides(self):
        env = os.environ.copy()
        env.update({'AIC_ORCA_UNAME': 'Linux', 'ANTHROPIC_API_KEY': 'sk-ant-testsecret', 'GH_TOKEN': 'ghp_testsecret'})
        first = self.run_setup(['--dry-run'], env)
        second = self.run_setup(['--dry-run'], env)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertNotIn('sk-ant-testsecret', first.stdout + first.stderr)
        self.assertNotIn('ghp_testsecret', first.stdout + first.stderr)
        applied = self.run_setup(['--apply'], env)
        self.assertEqual(applied.returncode, 3)
        self.assertIn('refusing --apply', applied.stdout)

    def test_link_plugin_requires_the_pinned_marketplace_id_and_sha(self):
        stub = self.root / 'claude'
        log = self.root / 'claude.log'
        script = ROOT / 'scripts' / 'macos-setup-orca.sh'
        stub.write_text(textwrap.dedent(f'''\
            #!/bin/sh
            printf '%s\\n' "$*" >> "{log}"
            if [ "$1" = "plugin" ] && [ "$2" = "list" ]; then
              printf '%s\\n' "$CLAUDE_PLUGIN_LIST"
              exit 0
            fi
            exit 0
            '''), encoding='utf-8')
        stub.chmod(0o755)

        def invoke(listing):
            log.write_text('', encoding='utf-8')
            env = os.environ.copy()
            env['AIC_ORCA_CLAUDE'] = str(stub)
            env['CLAUDE_PLUGIN_LIST'] = listing
            env['HOME'] = str(self.root)
            result = subprocess.run(
                ['bash', '-c', f'source "{script}"; link_plugin'],
                capture_output=True, text=True, check=False, env=env,
            )
            return result, log.read_text(encoding='utf-8')

        pinned = 'boom-big-nose-workflow@claude-mods-boombignose ad1a6032465546883d57299fda5677d6b2a7750d'
        ready, ready_log = invoke(pinned)
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertNotIn('plugin install', ready_log)
        wrong_name, wrong_log = invoke('boom-big-nose-workflow enabled')
        self.assertEqual(wrong_name.returncode, 0, wrong_name.stderr)
        self.assertIn('plugin install boom-big-nose-workflow@claude-mods-boombignose', wrong_log)
        other_market, other_log = invoke('boom-big-nose-workflow@boombignose-mods ad1a6032465546883d57299fda5677d6b2a7750d')
        self.assertIn('plugin install boom-big-nose-workflow@claude-mods-boombignose', other_log)

    def test_macos_helpers_compare_versions_and_plugin_cache_state(self):
        script = str(ROOT / 'scripts' / 'macos-setup-orca.sh')
        newer = subprocess.run(
            ['bash', '-c', f'source "{script}"; version_ge "2.39.1" "2.38"; echo $?'],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(newer.stdout.strip(), '0')
        older = subprocess.run(
            ['bash', '-c', f'source "{script}"; version_ge "2.37.9" "2.38" && echo yes || echo no'],
            capture_output=True, text=True, check=False,
        )
        self.assertIn('no', older.stdout)
        cache = self.root / 'cache'
        cache.mkdir()
        self.git(cache, 'init')
        self.git(cache, 'config', 'user.email', 'test@example.invalid')
        self.git(cache, 'config', 'user.name', 'AIC Test')
        (cache / 'README.md').write_text('plugin\n', encoding='utf-8')
        self.git(cache, 'add', 'README.md')
        self.git(cache, 'commit', '-m', 'init')
        moved = subprocess.run(
            ['bash', '-c', f'source "{script}"; plugin_state "{cache}"'],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(moved.stdout.strip(), 'moved')
        (cache / 'extra.txt').write_text('dirty\n', encoding='utf-8')
        dirty = subprocess.run(
            ['bash', '-c', f'source "{script}"; plugin_state "{cache}"'],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(dirty.stdout.strip(), 'dirty')
        link = self.root / 'linked-cache'
        link.symlink_to(cache, target_is_directory=True)
        linked = subprocess.run(
            ['bash', '-c', f'source "{script}"; plugin_state "{link}"'],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(linked.stdout.strip(), 'symlink')

    def test_public_smoke_script(self):
        script = ROOT / 'tests' / 'orca_claude_smoke.sh'
        self.assertTrue(script.stat().st_mode & stat.S_IXUSR)
        result = subprocess.run(['sh', str(script)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('smoke ok', result.stdout)

    def git(self, cwd, *args):
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)

    def run_loop(self, args, env):
        child = dict(env)
        child['PYTHONPATH'] = str(ROOT / 'scripts')
        return subprocess.run(
            [sys.executable, '-m', 'orca_claude.loop', *args],
            cwd=ROOT, env=child, capture_output=True, text=True, check=False,
        )

    def run_setup(self, args, env):
        return subprocess.run(
            ['bash', str(ROOT / 'scripts' / 'macos-setup-orca.sh'), *args],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )

    def fake_claude(self, *, sleep):
        path = self.root / ('claude-sleep' if sleep else 'claude-ok')
        args = self.root / 'claude-args'
        called = self.root / 'claude-called'
        if sleep:
            body = textwrap.dedent(f'''\
                #!/bin/sh
                if [ "$1" = "--version" ]; then echo "2.1.310 (Claude Code)"; exit 0; fi
                sleep 3
                ''')
        else:
            body = textwrap.dedent(f'''\
                #!/bin/sh
                if [ "$1" = "--version" ]; then echo "2.1.310 (Claude Code)"; exit 0; fi
                printf '%s\\n' "$@" > "{args}"
                printf 'ORCA_HEADLESS=%s\\n' "${{ORCA_HEADLESS-}}" > "{self.root / 'claude-env'}"
                printf 'ORCA_PLAN=%s\\n' "${{ORCA_PLAN-}}" >> "{self.root / 'claude-env'}"
                printf 'ORCA_ACTIVE_STREAM=%s\\n' "${{ORCA_ACTIVE_STREAM-}}" >> "{self.root / 'claude-env'}"
                touch "{called}"
                cat <<'EOF'
                {{"type":"result","subtype":"success","is_error":false,"result":"ok","structured_output":{{"status":"passed","streams":[],"evidence":["verify"],"push_performed":false,"delete_performed":false}},"permission_denials":[]}}
                EOF
                ''')
        path.write_text(body, encoding='utf-8')
        path.chmod(0o755)
        return path
