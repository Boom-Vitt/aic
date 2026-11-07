"""Owner-provenance publication regressions with simulated external I/O only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maintenance.contracts import CollectionBatch
from maintenance.controller import Controller
from maintenance.github import ACTOR, GitHub, GitHubError, REPO
from maintenance.state import State
from test_maintainer_github import API
from test_maintainer_policy import candidate

MARKER = '<!-- aic-maintainer:security-publication -->'
ISSUES = '/repos/' + REPO + '/issues'
COMMENTS = ISSUES + '/7/comments'
NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)


def issue(number, marker, *, author=ACTOR, state='open', assigned=True):
    return dict(number=number, html_url=f'https://github.com/{REPO}/issues/{number}',
                body='Synthetic issue evidence\n\n' + marker, state=state,
                user={'login': author}, assignees=[{'login': ACTOR}] if assigned else [],
                labels=[{'name': 'aic-adoption'}, {'name': 'aic-maintainer'}])


def comment(number, *, author=ACTOR, body=MARKER):
    return dict(id=number, body=body, user={'login': author})


class PublicationAPI(API):
    """Retain real REST decoding/pagination and model only GitHub's remote state."""
    def __init__(self):
        super().__init__()
        self.issues = []
        self.comments = []
        self.issue_write_error = None
        self.persist_issue = True
        self.routes['GET', ISSUES] = lambda query: self.page(self.issues, query)
        self.routes['GET', COMMENTS] = lambda query: self.page(self.comments, query)

    @staticmethod
    def page(rows, query):
        start = (int(query['page'][0]) - 1) * 100
        return rows[start:start + 100]

    def __call__(self, argv, **kwargs):
        if argv[:2] != ['gh', 'api']:
            raise AssertionError('Only simulated GitHub API I/O is allowed')
        method = argv[argv.index('--method') + 1]
        path = urlsplit(argv[2]).path
        if method == 'POST' and path == ISSUES:
            payload = json.loads(kwargs['input'])
            number = max((row['number'] for row in self.issues), default=0) + 1
            created = issue(number, '')
            created.update(title=payload['title'], body=payload['body'],
                           assignees=[{'login': login} for login in payload['assignees']],
                           labels=[{'name': name} for name in payload['labels']])
            if self.persist_issue:
                self.issues.append(created)
            self.routes[method, path] = self.issue_write_error or created
        elif method != 'GET':
            raise AssertionError('Unexpected simulated mutation: ' + method + ' ' + path)
        return super().__call__(argv, **kwargs)


class PublicationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        self.api = PublicationAPI()
        self.github = GitHub(write_enabled=True, runner=self.api, working_directory=self.project)
        self.source = replace(candidate('publication-collision-v1'), documents=())
        digest = hashlib.sha256(self.source.key.encode()).hexdigest()
        self.source_marker = '<!-- aic-maintainer:source:' + digest + ' -->'
        self.effect_name = 'issue:' + digest
        self.discovery = []
        run_patch = patch('subprocess.run', side_effect=self.external_git)
        run_patch.start()
        self.addCleanup(run_patch.stop)
        process_patch = patch('subprocess.Popen', side_effect=AssertionError('No model or service process is allowed'))
        process_patch.start()
        self.addCleanup(process_patch.stop)

    def external_git(self, argv, **kwargs):
        # This lane needs only an origin read, never a checkout or credential helper.
        if argv[0] != 'git' or argv[-3:] != ['config', '--get', 'remote.origin.url']:
            raise AssertionError('Unexpected external command: ' + repr(argv))
        return subprocess.CompletedProcess(argv, 0, 'https://github.com/' + REPO + '.git\n', '')

    def collect(self, now, *, seen, limit):
        self.discovery.append(now)
        return CollectionBatch((self.source,), (), now.isoformat())

    def run_controller(self, now=NOW):
        controller = Controller(self.project, publish=True, github=self.github,
                                collect=self.collect, now=now)
        return controller.run()

    def journal(self):
        state = State(self.project / '.work/maintainer/state.sqlite3')
        self.addCleanup(state.close)
        return state

    def assert_foreign_issue_does_not_hold_queue(self, state):
        foreign = issue(1, self.source_marker, author='public-contributor', state=state)
        foreign_before = json.loads(json.dumps(foreign))
        self.api.issues.append(foreign)
        first = self.run_controller()
        self.assertEqual(first['status'], 'manual-primary-evidence')
        second = self.run_controller(NOW + timedelta(days=1))
        self.assertEqual(second['status'], 'no-new-candidates')
        self.assertEqual(len(self.discovery), 2)
        self.assertEqual(len(self.api.writes), 1)
        owned = [row for row in self.api.issues if row['user']['login'] == ACTOR]
        self.assertEqual(len(owned), 1)
        self.assertIn({'login': ACTOR}, owned[0]['assignees'])
        self.assertIn(self.source_marker, owned[0]['body'].splitlines())
        self.assertEqual(self.api.issues[0], foreign_before)
        journal = self.journal()
        self.assertIsNone(journal.active_job())
        self.assertIn(self.source.key, journal.seen())

    def test_foreign_open_issue_marker_does_not_hold_queue(self):
        self.assert_foreign_issue_does_not_hold_queue('open')

    def test_foreign_closed_issue_marker_does_not_hold_queue(self):
        self.assert_foreign_issue_does_not_hold_queue('closed')

    def test_no_collision_creates_one_assigned_issue_and_releases_queue(self):
        self.assertEqual(self.run_controller()['status'], 'manual-primary-evidence')
        self.assertEqual(self.run_controller(NOW + timedelta(days=1))['status'], 'no-new-candidates')
        self.assertEqual(len(self.discovery), 2)
        self.assertEqual(len(self.api.writes), 1)
        self.assertEqual(self.api.issues[0]['user']['login'], ACTOR)
        self.assertEqual(self.api.issues[0]['assignees'], [{'login': ACTOR}])
        self.assertIsNone(self.journal().active_job())

    def test_owner_issue_on_later_page_wins_over_foreign_marker_collisions(self):
        self.api.issues = [issue(number, self.source_marker, author='public-contributor')
                           for number in range(1, 101)]
        owned = issue(101, self.source_marker)
        self.api.issues.append(owned)
        result = self.run_controller()
        self.assertEqual(result['status'], 'manual-primary-evidence')
        self.assertEqual(self.api.writes, [])
        self.assertIsNone(self.journal().active_job())
        self.assertIn(self.source.key, self.journal().seen())
        self.assertEqual(self.github.create_issue('Assess source', 'Evidence', self.source_marker,
                                                 adoption=True),
                         {'number': 101, 'url': owned['html_url']})
        self.assertEqual(self.api.writes, [])

    def assert_owner_problem_holds_queue(self):
        first = self.run_controller()
        self.assertEqual(first['status'], 'blocked')
        journal = self.journal()
        original = journal.active_job()
        journal.close()
        second = self.run_controller(NOW + timedelta(days=1))
        self.assertEqual(second['status'], 'blocked')
        self.assertEqual(second['job'], first['job'])
        journal = self.journal()
        self.assertEqual(journal.active_job()['key'], original['key'])
        self.assertNotIn(self.source.key, journal.seen())
        self.assertEqual(len(self.discovery), 1)
        self.assertEqual(self.api.writes, [])

    def test_duplicate_owner_issue_markers_remain_blocked(self):
        self.api.issues = [issue(1, self.source_marker), issue(2, self.source_marker)]
        self.assert_owner_problem_holds_queue()

    def test_owner_issue_without_owner_assignment_remains_blocked(self):
        self.api.issues = [issue(1, self.source_marker, assigned=False)]
        self.assert_owner_problem_holds_queue()

    def test_uncertain_write_is_not_replayed_for_foreign_only_marker(self):
        self.api.persist_issue = False
        self.api.issue_write_error = subprocess.TimeoutExpired('gh', 45)
        first = self.run_controller()
        self.assertEqual(first['status'], 'blocked')
        journal = self.journal()
        before = journal.effect(first['job'], self.effect_name)
        self.assertEqual(before['status'], 'pending')
        journal.close()
        self.api.issues.append(issue(1, self.source_marker, author='public-contributor'))
        second = self.run_controller(NOW + timedelta(days=1))
        self.assertEqual(second['status'], 'blocked')
        self.assertEqual(second['job'], first['job'])
        self.assertEqual(len(self.api.writes), 1)
        self.assertEqual(len(self.discovery), 1)
        journal = self.journal()
        self.assertEqual(journal.effect(first['job'], self.effect_name), before)
        self.assertEqual(journal.active_job()['key'], first['job'])
        self.assertNotIn(self.source.key, journal.seen())

    def test_uncertain_owner_write_reconciles_despite_foreign_collision(self):
        self.api.issue_write_error = subprocess.TimeoutExpired('gh', 45)
        first = self.run_controller()
        self.assertEqual(first['status'], 'blocked')
        self.assertEqual(len(self.api.issues), 1)
        owned = self.api.issues[0]
        self.api.issues.append(issue(2, self.source_marker, author='public-contributor', state='closed'))
        second = self.run_controller(NOW + timedelta(days=1))
        self.assertEqual(second['status'], 'manual-primary-evidence')
        self.assertEqual(len(self.api.writes), 1)
        self.assertEqual(len(self.discovery), 1)
        journal = self.journal()
        effect = journal.effect(first['job'], self.effect_name)
        self.assertEqual(effect['status'], 'complete')
        self.assertEqual(effect['result'], {'number': owned['number'], 'url': owned['html_url']})
        self.assertIsNone(journal.active_job())
        self.assertIn(self.source.key, journal.seen())

    def test_marker_substrings_and_pull_requests_do_not_replace_issue_creation(self):
        substring = issue(1, 'prefix ' + self.source_marker + ' suffix')
        pull_request = issue(2, self.source_marker)
        pull_request['pull_request'] = {'url': 'https://api.github.com/repos/' + REPO + '/pulls/2'}
        self.api.issues = [substring, pull_request]
        self.assertEqual(self.run_controller()['status'], 'manual-primary-evidence')
        self.assertEqual(len(self.api.writes), 1)
        self.assertEqual(self.api.issues[-1]['number'], 3)
        self.assertIsNone(self.journal().active_job())

    def test_foreign_only_comment_marker_is_not_owner_evidence(self):
        self.api.comments = [comment(1, author='public-contributor')]
        self.assertFalse(self.github.find_comment(7, MARKER))
        self.assertEqual(self.api.writes, [])

    def test_owner_comment_on_later_page_wins_over_foreign_marker_collisions(self):
        self.api.comments = [comment(number, author='public-contributor') for number in range(1, 101)]
        self.api.comments.append(comment(101))
        self.assertTrue(self.github.find_comment(7, MARKER))
        self.assertEqual(self.api.writes, [])

    def test_duplicate_owner_comment_markers_remain_ambiguous(self):
        self.api.comments = [comment(1), comment(2), comment(3, author='public-contributor')]
        with self.assertRaises(GitHubError):
            self.github.find_comment(7, MARKER)
        self.assertEqual(self.api.writes, [])

    def test_comment_substrings_are_not_assessment_evidence(self):
        self.api.comments = [comment(1, body='prefix ' + MARKER + ' suffix')]
        self.assertFalse(self.github.find_comment(7, MARKER))
        self.assertEqual(self.api.writes, [])

    def test_owner_comment_cannot_authorize_a_foreign_pr(self):
        self.api.pr['user']['login'] = 'public-contributor'
        self.api.comments = [comment(1)]
        with self.assertRaises(GitHubError):
            self.github.find_comment(7, MARKER)
        self.assertEqual(self.api.writes, [])


if __name__ == '__main__':
    unittest.main()
