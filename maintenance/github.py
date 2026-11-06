"""Fail-closed, owner-bound GitHub REST gateway using existing gh authentication.

Writes are single attempts. An uncertain error requires read-only reconciliation by
its caller, never replay. No review approval is fabricated: review evidence uses
comments and owner-authored commit statuses.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from urllib.parse import quote, urlencode

REPO = 'Boom-Vitt/aic'
ACTOR = 'Boom-Vitt'
REQUIRED = ('offline-contracts', 'aic/macmini', 'aic/independent-review')
LOCAL = REQUIRED[1:]
MAX_PAGES = 100


class GitHubError(RuntimeError):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


class GitHub:
    def __init__(self, repo=REPO, *, write_enabled=False, runner=None, working_directory=None):
        if repo != REPO:
            raise GitHubError('Repository is not approved')
        self.repo = repo
        self.write_enabled = write_enabled
        self.runner = runner or subprocess.run
        self.working_directory = os.fspath(working_directory or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.root = '/repos/' + repo

    def _write(self):
        if not self.write_enabled:
            raise GitHubError('GitHub writes are disabled')
        self.identity()

    def _api(self, path, method='GET', data=None, *, missing=False):
        mutation = method != 'GET'
        if mutation and not self.write_enabled:
            raise GitHubError('GitHub writes are disabled')
        argv = ['gh', 'api', path, '--hostname', 'github.com', '--method', method,
                '--include', '-H', 'Accept: application/vnd.github+json',
                '-H', 'X-GitHub-Api-Version: 2022-11-28']
        if data is not None:
            argv += ['--input', '-']
        try:
            result = self.runner(argv, input=json.dumps(data) if data is not None else None,
                                 capture_output=True, text=True, timeout=45, shell=False)
        except (OSError, subprocess.SubprocessError):
            raise GitHubError('GitHub transport failed', uncertain=mutation) from None
        text = result.stdout.replace('\r\n', '\n')
        headers, separator, body = text.partition('\n\n')
        match = re.match(r'HTTP/\S+ (\d{3})(?: |$)', headers)
        if not separator or not match:
            raise GitHubError('GitHub response has no reliable HTTP status', uncertain=mutation)
        code = int(match[1])
        if code == 404 and missing:
            return None
        if not 200 <= code < 300:
            raise GitHubError(f'GitHub HTTP {code}', uncertain=mutation and code >= 500)
        if result.returncode:
            raise GitHubError('GitHub command failed after response', uncertain=mutation)
        if code == 204:
            return None
        try:
            value = json.loads(body)
            if mutation and not isinstance(value, dict):
                raise GitHubError('Malformed GitHub mutation response', uncertain=True)
            return value
        except (ValueError, TypeError):
            raise GitHubError('GitHub returned invalid JSON', uncertain=mutation) from None

    def _pages(self, path, *, key=None, params=None):
        rows = []
        total = None
        for page in range(1, MAX_PAGES + 1):
            query = dict(params or {}, per_page=100, page=page)
            value = self._api(path + '?' + urlencode(query))
            if key:
                if not isinstance(value, dict) or type(value.get('total_count')) is not int:
                    raise GitHubError('Incomplete paginated GitHub response')
                if total is not None and total != value['total_count']:
                    raise GitHubError('GitHub result changed during pagination')
                total = value['total_count']
                value = value.get(key)
            if not isinstance(value, list) or len(value) > 100 or any(not isinstance(x, dict) for x in value):
                raise GitHubError('Malformed GitHub page')
            rows.extend(value)
            if len(value) < 100:
                if total is not None and len(rows) != total:
                    raise GitHubError('Truncated GitHub result')
                return rows
        raise GitHubError('GitHub pagination bound reached; lookup is incomplete')

    @staticmethod
    def _sha(sha):
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{40}', sha):
            raise GitHubError('Invalid full commit SHA')
        return sha

    @staticmethod
    def _branch(branch):
        if not isinstance(branch, str) or not re.fullmatch(r'aic/research-[A-Za-z0-9][A-Za-z0-9_-]{0,119}', branch):
            raise GitHubError('Branch is not an owned research branch')
        return branch

    @staticmethod
    def _number(number):
        if type(number) is not int or number < 1:
            raise GitHubError('Invalid issue or PR number')
        return str(number)

    @staticmethod
    def _marker(marker):
        if not isinstance(marker, str) or not re.fullmatch(r'<!-- aic-maintainer:[A-Za-z0-9:._/-]{1,240} -->', marker):
            raise GitHubError('Invalid controller marker')
        return marker

    @staticmethod
    def _object(value, keys, *, mutation=False):
        if not isinstance(value, dict) or any(k not in value for k in keys):
            raise GitHubError('Incomplete GitHub object', uncertain=mutation)
        return value

    def identity(self):
        value = self._api('/user')
        if not isinstance(value, dict) or value.get('login') != ACTOR:
            raise GitHubError('Authenticated GitHub actor is not approved')
        return ACTOR

    def main_sha(self):
        value = self._api(self.root + '/branches/main')
        try:
            return self._sha(value['commit']['sha'])
        except (KeyError, TypeError):
            raise GitHubError('Missing main SHA') from None

    def protection(self):
        # Unknown/applicable rulesets cannot safely be normalized or overwritten.
        rules = self._pages(self.root + '/rules/branches/main')
        if rules:
            raise GitHubError('Applicable rules require explicit owner policy review')
        branch = self._api(self.root + '/branches/main')
        if not isinstance(branch, dict) or type(branch.get('protected')) is not bool:
            raise GitHubError('Unknown branch protection state')
        if not branch['protected']:
            return dict(protected=False, strict=False, enforce_admins=False, required_contexts=[],
                        required_pr=False, allow_force_pushes=False, allow_deletions=False)
        value = self._api(self.root + '/branches/main/protection')
        try:
            checks = value['required_status_checks']
            contexts = checks['contexts']
            strict = checks['strict']
            admins = value['enforce_admins']['enabled']
            force = value['allow_force_pushes']['enabled']
            deletion = value['allow_deletions']['enabled']
            reviews = value['required_pull_request_reviews']
            bypass = reviews.get('bypass_pull_request_allowances', {}) if isinstance(reviews, dict) else {}
            if any(bypass.values()):
                raise GitHubError('PR bypass allowances are incompatible')
            if not isinstance(contexts, list) or any(not isinstance(c, str) for c in contexts) or any(type(b) is not bool for b in (strict, admins, force, deletion)):
                raise GitHubError('Unknown protection fields')
            return dict(protected=True, strict=strict, enforce_admins=admins,
                        required_contexts=sorted(set(contexts)), required_pr=isinstance(reviews, dict),
                        allow_force_pushes=force, allow_deletions=deletion)
        except (KeyError, TypeError, AttributeError):
            raise GitHubError('Incomplete protection policy') from None

    @staticmethod
    def _compliant(policy):
        return (policy['protected'] and policy['strict'] and policy['enforce_admins'] and policy['required_pr']
                and not policy['allow_force_pushes'] and not policy['allow_deletions']
                and set(REQUIRED) <= set(policy['required_contexts']))

    def _require_published_maintainer(self):
        reference = self._api(self.root + '/git/ref/heads/main')
        try:
            sha = self._sha(reference['object']['sha'])
        except (KeyError, TypeError):
            raise GitHubError('Published main identity is incomplete') from None
        tree = self._api(self.root + '/git/trees/' + sha + '?recursive=1')
        if not isinstance(tree, dict) or tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
            raise GitHubError('Published source inventory is incomplete; protection was not changed')
        try:
            files = {entry['path']: entry for entry in tree['tree']}
        except (KeyError, TypeError):
            raise GitHubError('Published source inventory is malformed') from None
        required = ('maintenance/controller.py', 'maintenance/policy.py', 'scripts/maintain.py')
        if len(files) != len(tree['tree']) or any(
                path not in files or files[path].get('type') != 'blob' or files[path].get('mode') not in ('100644', '100755')
                for path in required):
            raise GitHubError('Publish and verify the initial owner-reviewed maintainer in main before enabling its required checks')

    def protect_main(self):
        self._write()
        self._require_published_maintainer()
        policy = self.protection()
        if policy['protected']:
            if not self._compliant(policy):
                raise GitHubError('Existing protection is nonmatching; refusing to overwrite')
            return policy
        self._api(self.root + '/branches/main/protection', 'PUT', {
            'required_status_checks': {'strict': True, 'contexts': list(REQUIRED)},
            'enforce_admins': True, 'required_pull_request_reviews': {
                'dismiss_stale_reviews': True, 'require_code_owner_reviews': False,
                'required_approving_review_count': 0},
            'restrictions': None, 'allow_force_pushes': False, 'allow_deletions': False})
        try:
            policy = self.protection()
            if not self._compliant(policy):
                raise GitHubError('Installed protection could not be confirmed')
            return policy
        except GitHubError:
            raise GitHubError('Protection installation requires reconciliation', uncertain=True) from None

    def ensure_labels(self):
        self._write()
        existing = {row.get('name') for row in self._pages(self.root + '/labels')}
        for name, color in (('aic-research', '0969da'), ('aic-adoption', '8250df'), ('aic-maintainer', '1a7f37')):
            if name not in existing:
                self._api(self.root + '/labels', 'POST', {'name': name, 'color': color})

    def find_issue(self, marker):
        self._marker(marker)
        rows = self._pages(self.root + '/issues', params={'state': 'all'})
        matches = [r for r in rows if 'pull_request' not in r and marker in (r.get('body') or '').splitlines()]
        if len(matches) > 1:
            raise GitHubError('Ambiguous controller issue marker')
        return matches[0] if matches else None

    def create_issue(self, title, body, marker, *, adoption=False):
        self._write()
        self._marker(marker)
        found = self.find_issue(marker)
        labels = ['aic-adoption' if adoption else 'aic-research', 'aic-maintainer']
        if found:
            value = found
        else:
            body = body if marker in body.splitlines() else body + '\n\n' + marker
            value = self._api(self.root + '/issues', 'POST', {'title': title, 'body': body,
                              'assignees': [ACTOR], 'labels': labels})
        self._object(value, ('number', 'html_url', 'assignees', 'labels'), mutation=not bool(found))
        try:
            assigned = {row['login'] for row in value['assignees']}
            actual_labels = {row if isinstance(row, str) else row['name'] for row in value['labels']}
            if ACTOR not in assigned or not set(labels) <= actual_labels:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise GitHubError('Issue assignment/labels require reconciliation', uncertain=not bool(found)) from None
        return {'number': value['number'], 'url': value['html_url']}

    def _owned(self, value, expected_sha=None):
        try:
            self._branch(value['head']['ref'])
            self._sha(value['head']['sha'])
            self._sha(value['base']['sha'])
            if (value['head']['repo']['full_name'] != REPO or value['head']['repo']['fork'] is not False
                    or value['base']['repo']['full_name'] != REPO or value['base']['ref'] != 'main'
                    or value['user']['login'] != ACTOR
                    or (expected_sha is not None and value['head']['sha'] != expected_sha)):
                raise GitHubError('PR ownership or expected head does not match')
        except (KeyError, TypeError):
            raise GitHubError('Incomplete PR ownership evidence') from None
        return value

    def find_pr(self, branch):
        self._branch(branch)
        rows = self._pages(self.root + '/pulls', params={'state': 'all', 'head': ACTOR + ':' + branch, 'base': 'main'})
        matches = [r for r in rows if (r.get('head') or {}).get('ref') == branch]
        if len(matches) > 1:
            raise GitHubError('Ambiguous research PR branch')
        if not matches:
            return None
        self._owned(matches[0])
        return self.pr(matches[0]['number'])

    def create_pr(self, branch, title, body):
        self._write()
        self._branch(branch)
        found = self.find_pr(branch)
        if found:
            return {k: found[k] for k in ('number', 'url', 'head_sha')}
        value = self._api(self.root + '/pulls', 'POST', {'head': branch, 'base': 'main', 'title': title, 'body': body, 'maintainer_can_modify': False})
        try:
            self._owned(value)
            self._object(value, ('number', 'html_url'))
        except GitHubError:
            raise GitHubError('Created PR requires reconciliation', uncertain=True) from None
        return {'number': value['number'], 'url': value['html_url'], 'head_sha': value['head']['sha']}

    def pr(self, number):
        path = self.root + '/pulls/' + self._number(number)
        value = self._owned(self._api(path))
        self._object(value, ('number', 'html_url', 'state', 'merged', 'changed_files'))
        files = self._pages(path + '/files')
        if type(value['changed_files']) is not int or len(files) != value['changed_files'] or len(files) >= 3000:
            raise GitHubError('PR file listing incomplete or at GitHub truncation limit')
        if len({f.get('filename') for f in files}) != len(files):
            raise GitHubError('Duplicate PR file listing')
        normalized = []
        for row in files:
            self._object(row, ('filename', 'status'))
            normalized.append({'filename': row['filename'], 'status': row['status'], 'previous_filename': row.get('previous_filename')})
        again = self._owned(self._api(path), value['head']['sha'])
        if again['base']['sha'] != value['base']['sha'] or again.get('state') != value['state']:
            raise GitHubError('PR changed during snapshot')
        return dict(number=value['number'], url=value['html_url'], state=value['state'], merged=value['merged'],
                    head_sha=value['head']['sha'], base_sha=value['base']['sha'], head_ref=value['head']['ref'],
                    head_repo=REPO, base_repo=REPO, author=ACTOR, files=normalized)

    def checks(self, sha):
        self._sha(sha)
        runs = self._pages(self.root + '/commits/' + sha + '/check-runs', key='check_runs', params={'filter': 'latest'})
        statuses = self._pages(self.root + '/commits/' + sha + '/statuses')
        result = dict.fromkeys(REQUIRED, 'missing')
        matching = [r for r in runs if r.get('name') == REQUIRED[0]]
        if matching:
            # Ambiguous same-name jobs never become an accidental green.
            valid = [r for r in matching if r.get('head_sha') == sha and (r.get('app') or {}).get('slug') == 'github-actions' and (r.get('app') or {}).get('id') == 15368]
            if len(valid) != len(matching):
                result[REQUIRED[0]] = 'failure'
            elif all(r.get('status') == 'completed' and r.get('conclusion') == 'success' for r in valid):
                result[REQUIRED[0]] = 'success'
            elif any(r.get('status') == 'completed' for r in valid):
                result[REQUIRED[0]] = 'failure'
            else:
                result[REQUIRED[0]] = 'pending'
        for context in LOCAL:
            matching = [s for s in statuses if s.get('context') == context]
            if matching:
                if any(type(s.get('id')) is not int for s in matching):
                    raise GitHubError('Status ordering evidence missing')
                latest = max(matching, key=lambda s: s['id'])
                # Status rows have no SHA field: the full-SHA endpoint binds them.
                if latest.get('sha', sha) != sha or (latest.get('creator') or {}).get('login') != ACTOR:
                    result[context] = 'failure'
                else:
                    state = latest.get('state')
                    result[context] = state if state in ('success', 'pending') else 'failure'
        return result

    def status(self, sha, context, state, description):
        self._write()
        self._sha(sha)
        if context not in LOCAL or state not in ('pending', 'success', 'failure', 'error'):
            raise GitHubError('Unowned status context or invalid state')
        value = self._api(self.root + '/statuses/' + sha, 'POST', {'context': context, 'state': state, 'description': description[:140]})
        self._object(value, ('id', 'context', 'state'), mutation=True)
        if value['context'] != context or value['state'] != state:
            raise GitHubError('Status write requires reconciliation', uncertain=True)

    def comment(self, number, body):
        self._write()
        # Assessment evidence on an owned PR, never a review approval endpoint.
        self.pr(number)
        value = self._api(self.root + '/issues/' + self._number(number) + '/comments', 'POST', {'body': body})
        self._object(value, ('id',), mutation=True)

    def branch_sha(self, branch):
        self._branch(branch)
        value = self._api(self.root + '/git/ref/heads/' + quote(branch, safe=''), missing=True)
        if value is None:
            return None
        try:
            return self._sha(value['object']['sha'])
        except (KeyError, TypeError):
            raise GitHubError('Incomplete remote branch identity') from None

    def find_comment(self, number, marker):
        self._marker(marker)
        self.pr(number)
        rows = self._pages(self.root + '/issues/' + self._number(number) + '/comments')
        matches = [row for row in rows if marker in (row.get('body') or '').splitlines()]
        if len(matches) > 1 or any((row.get('user') or {}).get('login') != ACTOR for row in matches):
            raise GitHubError('Ambiguous or foreign assessment marker')
        return bool(matches)

    def merge(self, number, expected_sha):
        self._write()
        self._sha(expected_sha)
        value = self.pr(number)
        if value['state'] != 'open' or value['merged'] is not False or value['head_sha'] != expected_sha:
            raise GitHubError('PR is not open at the expected head')
        if not self._compliant(self.protection()):
            raise GitHubError('Required no-bypass protection is absent')
        if any(state != 'success' for state in self.checks(expected_sha).values()):
            raise GitHubError('Required checks are not successful')
        # Re-read ownership after slower gates; API SHA guards concurrent head edits.
        self._owned(self._api(self.root + '/pulls/' + self._number(number)), expected_sha)
        result = self._api(self.root + '/pulls/' + str(number) + '/merge', 'PUT', {'sha': expected_sha, 'merge_method': 'squash'})
        self._object(result, ('merged', 'sha', 'message'), mutation=True)
        if type(result['merged']) is not bool:
            raise GitHubError('Uncertain merge response', uncertain=True)
        return {k: result[k] for k in ('merged', 'sha', 'message')}

    def close_pr(self, number, expected_sha, reason):
        self._write()
        self._sha(expected_sha)
        path = self.root + '/pulls/' + self._number(number)
        value = self._owned(self._api(path), expected_sha)
        if value.get('state') != 'open' or value.get('merged') is not False:
            raise GitHubError('Only an open unmerged owned PR may be closed')
        # Closing has no conditional-SHA API; no comment write before the guard.
        self._api(path, 'PATCH', {'state': 'closed'})

    def delete_branch(self, branch, expected_sha):
        self._write()
        self._branch(branch)
        self._sha(expected_sha)
        path = self.root + '/git/ref/heads/' + quote(branch, safe='')
        value = self._api(path)
        if not isinstance(value, dict) or (value.get('object') or {}).get('sha') != expected_sha:
            raise GitHubError('Remote branch SHA does not match')
        ref = 'refs/heads/' + branch
        # Conditional deletion only: the server rejects a concurrently changed ref.
        # Empty helper resets inherited helpers; this fixed helper uses existing gh auth.
        argv = ['git', '-c', 'core.hooksPath=/dev/null',
                '-c', 'credential.helper=',
                '-c', 'credential.https://github.com.helper=!gh auth git-credential',
                '-c', 'credential.interactive=false', '-c', 'core.askPass=',
                'push', '--porcelain', '--force-with-lease=' + ref + ':' + expected_sha,
                'https://github.com/Boom-Vitt/aic.git', ':' + ref]
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment['GIT_TERMINAL_PROMPT'] = '0'
        try:
            result = self.runner(argv, capture_output=True, text=True, timeout=45,
                                 shell=False, env=environment,
                                 cwd=self.working_directory)
        except (OSError, subprocess.SubprocessError):
            raise GitHubError('Conditional branch deletion transport failed', uncertain=True) from None
        if result.returncode:
            stale = '[rejected] (stale info)' in result.stdout
            raise GitHubError('Conditional branch deletion rejected' if stale else
                              'Branch deletion requires reconciliation', uncertain=not stale)
