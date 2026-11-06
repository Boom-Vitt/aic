"""Real local Git artifacts and restart effects; no model or network calls."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maintenance.controller import Controller, MaintenanceBlocked, research_packet, review_packet
from maintenance.github import GitHubError
from maintenance.state import State
from maintenance import policy
from maintenance.agents import AgentError, NoToolAgents
from test_maintainer_agents import ControlledCLI, assistant, events, jsonl
from test_maintainer_policy import candidate, research, review


@unittest.skipUnless(shutil.which('git'), 'Maintenance requires Git')
class ControllerArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.git('init', '--quiet', '--initial-branch=main')
        (self.project / 'protected.txt').write_text('preserve this existing project data\n')
        self.git('add', '--', 'protected.txt')
        self.git('commit', '--quiet', '-m', 'fixture base')
        self.base = self.git('rev-parse', 'HEAD')
        self.controller = Controller(self.project)
        self.day = '2026-11-06'
        self.path = policy.record_path(self.day)
        self.text = '# Original research evidence\n\nA bounded, reference-only factual note.\n'
        target = self.project / self.path
        target.parent.mkdir(parents=True)
        target.write_text(self.text)
        self.git('add', '--', self.path)
        self.git('commit', '--quiet', '-m', 'new reference record')
        self.data = dict(day=self.day, base_sha=self.base, head_sha=self.git('rev-parse', 'HEAD'))

    def git(self, *args):
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'commit.gpgsign=false', '-c', 'user.name=AIC Fixture', '-c', 'user.email=aic-fixture@example.invalid', *args], cwd=self.project, env=environment, text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def test_one_new_regular_record_passes_without_touching_existing_data(self):
        before = (self.project / 'protected.txt').read_bytes()
        self.controller._artifact(self.project, self.data, self.text)
        self.assertEqual((self.project / 'protected.txt').read_bytes(), before)
        self.assertEqual(self.git('diff', '--name-only', self.base, 'HEAD'), self.path)

    def test_extra_code_change_is_rejected_even_with_a_valid_record(self):
        (self.project / 'protected.txt').write_text('unauthorized replacement\n')
        self.git('add', '--', 'protected.txt')
        self.git('commit', '--quiet', '-m', 'unpermitted change')
        self.data['head_sha'] = self.git('rev-parse', 'HEAD')
        with self.assertRaises(MaintenanceBlocked):
            self.controller._artifact(self.project, self.data, self.text)

    def test_executable_record_or_symlink_never_enters_the_publication_lane(self):
        target = self.project / self.path
        target.chmod(0o755)
        self.git('add', '--', self.path)
        self.git('commit', '--quiet', '-m', 'invalid executable mode')
        self.data['head_sha'] = self.git('rev-parse', 'HEAD')
        with self.assertRaises(MaintenanceBlocked):
            self.controller._artifact(self.project, self.data, self.text)
        target.unlink()
        target.symlink_to(self.project / 'protected.txt')
        self.git('add', '--', self.path)
        self.git('commit', '--quiet', '-m', 'invalid linked record')
        self.data['head_sha'] = self.git('rev-parse', 'HEAD')
        before = (self.project / 'protected.txt').read_bytes()
        with self.assertRaises(MaintenanceBlocked):
            self.controller._artifact(self.project, self.data, self.text)
        self.assertTrue(target.is_symlink())
        self.assertEqual((self.project / 'protected.txt').read_bytes(), before)

    def test_reviewed_bytes_and_head_cannot_be_replaced_after_validation(self):
        target = self.project / self.path
        target.write_text(self.text + '\n')
        self.git('add', '--', self.path)
        self.git('commit', '--quiet', '-m', 'different bytes')
        with self.assertRaises(MaintenanceBlocked):
            self.controller._artifact(self.project, self.data, self.text)
        self.data['head_sha'] = self.git('rev-parse', 'HEAD')
        with self.assertRaises(MaintenanceBlocked):
            self.controller._artifact(self.project, self.data, self.text)

    def test_untracked_surprises_are_preserved_not_deleted_or_published(self):
        surprise = self.project / 'owner-notes.txt'
        surprise.write_text('owner work')
        with self.assertRaises(MaintenanceBlocked):
            self.controller._artifact(self.project, self.data, self.text)
        self.assertEqual(surprise.read_text(), 'owner work')

    def test_preview_has_no_state_directory_or_external_calls(self):
        class Forbidden:
            def identity(self):
                raise AssertionError('No GitHub call in preview')
        controller = Controller(self.project, github=Forbidden(), collect=lambda *_args, **_kwargs: self.fail('No discovery in preview'))
        result = controller.run()
        self.assertFalse(result['side_effects'])
        self.assertFalse((self.project / '.work/maintainer').exists())


    def test_cleanup_preserves_owner_files_then_removes_only_owned_clone(self):
        root = Path(self.temp.name) / 'controller-root'
        root.mkdir()
        controller = Controller(root)
        key = '2026-11-06-' + 'a' * 16
        directory = controller.private / 'jobs' / key
        checkout = directory / 'checkout'
        directory.mkdir(parents=True)
        self.git('remote', 'add', 'origin', 'https://github.com/' + policy.REPO + '.git')
        self.git('switch', '--quiet', '-c', 'aic/research-fixture')
        self.git('branch', '--force', 'main', self.base)
        shutil.copytree(self.project, checkout)
        owner = dict(owner='aic-maintainer-checkout-v1', job=key, repository=policy.REPO)
        (directory / 'checkout-owner.json').write_bytes(policy.canonical(owner) + bytes([10]))
        source_packet = directory / 'source-packet.json'
        source_packet.write_text('preserve primary evidence')
        surprise = checkout / 'owner-private.txt'
        surprise.write_text('preserve this user work')
        data = dict(self.data, branch='aic/research-fixture', initial_base_sha=self.base)
        with self.assertRaises(MaintenanceBlocked):
            controller._cleanup(key, data)
        self.assertEqual(surprise.read_text(), 'preserve this user work')
        surprise.unlink()
        controller._cleanup(key, data)
        self.assertFalse(checkout.exists())
        self.assertEqual(source_packet.read_text(), 'preserve primary evidence')

    def owned_checkout(self):
        root = Path(self.temp.name) / 'owned-root'
        root.mkdir()
        controller = Controller(root)
        controller.state = State(controller.private / 'state.sqlite3')
        self.addCleanup(controller.state.close)
        key = '2026-11-06-' + 'd' * 16
        directory = controller._job_directory(key)
        directory.mkdir(parents=True)
        checkout = directory / 'checkout'
        self.git('switch', '--quiet', '-c', 'aic/research-fixture')
        self.git('branch', '--force', 'main', self.base)
        self.git('remote', 'add', 'origin', 'https://github.com/' + policy.REPO + '.git')
        self.git('update-ref', 'refs/remotes/origin/main', self.base)
        self.git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        shutil.copytree(self.project, checkout)
        owner = dict(owner='aic-maintainer-checkout-v1', job=key, repository=policy.REPO)
        (directory / 'checkout-owner.json').write_bytes(policy.canonical(owner) + b'\n')
        data = dict(self.data, initial_base_sha=self.base, branch='aic/research-fixture', pushed_head=self.data['head_sha'])
        return controller, key, checkout, data

    def test_cleanup_preserves_stash_tags_and_unmanaged_refs(self):
        controller, key, checkout, data = self.owned_checkout()
        original = self.project
        self.project = checkout
        for ref in ('refs/stash', 'refs/tags/owner-proof', 'refs/owner/private'):
            with self.subTest(ref=ref):
                self.git('update-ref', ref, data['head_sha'])
                with self.assertRaises(MaintenanceBlocked):
                    controller._cleanup(key, data)
                self.assertEqual(self.git('rev-parse', ref), data['head_sha'])
                self.git('update-ref', '-d', ref)
        self.git('symbolic-ref', 'refs/owner/dangling', 'refs/heads/missing-owner-work')
        with self.assertRaises(MaintenanceBlocked):
            controller._cleanup(key, data)
        self.assertEqual(self.git('symbolic-ref', 'refs/owner/dangling'), 'refs/heads/missing-owner-work')
        self.git('symbolic-ref', '--delete', 'refs/owner/dangling')
        (checkout / 'protected.txt').write_text('owner stashed changes\n')
        self.git('stash', 'push', '--quiet', '-m', 'owner work')
        self.assertEqual(self.git('status', '--porcelain'), '')
        with self.assertRaises(MaintenanceBlocked):
            controller._cleanup(key, data)
        self.assertIn('owner stashed changes', self.git('show', 'stash:protected.txt'))
        self.project = original

    def test_cleanup_preserves_allowed_names_with_unexpected_targets(self):
        controller, key, checkout, data = self.owned_checkout()
        original = self.project
        self.project = checkout
        owner_commit = self.git('commit-tree', self.git('rev-parse', 'HEAD^{tree}'), '-p', data['head_sha'], '-m', 'owner commit')
        for ref in ('refs/heads/main', 'refs/remotes/origin/main', 'refs/remotes/origin/' + data['branch']):
            with self.subTest(ref=ref):
                self.git('update-ref', ref, owner_commit)
                with self.assertRaises(MaintenanceBlocked):
                    controller._cleanup(key, data)
                self.assertEqual(self.git('rev-parse', ref), owner_commit)
                self.git('update-ref', '-d', ref)
                if ref == 'refs/heads/main' or ref == 'refs/remotes/origin/main':
                    self.git('update-ref', ref, self.base)
        self.project = original

    def integration_interruption(self):
        controller, key, checkout, data = self.owned_checkout()
        original = self.project
        self.project = checkout
        target = self.git('commit-tree', self.git('rev-parse', self.base + '^{tree}'), '-p', self.base, '-m', 'advanced main')
        self.project = original
        class Remote:
            def main_sha(self):
                return target
            def branch_sha(self, branch):
                return data['head_sha']
        controller.github = Remote()
        real_git = controller._git
        class Interrupted(BaseException):
            pass
        def interrupted_git(path, *args, **kwargs):
            if args[:3] == ('fetch', '--quiet', 'origin'):
                return real_git(path, 'update-ref', 'refs/remotes/origin/main', target)
            result = real_git(path, *args, **kwargs)
            if 'merge' in args:
                raise Interrupted()
            return result
        controller._git = interrupted_git
        with self.assertRaises(Interrupted):
            controller._refresh(key, data, checkout, self.text)
        resumed = controller.state.active_job()['data']
        self.assertEqual(resumed['base_sha'], self.base)
        self.assertEqual(resumed['integration']['target_main'], target)
        controller._git = real_git
        return controller, key, checkout, resumed, target

    def test_interrupted_known_integration_recovers_exact_head_and_invalidates_review(self):
        controller, key, checkout, data, target = self.integration_interruption()
        data['review'] = {'old': 'review'}
        expected_head = data['integration']['expected_head']
        controller._recover_integration(key, data, checkout, self.text)
        self.assertEqual((data['base_sha'], data['head_sha']), (target, expected_head))
        self.assertNotIn('review', data)
        self.assertNotIn('integration', data)
        controller._artifact(checkout, data, self.text)

    def test_interrupted_integration_preserves_unexpected_head(self):
        controller, key, checkout, data, target = self.integration_interruption()
        original = self.project
        self.project = checkout
        self.git('commit', '--quiet', '--allow-empty', '-m', 'owner work after interruption')
        owner_head = self.git('rev-parse', 'HEAD')
        self.project = original
        with self.assertRaises(MaintenanceBlocked):
            controller._recover_integration(key, data, checkout, self.text)
        self.assertEqual(controller._git(checkout, 'rev-parse', 'HEAD'), owner_head)
        self.assertEqual(data['base_sha'], self.base)

    def test_rejected_cleanup_resumes_without_rebuilding_deleted_branch(self):
        controller, key, checkout, data = self.owned_checkout()
        sources = [candidate()]
        result = research()
        verdict = review()
        verdict.update(head_sha=data['head_sha'], source_digest=policy.source_digest(sources), verdict='reject')
        verdict['assessments'][0]['verdict'] = 'reject'
        data.update(candidates=[asdict(sources[0])], research=result, review=verdict,
                    pr=dict(number=7, url='https://example.invalid/pr/7'))
        controller._save(key, data, 'reviewed')
        class Cached:
            def accepted(self, role, *args, **kwargs):
                return result if role == 'research' else verdict
            def run(self, *args, **kwargs):
                raise AssertionError('Cleanup must not start a role')
        class Remote:
            closed = False
            deleted = False
            close_calls = 0
            delete_calls = 0
            def pr(self, number):
                return dict(merged=False, head_sha=data['head_sha'], head_ref=data['branch'], state='closed' if self.closed else 'open')
            def close_pr(self, *args):
                self.close_calls += 1
                self.closed = True
                return dict(closed=True)
            def branch_sha(self, branch):
                return None if self.deleted else data['head_sha']
            def delete_branch(self, *args):
                self.delete_calls += 1
                self.deleted = True
                return dict(deleted=True)
            def main_sha(self):
                raise AssertionError('Rejected cleanup must ignore advanced main')
        remote = Remote()
        controller.github = remote
        controller._prepare = lambda *args: self.fail('Rejected work must not be rebuilt')
        controller._refresh = lambda *args: self.fail('Rejected work must not be integrated')
        surprise = checkout / 'owner.txt'
        surprise.write_text('preserve')
        with self.assertRaises(MaintenanceBlocked):
            controller._reject(key, data)
        self.assertTrue(controller.state.active_job()['data']['rejection_cleanup'])
        self.assertTrue(remote.closed and remote.deleted)
        with self.assertRaises(MaintenanceBlocked):
            controller._resume(key, controller.state.active_job()['data'], Cached())
        surprise.unlink()
        save = controller._save
        def interrupted_save(key, value, status):
            if status == 'rejected':
                raise OSError('interrupted after successful cleanup')
            return save(key, value, status)
        controller._save = interrupted_save
        with self.assertRaises(OSError):
            controller._resume(key, data, Cached())
        self.assertFalse(checkout.exists())
        controller._save = save
        outcome = controller._resume(key, controller.state.active_job()['data'], Cached())
        self.assertEqual(outcome['status'], 'review-rejected')
        self.assertEqual((remote.close_calls, remote.delete_calls), (1, 1))
        self.assertIsNone(controller.state.active_job())

    def test_unmanaged_clone_and_unsafe_job_keys_are_never_removed(self):
        root = Path(self.temp.name) / 'controller-root'
        root.mkdir()
        controller = Controller(root)
        for key in ('../../outside', '2026-11-06-not-a-digest'):
            with self.subTest(key=key), self.assertRaises(MaintenanceBlocked):
                controller._cleanup(key, self.data)
        key = '2026-11-06-' + 'b' * 16
        checkout = controller.private / 'jobs' / key / 'checkout'
        checkout.mkdir(parents=True)
        owner_work = checkout / 'notes.txt'
        owner_work.write_text('unmanaged work')
        with self.assertRaises(MaintenanceBlocked):
            controller._cleanup(key, self.data)
        self.assertEqual(owner_work.read_text(), 'unmanaged work')

class ControllerEffectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.path = self.project / '.work/maintainer/state.sqlite3'
        self.calls = 0

    def controller(self):
        controller = Controller(self.project)
        controller.state = State(self.path)
        self.addCleanup(controller.state.close)
        return controller

    def test_uncertain_effect_is_not_repeated_after_restart(self):
        first = self.controller()
        remote_object = self.project / 'remote-object'
        def operation():
            self.calls += 1
            remote_object.write_text('created once')
            raise GitHubError('Response lost after creation', uncertain=True)
        with self.assertRaises(GitHubError):
            first._effect('job-one', 'create', {'marker': 'one'}, operation, lambda: (False, None))
        first.state.close()
        resumed = self.controller()
        with self.assertRaises(MaintenanceBlocked):
            resumed._effect('job-one', 'create', {'marker': 'one'}, operation, lambda: (False, None))
        observed = resumed._effect('job-one', 'create', {'marker': 'one'}, operation, lambda: (remote_object.exists(), {'confirmed': True}))
        self.assertTrue(observed['confirmed'])
        self.assertEqual(self.calls, 1)
        self.assertEqual(remote_object.read_text(), 'created once')

    def test_effect_identity_cannot_expand_during_reconciliation(self):
        controller = self.controller()
        controller.state.begin_effect('job-one', 'write', {'target': 'owned'})
        with self.assertRaises(MaintenanceBlocked):
            controller._effect('job-one', 'write', {'target': 'other'}, lambda: self.fail('No changed mutation'))
        self.assertEqual(controller.state.effect('job-one', 'write')['descriptor']['target'], 'owned')

    def test_resumed_publication_rechecks_both_roles_without_another_process(self):
        now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
        templates = {item['id'] for item in json.loads((ROOT / 'skills/aic/assets/workflows.json').read_text())['templates']}
        for role in ('research', 'review'):
            with self.subTest(role=role), tempfile.TemporaryDirectory(dir=ROOT / '.work') as temporary:
                controller = Controller(Path(temporary), clock=lambda: now)
                controller.state = State(controller.private / 'state.sqlite3')
                self.addCleanup(controller.state.close)
                key = '2026-11-06-' + 'c' * 16
                cli = ControlledCLI(output=jsonl(events(assistant(research()))))
                agents = NoToolAgents(controller.state, enabled=True, runner=cli, artifact_root=controller.project / '.work')
                sources = [candidate()]
                packet = research_packet(sources, templates)
                directory = controller.private / 'jobs' / key / 'agents' / 'research'
                output = agents.run('research', packet, directory=directory, now=now, job_key=key)
                result = policy.validate_research(output, sources, templates)
                agents.accept('research', packet, output, now=now, job_key=key)
                data = dict(day='2026-11-06', candidates=[asdict(sources[0])], research=result, head_sha='a' * 40)
                if role == 'review':
                    text = policy.render_records(data['day'], result['records'], sources)
                    packet = review_packet(sources, result['records'], text, data['head_sha'], policy.record_path(data['day']))
                    verdict = review()
                    verdict['source_digest'] = policy.source_digest(sources)
                    cli.output = jsonl(events(assistant(verdict)))
                    directory = controller.private / 'jobs' / key / 'agents' / ('review-' + data['head_sha'][:12])
                    review_key = key + '-review-' + data['head_sha'][:12]
                    output = agents.run('review', packet, directory=directory, now=now, job_key=review_key)
                    data['review'] = policy.validate_review(output, head_sha=data['head_sha'], bundle_digest=policy.source_digest(sources), records=result['records'], candidates=sources)
                    agents.accept('review', packet, output, now=now, job_key=review_key)
                trace = next(directory.glob('*/trace.jsonl'))
                trace.write_text('modified private evidence')
                starts = cli.starts
                controller._issue = lambda *args: self.fail('Changed evidence must hold before an issue mutation')
                controller._prepare = lambda *args: self.fail('Changed evidence must hold before preparing publication')
                with self.assertRaises(AgentError):
                    controller._resume(key, data, agents)
                self.assertEqual((cli.starts, controller.state.runs('2026-11-06')), (starts, starts))
                self.assertEqual(trace.read_text(), 'modified private evidence')

    def test_mixed_batch_assigns_incomplete_evidence_once_before_complete_record_proceeds(self):
        controller = self.controller()
        now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
        controller.clock = lambda: now
        key = '2026-11-06-' + 'e' * 16
        complete = candidate()
        incomplete = replace(candidate('partial-v1'), documents=())
        data = dict(day='2026-11-06', candidates=[asdict(complete), asdict(incomplete)])
        class Remote:
            created = 0
            def find_issue(self, marker):
                return None
            def create_issue(self, title, body, marker, *, adoption):
                self.created += 1
                self.body = body
                return dict(number=self.created, url='https://example.invalid/issue')
        remote = Remote()
        controller.github = remote
        cli = ControlledCLI(output=jsonl(events(assistant(research()))))
        agents = NoToolAgents(controller.state, enabled=True, runner=cli, artifact_root=controller.private)
        def publication_reached(*args):
            raise MaintenanceBlocked('Complete candidate reached artifact preparation')
        controller._prepare = publication_reached
        for attempt in range(2):
            with self.assertRaisesRegex(MaintenanceBlocked, 'reached artifact preparation'):
                controller._resume(key, data, agents)
        self.assertEqual(remote.created, 1)
        self.assertIn('Obtain complete primary-method', remote.body)
        self.assertIn(incomplete.key, controller.state.seen())
        self.assertEqual(data['primary_evidence_tasks'][incomplete.key]['number'], 1)
        self.assertEqual(cli.starts, 1)
        trace = next((controller.private / 'jobs' / key / 'agents' / 'research').glob('*/trace.jsonl'))
        trace.write_text('changed accepted role evidence')
        with self.assertRaises(AgentError):
            controller._resume(key, data, agents)
        self.assertEqual((remote.created, cli.starts), (1, 1))

    def test_mixed_batch_keeps_manual_disposition_when_complete_research_fails(self):
        controller = self.controller()
        key = '2026-11-06-' + 'f' * 16
        incomplete = replace(candidate('partial-failed'), documents=())
        data = dict(day='2026-11-06', candidates=[asdict(candidate()), asdict(incomplete)])
        class Remote:
            created = 0
            def find_issue(self, marker):
                return None
            def create_issue(self, *args, **kwargs):
                self.created += 1
                return dict(number=self.created, url='https://example.invalid/issue')
        class FailedResearch:
            starts = 0
            def run(self, *args, **kwargs):
                self.starts += 1
                raise AgentError('Reserved research failed')
        remote, agents = Remote(), FailedResearch()
        controller.github = remote
        with self.assertRaises(AgentError):
            controller._resume(key, data, agents)
        self.assertEqual((remote.created, agents.starts), (1, 1))
        self.assertIn(incomplete.key, controller.state.seen())
        resumed = controller.state.active_job()['data']
        self.assertEqual(resumed['primary_evidence_tasks'][incomplete.key]['number'], 1)


if __name__ == '__main__':
    unittest.main()
