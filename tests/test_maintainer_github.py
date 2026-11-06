"""Controlled HTTP boundary tests; no live GitHub mutations."""
import json
import subprocess
import unittest
from urllib.parse import urlsplit, parse_qs

from maintenance.github import GitHub, GitHubError

SHA = 'a' * 40
OTHER = 'b' * 40
REPO = 'Boom-Vitt/aic'
MARKER = '<!-- aic-maintainer:source-123 -->'


def snapshot(**changes):
    value = dict(number=7, html_url=f'https://github.com/{REPO}/pull/7', state='open',
                 merged=False, changed_files=1, user={'login': 'Boom-Vitt'},
                 head={'sha': SHA, 'ref': 'aic/research-example', 'repo': {'full_name': REPO, 'fork': False}},
                 base={'sha': OTHER, 'ref': 'main', 'repo': {'full_name': REPO}})
    value.update(changes)
    return value


def protection():
    return dict(required_status_checks={'strict': True, 'contexts': ['offline-contracts', 'aic/macmini', 'aic/independent-review']},
                enforce_admins={'enabled': True}, required_pull_request_reviews={'required_approving_review_count': 0},
                allow_force_pushes={'enabled': False}, allow_deletions={'enabled': False})


class API:
    def __init__(self):
        self.writes = []
        self.routes = {}
        self.remote_sha = SHA
        self.race_sha = None
        self.git_failure = None
        self.pr = snapshot()
        self.run = dict(id=1, name='offline-contracts', head_sha=SHA, status='completed', conclusion='success', app={'id': 15368, 'slug': 'github-actions'})
        self.statuses = [dict(id=i, sha=SHA, context=c, state='success', creator={'login': 'Boom-Vitt'}) for i, c in enumerate(('aic/macmini', 'aic/independent-review'), 1)]

    def __call__(self, argv, **kwargs):
        if argv[0] == 'git':
            self.writes.append(('GIT', 'owned-ref-delete', {}))
            if self.git_failure:
                raise self.git_failure
            if self.race_sha:
                self.remote_sha = self.race_sha
            lease = next(value for value in argv if value.startswith('--force-with-lease='))
            expected = lease.rsplit(':', 1)[1]
            if expected != self.remote_sha:
                return subprocess.CompletedProcess(argv, 1, '!\t:refs/heads/aic/research-example\t[rejected] (stale info)\n', '')
            self.remote_sha = None
            return subprocess.CompletedProcess(argv, 0, '-\t:refs/heads/aic/research-example\t[deleted]\n', '')
        method = argv[argv.index('--method') + 1]
        endpoint = argv[2]
        path = urlsplit(endpoint).path
        if method != 'GET':
            self.writes.append((method, path, json.loads(kwargs.get('input') or '{}')))
        route = self.routes.get((method, endpoint), self.routes.get((method, path)))
        if isinstance(route, Exception):
            raise route
        if callable(route):
            route = route(parse_qs(urlsplit(endpoint).query))
        if route is None:
            if path == '/user': route = {'login': 'Boom-Vitt'}
            elif path.endswith('/rules/branches/main'): route = []
            elif path.endswith('/branches/main/protection'): route = protection()
            elif path.endswith('/branches/main'): route = {'protected': True, 'commit': {'sha': OTHER}}
            elif path.endswith('/pulls/7/files'): route = [{'filename': 'record.md', 'status': 'added'}]
            elif path.endswith('/pulls/7'): route = self.pr
            elif '/check-runs' in path: route = {'total_count': 1, 'check_runs': [self.run]}
            elif path.endswith('/statuses'): route = self.statuses
            elif path.endswith('/merge'): route = {'merged': True, 'sha': OTHER, 'message': 'merged'}
            elif '/git/ref/heads/' in path: route = {'object': {'sha': SHA}}
            elif '/git/trees/' in path: route = {'truncated': False, 'tree': [{'path': name, 'type': 'blob', 'mode': '100644'} for name in ('maintenance/controller.py', 'maintenance/policy.py', 'scripts/maintain.py')]}
            elif method == 'DELETE': route = (204, '')
            else: raise AssertionError((method, endpoint))
        status, body = route if isinstance(route, tuple) else (200, json.dumps(route))
        return subprocess.CompletedProcess(argv, int(status >= 400), f'HTTP/2.0 {status} Status\r\n\r\n{body}', '')


class GatewayTests(unittest.TestCase):
    def test_all_writes_default_disabled(self):
        api = API(); gh = GitHub(runner=api)
        calls = [lambda: gh.ensure_labels(), lambda: gh.protect_main(), lambda: gh.create_issue('t', 'b', MARKER),
                 lambda: gh.create_pr('aic/research-example', 't', 'b'), lambda: gh.status(SHA, 'aic/macmini', 'success', 'ok'),
                 lambda: gh.comment(7, 'review'), lambda: gh.merge(7, SHA), lambda: gh.close_pr(7, SHA, 'obsolete'),
                 lambda: gh.delete_branch('aic/research-example', SHA)]
        for call in calls:
            with self.assertRaises(GitHubError): call()
        self.assertEqual(api.writes, [])

    def test_repo_and_actor_bound(self):
        with self.assertRaises(GitHubError): GitHub('foreign/repo')
        api = API(); api.routes['GET', '/user'] = {'login': 'someone'}
        with self.assertRaises(GitHubError): GitHub(runner=api).identity()

    def test_exact_issue_marker_and_complete_pagination(self):
        api = API()
        api.routes['GET', f'/repos/{REPO}/issues'] = lambda q: ([{'number': i, 'body': 'not exact ' + MARKER + ' suffix'} for i in range(100)] if q['page'] == ['1'] else [{'number': 500, 'body': 'record\n' + MARKER, 'html_url': 'url'}])
        self.assertEqual(GitHub(runner=api).find_issue(MARKER)['number'], 500)

    def test_ambiguous_or_partial_issue_lookup_refused(self):
        api = API(); path = f'/repos/{REPO}/issues'
        api.routes['GET', path] = [{'number': i, 'body': MARKER} for i in (1, 2)]
        with self.assertRaises(GitHubError): GitHub(runner=api).find_issue(MARKER)
        api.routes['GET', path] = lambda q: [{'number': i, 'body': ''} for i in range(100)]
        with self.assertRaises(GitHubError): GitHub(runner=api).find_issue(MARKER)

    def test_issue_creation_assigned_and_marked(self):
        api = API(); api.routes['GET', f'/repos/{REPO}/issues'] = []
        api.routes['POST', f'/repos/{REPO}/issues'] = {'number': 8, 'html_url': 'url', 'assignees': [{'login': 'Boom-Vitt'}], 'labels': [{'name': 'aic-research'}, {'name': 'aic-maintainer'}]}
        result = GitHub(write_enabled=True, runner=api).create_issue('Evidence', 'Body', MARKER)
        self.assertEqual(result['number'], 8)
        body = api.writes[0][2]
        self.assertEqual(body['assignees'], ['Boom-Vitt'])
        self.assertIn(MARKER, body['body'].splitlines())
        self.assertEqual(set(body['labels']), {'aic-research', 'aic-maintainer'})

    def test_guarded_merge_succeeds(self):
        api = API()
        self.assertTrue(GitHub(write_enabled=True, runner=api).merge(7, SHA)['merged'])
        self.assertEqual(api.writes[0][2], {'sha': SHA, 'merge_method': 'squash'})

    def test_foreign_fork_stale_and_missing_checks_cannot_merge(self):
        for mode in ('foreign', 'fork', 'stale', 'empty', 'failed', 'skipped', 'neutral', 'wrong-app', 'wrong-actor', 'wrong-sha'):
            with self.subTest(mode=mode):
                api = API()
                if mode == 'foreign': api.pr['user']['login'] = 'other'
                elif mode == 'fork': api.pr['head']['repo']['fork'] = True
                elif mode == 'stale': api.pr['head']['sha'] = OTHER
                elif mode == 'empty': api.statuses = []
                elif mode in ('failed', 'skipped', 'neutral'): api.run['conclusion'] = mode
                elif mode == 'wrong-app': api.run['app'] = {'slug': 'fake', 'id': 1}
                elif mode == 'wrong-actor': api.statuses[0]['creator']['login'] = 'other'
                elif mode == 'wrong-sha': api.run['head_sha'] = OTHER
                with self.assertRaises(GitHubError): GitHub(write_enabled=True, runner=api).merge(7, SHA)
                self.assertEqual(api.writes, [])

    def test_partial_files_refused(self):
        api = API(); api.pr['changed_files'] = 2
        with self.assertRaises(GitHubError): GitHub(runner=api).pr(7)

    def test_protection_never_overwrites_existing_policy(self):
        api = API(); gh = GitHub(write_enabled=True, runner=api)
        self.assertTrue(gh.protect_main()['protected']); self.assertEqual(api.writes, [])
        weak = protection(); weak['enforce_admins']['enabled'] = False
        api.routes['GET', f'/repos/{REPO}/branches/main/protection'] = weak
        with self.assertRaises(GitHubError): gh.protect_main()
        self.assertEqual(api.writes, [])

    def test_unknown_rules_refused(self):
        api = API(); api.routes['GET', f'/repos/{REPO}/rules/branches/main'] = [{'type': 'unknown'}]
        with self.assertRaises(GitHubError): GitHub(runner=api).protection()

    def test_branch_guards(self):
        for branch in ('main', 'feature/test', 'aic/research-../main', 'aic/research-x/child'):
            api = API()
            with self.assertRaises(GitHubError): GitHub(write_enabled=True, runner=api).delete_branch(branch, SHA)
            self.assertEqual(api.writes, [])
        api = API()
        with self.assertRaises(GitHubError): GitHub(write_enabled=True, runner=api).delete_branch('aic/research-example', OTHER)
        self.assertEqual(api.writes, [])

    def test_close_foreign_or_stale_refused(self):
        api = API()
        with self.assertRaises(GitHubError): GitHub(write_enabled=True, runner=api).close_pr(7, OTHER, 'stale')
        self.assertEqual(api.writes, [])

    def test_mutation_uncertainty_without_retry(self):
        for response, uncertain in (((503, '{}'), True), ((422, '{}'), False), ((200, 'not json'), True), (subprocess.TimeoutExpired('gh', 30), True)):
            api = API(); api.routes['POST', f'/repos/{REPO}/statuses/{SHA}'] = response
            with self.assertRaises(GitHubError) as caught:
                GitHub(write_enabled=True, runner=api).status(SHA, 'aic/macmini', 'success', 'ok')
            self.assertEqual(caught.exception.uncertain, uncertain)
            self.assertEqual(len(api.writes), 1)

    def test_no_false_review_approval_or_foreign_context(self):
        api = API()
        with self.assertRaises(GitHubError): GitHub(write_enabled=True, runner=api).status(SHA, 'offline-contracts', 'success', 'fake')
        self.assertEqual(api.writes, [])

    def test_real_status_schema_and_latest_failure(self):
        api = API()
        for status in api.statuses:
            status.pop('sha')
        gh = GitHub(runner=api)
        self.assertEqual(gh.checks(SHA)['aic/macmini'], 'success')
        api.statuses.append(dict(id=100, context='aic/macmini', state='failure', creator={'login': 'Boom-Vitt'}))
        self.assertEqual(gh.checks(SHA)['aic/macmini'], 'failure')

    def test_install_only_after_explicit_call_and_confirm(self):
        api = API()
        branch_path = f'/repos/{REPO}/branches/main'
        api.routes['GET', branch_path] = {'protected': False}
        def install(query):
            api.routes['GET', branch_path] = {'protected': True}
            return protection()
        api.routes['PUT', branch_path + '/protection'] = install
        gh = GitHub(write_enabled=True, runner=api)
        self.assertFalse(gh.protection()['protected'])
        self.assertEqual(api.writes, [])
        self.assertTrue(gh.protect_main()['protected'])
        self.assertEqual(len(api.writes), 1)
        policy = api.writes[0][2]
        self.assertTrue(policy['enforce_admins'])
        self.assertFalse(policy['allow_force_pushes'])
        self.assertFalse(policy['allow_deletions'])
        self.assertEqual(set(policy['required_status_checks']['contexts']), {'offline-contracts', 'aic/macmini', 'aic/independent-review'})

    def test_initial_required_checks_cannot_precede_maintainer_publication(self):
        for state in ('missing', 'partial-tree', 'symlink'):
            api = API()
            branch = f'/repos/{REPO}/branches/main'
            api.routes['GET', branch] = {'protected': False}
            def install(query):
                api.routes['GET', branch] = {'protected': True}
                return protection()
            api.routes['PUT', branch + '/protection'] = install
            tree = {'truncated': False, 'tree': []}
            if state != 'missing':
                tree['tree'] = [{'path': name, 'type': 'blob', 'mode': '100644'} for name in ('maintenance/controller.py', 'maintenance/policy.py', 'scripts/maintain.py')]
                if state == 'partial-tree':
                    tree['truncated'] = True
                else:
                    tree['tree'][0]['mode'] = '120000'
            api.routes['GET', f'/repos/{REPO}/git/trees/{SHA}'] = tree
            github = GitHub(write_enabled=True, runner=api)
            with self.subTest(state=state), self.assertRaises(GitHubError):
                github.protect_main()
            self.assertFalse(github.protection()['protected'])
            self.assertEqual(api.writes, [])

    def test_find_pr_refuses_foreign_head(self):
        api = API(); foreign = snapshot()
        foreign['head']['repo']['full_name'] = 'other/aic'
        api.routes['GET', f'/repos/{REPO}/pulls'] = [foreign]
        with self.assertRaises(GitHubError): GitHub(runner=api).find_pr('aic/research-example')
        self.assertEqual(api.writes, [])

    def test_complete_pr_files_and_head_change_during_snapshot(self):
        api = API(); api.pr['changed_files'] = 101
        api.routes['GET', f'/repos/{REPO}/pulls/7/files'] = lambda q: [
            {'filename': f'record-{i}.md', 'status': 'added'}
            for i in (range(100) if q['page'] == ['1'] else [100])]
        self.assertEqual(len(GitHub(runner=api).pr(7)['files']), 101)
        reads = []
        def changing(query):
            reads.append(True)
            changed = snapshot()
            if len(reads) > 1:
                changed['head']['sha'] = OTHER
            return changed
        api.routes['GET', f'/repos/{REPO}/pulls/7'] = changing
        api.routes['GET', f'/repos/{REPO}/pulls/7/files'] = [{'filename': 'record.md', 'status': 'added'}]
        with self.assertRaises(GitHubError): GitHub(runner=api).pr(7)

    def test_owned_branch_delete_and_close_have_single_effect(self):
        api = API(); gh = GitHub(write_enabled=True, runner=api)
        gh.delete_branch('aic/research-example', SHA)
        self.assertEqual(len(api.writes), 1)
        api.writes.clear()
        gh.close_pr(7, SHA, 'superseded')
        self.assertEqual(len(api.writes), 1)
        self.assertEqual(api.writes[0][2]['state'], 'closed')

    def test_status_transition_and_owned_comment_evidence(self):
        api = API(); gh = GitHub(write_enabled=True, runner=api)
        def status_response(query):
            payload = api.writes[-1][2]
            api.statuses.append(dict(id=99, context=payload['context'], state=payload['state'], creator={'login': 'Boom-Vitt'}))
            return dict(id=99, context=payload['context'], state=payload['state'])
        api.routes['POST', f'/repos/{REPO}/statuses/{SHA}'] = status_response
        gh.status(SHA, 'aic/independent-review', 'pending', 'Review reserved')
        self.assertEqual(gh.checks(SHA)['aic/independent-review'], 'pending')
        api.routes['POST', f'/repos/{REPO}/issues/7/comments'] = {'id': 321}
        gh.comment(7, 'Independent assessment for exact head ' + SHA)
        self.assertEqual(api.writes[-1][1], f'/repos/{REPO}/issues/7/comments')

    def test_labels_preserve_existing_and_pr_creation_is_reconciled(self):
        api = API(); gh = GitHub(write_enabled=True, runner=api)
        api.routes['GET', f'/repos/{REPO}/labels'] = [{'name': 'aic-research'}, {'name': 'unrelated'}]
        api.routes['POST', f'/repos/{REPO}/labels'] = {'id': 1}
        gh.ensure_labels()
        self.assertEqual({effect[2]['name'] for effect in api.writes}, {'aic-adoption', 'aic-maintainer'})
        api.writes.clear()
        api.routes['GET', f'/repos/{REPO}/pulls'] = []
        api.routes['POST', f'/repos/{REPO}/pulls'] = snapshot()
        result = gh.create_pr('aic/research-example', 'Research', 'Evidence')
        self.assertEqual(result['head_sha'], SHA)
        self.assertEqual(len(api.writes), 1)
        api.routes['POST', f'/repos/{REPO}/pulls'] = {'number': 7}
        with self.assertRaises(GitHubError) as error:
            gh.create_pr('aic/research-example', 'Research', 'Evidence')
        self.assertTrue(error.exception.uncertain)

    def test_silently_dropped_issue_assignment_requires_reconciliation(self):
        api = API()
        api.routes['GET', f'/repos/{REPO}/issues'] = []
        api.routes['POST', f'/repos/{REPO}/issues'] = {'number': 8, 'html_url': 'url', 'assignees': [], 'labels': []}
        with self.assertRaises(GitHubError) as caught:
            GitHub(write_enabled=True, runner=api).create_issue('Research', 'Evidence', MARKER)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(len(api.writes), 1)

    def test_conditional_delete_preserves_concurrently_changed_ref(self):
        api = API(); api.race_sha = OTHER
        with self.assertRaises(GitHubError) as caught:
            GitHub(write_enabled=True, runner=api).delete_branch('aic/research-example', SHA)
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(api.remote_sha, OTHER)
        self.assertEqual(len(api.writes), 1)
        self.assertEqual(api.writes[0][0], 'GIT')

    def test_conditional_delete_transport_failure_never_retried(self):
        api = API(); api.git_failure = subprocess.TimeoutExpired('git', 45)
        with self.assertRaises(GitHubError) as caught:
            GitHub(write_enabled=True, runner=api).delete_branch('aic/research-example', SHA)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(len(api.writes), 1)
