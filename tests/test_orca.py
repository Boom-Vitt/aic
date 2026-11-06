"""Isolated argv contract tests, not live Orca or model verification."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/aic/scripts'))

from aiclib import orca
from aiclib.safety import AICError, canonical_json


def recommendation():
    return dict(schema_version=1, task='Review the requested project', workflow='review',
                topology='solo', risk='low', reasons=['Owner requested review'], evidence=[],
                scope={'read': ['README.txt'], 'write': []}, acceptance=['Report evidence'],
                independent_subtasks=[], next_action='recommend', approval_required=True)


class OrcaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'requested'

    def plan(self):
        return orca.plan_handoff(self.root, recommendation(), name='review', model=None)

    def test_dry_run_has_no_writes_or_processes_even_without_binaries(self):
        with patch('subprocess.run', side_effect=AssertionError('No process')):
            plan = self.plan()
            self.assertEqual(plan['recommendation'], recommendation())
            with self.assertRaises(AICError):
                orca.apply_handoff(plan, orca_binary='/missing/orca')
        self.assertFalse(self.root.exists())

    def test_mutations_and_forged_operations_rejected_before_effects(self):
        plan = self.plan()
        for key, value in [('name', 'changed'), ('model', 'other'),
                           ('project', str(self.root.parent / 'other')),
                           ('operations', [{'argv': ['rm', '-rf', '/']}])]:
            changed = copy.deepcopy(plan)
            changed[key] = value
            with patch('subprocess.run', side_effect=AssertionError('No process')):
                with self.assertRaises(AICError):
                    orca.apply_handoff(changed, approval=plan['digest'])
        forged = copy.deepcopy(plan)
        forged['operations'] = [{'argv': ['malicious']}]
        forged['digest'] = hashlib.sha256(canonical_json({k: v for k, v in forged.items() if k != 'digest'})).hexdigest()
        with patch('subprocess.run', side_effect=AssertionError('No process')):
            with self.assertRaises(AICError):
                orca.apply_handoff(forged, approval=forged['digest'])
        self.assertFalse(self.root.exists())

    def test_contract_apply_probes_then_uses_scoped_fresh_session_argv(self):
        plan = self.plan()
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            self.assertNotIn('shell', kwargs)
            if '--help' in argv:
                return subprocess.CompletedProcess(argv, 0, '--path --json --agent --worktree --prompt --model', '')
            if argv[:3] == ['orca', 'agent', 'launch']:
                payload = {'ok': True, 'result': {'launch': {
                    'outcome': {'kind': 'terminal', 'handle': 'term-test'},
                    'prompt': {'outcome': 'handed-to-terminal'}}}}
            else:
                payload = {'ok': True, 'result': {}}
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), '')
        with patch('subprocess.run', side_effect=run):
            result = orca.apply_handoff(plan, approval=plan['digest'])
            before = len(calls)
            with self.assertRaises(AICError):
                orca.apply_handoff(plan, approval=plan['digest'])
            self.assertEqual(len(calls), before)
        self.assertEqual(result['status'], 'launched')
        self.assertIn(['orca', 'repo', 'add', '--path', str(self.root), '--json'], calls)
        launch = next(argv for argv in calls if argv[:3] == ['orca', 'agent', 'launch'] and '--help' not in argv)
        self.assertEqual(launch[3:7], ['--agent', 'omp', '--worktree', 'path:' + str(self.root)])
        for flag in ['--focus', '--effort', '--terminal', '--model']:
            self.assertNotIn(flag, launch)
        self.assertTrue((self.root / result['artifact']).is_file())
        self.assertFalse(result['task_completed'])

    def test_missing_capability_fails_before_project_creation(self):
        plan = self.plan()
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'unknown interface', '')):
            with self.assertRaises(AICError):
                orca.apply_handoff(plan, approval=plan['digest'])
        self.assertFalse(self.root.exists())

    def test_uncertain_launch_is_not_retried(self):
        plan = self.plan()
        launches = []
        def run(argv, **kwargs):
            if '--help' in argv:
                return subprocess.CompletedProcess(argv, 0, '--path --json --agent --worktree --prompt --model', '')
            if argv[:3] == ['orca', 'agent', 'launch']:
                launches.append(argv)
                raise subprocess.TimeoutExpired(argv, 30)
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"result":{}}', '')
        with patch('subprocess.run', side_effect=run):
            with self.assertRaisesRegex(AICError, 'uncertain'):
                orca.apply_handoff(plan, approval=plan['digest'])
            with self.assertRaises(AICError):
                orca.apply_handoff(plan, approval=plan['digest'])
        self.assertEqual(len(launches), 1)

    def test_negative_or_missing_launch_receipt_stays_uncertain(self):
        responses = [{}, {'ok': False, 'result': {}}, {'ok': True, 'result': {}}]
        for index, response in enumerate(responses):
            with self.subTest(response=response):
                project = self.root.parent / f'case-{index}'
                plan = orca.plan_handoff(project, recommendation(), name='review')
                launches = []
                def run(argv, **kwargs):
                    if '--help' in argv:
                        return subprocess.CompletedProcess(argv, 0, '--path --json --agent --worktree --prompt', '')
                    if argv[:3] == ['orca', 'agent', 'launch']:
                        launches.append(argv)
                        return subprocess.CompletedProcess(argv, 0, json.dumps(response), '')
                    return subprocess.CompletedProcess(argv, 0, '{"ok":true,"result":{}}', '')
                with patch('subprocess.run', side_effect=run):
                    with self.assertRaisesRegex(AICError, 'uncertain'):
                        orca.apply_handoff(plan, approval=plan['digest'])
                    with self.assertRaises(AICError):
                        orca.apply_handoff(plan, approval=plan['digest'])
                self.assertEqual(len(launches), 1)

    def test_registration_refusal_does_not_launch_agent(self):
        plan = self.plan()
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            if '--help' in argv:
                return subprocess.CompletedProcess(argv, 0, '--path --json --agent --worktree --prompt', '')
            return subprocess.CompletedProcess(argv, 0, '{"ok":false,"result":{}}', '')
        with patch('subprocess.run', side_effect=run):
            with self.assertRaisesRegex(AICError, 'registration'):
                orca.apply_handoff(plan, approval=plan['digest'])
        self.assertFalse(any(argv[:3] == ['orca', 'agent', 'launch'] and '--help' not in argv for argv in calls))

    def test_undecodable_launch_output_keeps_no_retry_boundary(self):
        plan = self.plan()
        def run(argv, **kwargs):
            if '--help' in argv:
                return subprocess.CompletedProcess(argv, 0, '--path --json --agent --worktree --prompt', '')
            if argv[:3] == ['orca', 'agent', 'launch']:
                raise UnicodeDecodeError('utf-8', b'\\xff', 0, 1, 'invalid')
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"result":{}}', '')
        with patch('subprocess.run', side_effect=run):
            with self.assertRaisesRegex(AICError, 'uncertain.*do not retry'):
                orca.apply_handoff(plan, approval=plan['digest'])
