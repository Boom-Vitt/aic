"""One bounded maintenance cycle; models never receive tools or GitHub authority."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import time
import subprocess
import sys

from . import collector, policy
from .agents import AgentError, NoToolAgents, MAX_PACKET_BYTES, MAX_RESULT_BYTES, MAX_TRACE_BYTES
from .contracts import Candidate, CollectionBatch, SourceDocument
from .github import GitHub, GitHubError
from .state import State, StateError


class MaintenanceBlocked(RuntimeError):
    pass


def candidates_from_json(values: list[dict]) -> list[Candidate]:
    return [Candidate(**dict(value, authors=tuple(value['authors']), documents=tuple(SourceDocument(**doc) for doc in value['documents']))) for value in values]


def _output_limits(role: str, candidates: list[Candidate], record_count: int = 0) -> dict:
    return policy.output_limits(role, candidate_count=len(candidates), record_count=record_count,
                                packet_bytes=MAX_PACKET_BYTES, result_bytes=MAX_RESULT_BYTES,
                                trace_bytes=MAX_TRACE_BYTES, source_text_chars=collector.MAX_TEXT_CHARS,
                                source_response_bytes=collector.MAX_RESPONSE_BYTES)


def research_packet(candidates: list[Candidate], templates: set[str]) -> dict:
    return dict(role='research', source_digest=policy.source_digest(candidates), sources=[asdict(candidate) for candidate in candidates], allowed_templates=sorted(templates),
        output_limits=_output_limits('research', candidates),
        format_rules='Obey output_limits and output_schema. Write original notes and tasks in English. Put URLs only in license.evidence_url; free-text fields must not introduce links. Use supplied source URLs, optionally with a simple section anchor.',
        task=('Assess ONLY the supplied primary evidence. Create original factual notes, not new workflow instructions. Reject irrelevant or scientifically unsupported candidates; use manual_tasks when a material source/rights/method decision cannot be established. Preprints and first-party engineering are not peer-reviewed trials. Distinguish matched budgets from unequal resources, coverage from selected correctness, and source-declared results from reproduction. Keep publication content rights separate from code licenses. Unknown/restrictive rights are reference-only, never copying permission. Do not reproduce long source phrases, prompts, tables or code. Every supplied candidate must appear exactly once across records/manual_tasks/rejected. No new URL, candidate identity, capability claim or template. Adoption tasks are manual proposals, never execution. Return exactly JSON matching output_schema; no markdown fences.'),
        output_schema={'schema_version': 1, 'records': [{'candidate_key': 'exact supplied key', 'summary': 'original factual paragraph', 'methods': ['original factual method'], 'findings': ['source-grounded observed finding'], 'limitations': ['material applicability/resource/evaluation limit'], 'license': {'status': 'verified or unverified', 'identifier': 'actual content license or unknown', 'evidence_url': 'supplied primary URL', 'observation': 'original rights observation with uncertainty'}, 'relevant_templates': ['existing applicable ID, maximum three'], 'adoption_task': 'bounded owner-decided applicability task', 'reference_only': True}], 'manual_tasks': [{'candidate_key': 'exact supplied key', 'reason': 'specific material prerequisite'}], 'rejected': [{'candidate_key': 'exact supplied key', 'reason': 'specific relevance/evidence reason'}]})


def review_packet(candidates: list[Candidate], records: list[dict], text: str, head_sha: str, path: str) -> dict:
    return dict(role='review', head_sha=head_sha, source_digest=policy.source_digest(candidates), sources=[asdict(candidate) for candidate in candidates], proposed_file=path, proposed_text=text,
        output_limits=_output_limits('review', candidates, len(records)),
        format_rules='Obey output_limits and output_schema. Write assessments in English. Put URLs only in findings.source_url; keep free-text assessments free of links. A source URL must be supplied, optionally with a simple section anchor.',
        task=('Independently review this exact proposed PR artifact/head against the original primary sources and research-only policy, not a generator self-grade. Check every factual method/finding/limitation, version, author credit, tier, rights evidence and original wording. Unknown or restrictive publication rights can be explicitly reference-only; no copied source expression, figures or code. The only permitted change is a new dated factual research record, never agent behavior, instructions, code, CI or permissions. Do not rank vendors universally or treat agreement as experiment reproduction. An unsupported claim, missing scientific caveat, copied passage or ambiguous material prerequisite means reject/manual, not approval. Return exactly JSON matching output_schema, no markdown fences.'),
        output_schema={'schema_version': 1, 'head_sha': head_sha, 'source_digest': policy.source_digest(candidates), 'verdict': 'approve or reject or manual', 'assessments': [{'candidate_key': record['candidate_key'], 'grounding': 'evidence-backed assessment', 'rights': 'specific content-rights assessment', 'originality': 'specific original-expression assessment', 'scope': 'specific research-only assessment', 'verdict': 'approve or reject or manual'} for record in records], 'findings': [{'candidate_key': 'actual record key', 'severity': 'blocker or warning', 'message': 'specific factual finding; use empty findings list if none', 'source_url': 'supplied primary source'}]})


def _private_json(path: Path, value: object):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = policy.canonical(value) + b'\n'
    if path.is_symlink():
        raise MaintenanceBlocked('Linked private evidence is refused.')
    if path.exists():
        if path.read_bytes() != content:
            raise MaintenanceBlocked('Existing private evidence differs; preserve it for owner inspection.')
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)


class Controller:
    def __init__(self, project: Path, *, publish=False, github=None, agents_factory=NoToolAgents, collect=collector.collect, bootstrap_fetch=collector.fetch_candidate, now=None, clock=None):
        self.project = Path(project).absolute()
        self.publish = publish
        self.github = github or GitHub(write_enabled=publish, working_directory=self.project)
        self.agents_factory = agents_factory
        self.collect = collect
        self.bootstrap_fetch = bootstrap_fetch
        self.clock = clock or ((lambda: now) if now is not None else (lambda: datetime.now(timezone.utc)))
        self.now = self.clock()
        self.day = policy.day_key(self.now)
        self.private = self.project / '.work' / 'maintainer'
        self.state = None

    def _git(self, checkout: Path, *arguments: str, binary=False, commit_time=None):
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment['GIT_TERMINAL_PROMPT'] = '0'
        if commit_time is not None:
            environment.update(GIT_AUTHOR_DATE=commit_time, GIT_COMMITTER_DATE=commit_time)
        argv = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'credential.helper=',
                '-c', 'credential.https://github.com.helper=!gh auth git-credential', '-c', 'credential.interactive=false', '-c', 'core.askPass=', *arguments]
        result = subprocess.run(argv, cwd=checkout, env=environment, capture_output=True, text=not binary, timeout=120, shell=False)
        if result.returncode:
            raise MaintenanceBlocked(f'Git operation failed (exit {result.returncode}); no reset, force-push or retry was performed.')
        return result.stdout if binary else result.stdout.strip()

    def _ready(self):
        self.github.identity()
        protection = self.github.protection()
        if not (protection['protected'] and protection['strict'] and protection['enforce_admins'] and protection['required_pr']
                and not protection['allow_force_pushes'] and not protection['allow_deletions'] and set(policy.CONTEXTS) <= set(protection['required_contexts'])):
            raise MaintenanceBlocked('Required no-bypass branch protection is absent; explicitly configure it before unattended work.')

    def _save(self, key: str, data: dict, status: str):
        self.state.save_job(key, status, data)

    def _effect(self, key: str, name: str, descriptor: dict, action, reconcile=None):
        existing = self.state.effect(key, name)
        if existing is not None and existing['descriptor'] != descriptor:
            raise MaintenanceBlocked('External-effect identity changed; preserve the prior operation.')
        if existing is not None and existing['status'] == 'complete':
            return existing['result']
        observed, result = reconcile() if reconcile is not None else (False, None)
        if existing is not None:
            if not observed:
                raise MaintenanceBlocked('An external action is uncertain and was not replayed: ' + name)
            self.state.finish_effect(key, name, result)
            return result
        self.state.begin_effect(key, name, descriptor)
        if observed:
            self.state.finish_effect(key, name, result)
            return result
        result = action()
        self.state.finish_effect(key, name, result)
        return result

    def _issue(self, key: str, candidate: Candidate, reason: str):
        marker = '<!-- aic-maintainer:source:' + hashlib.sha256(candidate.key.encode()).hexdigest() + ' -->'
        body = ('## Manual adoption task\n\n' + policy._markdown(reason) + '\n\n'
                '- [ ] Check applicability against the actual task and original acceptance.\n'
                '- [ ] Any workflow, code, CI or permission change needs a separate owner-approved PR.\n'
                '- [ ] Verify outcomes before adopting a research recommendation.\n\n'
                f'Primary source: {candidate.url}\n\nPublished: {candidate.published}; revision: {candidate.updated}; evidence tier: {candidate.tier}.\n\n'
                'Research citations are reference-only. Source availability, source-declared results and independent reproduction are distinct. No adoption or execution is approved by this issue.\n\n' + marker)
        def reconcile():
            found = self.github.find_issue(marker)
            if found is None:
                return False, None
            if (found.get('user') or {}).get('login') != policy.ACTOR or policy.ACTOR not in {item.get('login') for item in found.get('assignees', [])}:
                raise MaintenanceBlocked('An issue marker has unexpected ownership or assignment.')
            return True, dict(number=found['number'], url=found.get('html_url', found.get('url')))
        return self._effect(key, 'issue:' + hashlib.sha256(candidate.key.encode()).hexdigest(), dict(marker=marker),
            lambda: self.github.create_issue(('Assess research: ' + candidate.title)[:120], body, marker, adoption=True), reconcile)

    def _job_directory(self, key: str) -> Path:
        if not isinstance(key, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9a-f]{16}', key):
            raise MaintenanceBlocked('Invalid owned job directory identity.')
        directory = self.private / 'jobs' / key
        for ancestor in (directory, *directory.parents):
            if ancestor.is_symlink():
                raise MaintenanceBlocked('Linked job directories are preserved.')
            if ancestor == self.project:
                break
        return directory

    def _prepare(self, key: str, data: dict, text: str):
        directory = self._job_directory(key)
        checkout = directory / 'checkout'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if checkout.is_symlink():
            raise MaintenanceBlocked('Linked checkout is refused.')
        owner_path = directory / 'checkout-owner.json'
        owner = dict(owner='aic-maintainer-checkout-v1', job=key, repository=policy.REPO)
        if checkout.exists() and not owner_path.is_file():
            raise MaintenanceBlocked('An unmanaged checkout is preserved.')
        _private_json(owner_path, owner)
        if not checkout.exists():
            self._git(directory, 'clone', '--quiet', '--no-hardlinks', '--single-branch', '--no-tags', '--branch', 'main', 'https://github.com/' + policy.REPO + '.git', str(checkout))
        if self._git(checkout, 'config', '--get', 'remote.origin.url') != 'https://github.com/' + policy.REPO + '.git':
            raise MaintenanceBlocked('Checkout origin is not the approved repository.')
        if 'base_sha' not in data:
            data['base_sha'] = self._git(checkout, 'rev-parse', 'HEAD')
            data['initial_base_sha'] = data['base_sha']
            self._save(key, data, 'researched')
        branch = data['branch']
        current = self._git(checkout, 'branch', '--show-current')
        if current != branch:
            if current != 'main' or self._git(checkout, 'rev-parse', 'HEAD') != data['base_sha']:
                raise MaintenanceBlocked('Unexpected checkout branch/state is preserved.')
            self._git(checkout, 'switch', '--quiet', '-c', branch)
        target = checkout / policy.record_path(data['day'])
        for ancestor in target.parents:
            if ancestor == checkout:
                break
            if ancestor.is_symlink():
                raise MaintenanceBlocked('Research record parent is linked.')
        target.parent.mkdir(parents=True, exist_ok=True)
        expected = text.encode('utf-8')
        if target.is_symlink():
            raise MaintenanceBlocked('Linked research record is refused.')
        if target.exists():
            if target.read_bytes() != expected:
                raise MaintenanceBlocked('An existing research record is preserved; automatic replacements are forbidden.')
        else:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(expected)
        current_head = self._git(checkout, 'rev-parse', 'HEAD')
        if 'head_sha' in data and current_head != data['head_sha']:
            raise MaintenanceBlocked('Unexpected prepared head is preserved; it cannot be adopted.')
        if current_head == data['base_sha']:
            changed = self._git(checkout, 'status', '--porcelain', '--untracked-files=all')
            if changed not in ('?? ' + policy.record_path(data['day']), 'A  ' + policy.record_path(data['day'])):
                raise MaintenanceBlocked('Unexpected checkout changes are preserved.')
            self._git(checkout, 'add', '--', policy.record_path(data['day']))
            self._git(checkout, '-c', 'user.name=' + policy.ACTOR, '-c', 'user.email=' + policy.ACTOR + '@users.noreply.github.com', 'commit', '--quiet', '-m', 'research: add reference-only evidence for ' + data['day'])
        data['head_sha'] = self._git(checkout, 'rev-parse', 'HEAD')
        self._artifact(checkout, data, text)
        self._save(key, data, 'prepared')
        return checkout

    def _artifact(self, checkout: Path, data: dict, text: str):
        path = policy.record_path(data['day'])
        if self._git(checkout, 'rev-parse', 'HEAD') != data['head_sha']:
            raise MaintenanceBlocked('Local artifact head changed.')
        raw = self._git(checkout, 'diff', '--raw', '--no-abbrev', data['base_sha'], data['head_sha'], '--')
        rows = raw.splitlines()
        if len(rows) != 1:
            raise MaintenanceBlocked('Automatic publication cannot include extra files.')
        metadata, separator, filename = rows[0].partition('\t')
        parts = metadata.split()
        if not separator or filename != path or len(parts) != 5 or parts[0] != ':000000' or parts[1] != '100644' or parts[4] != 'A':
            raise MaintenanceBlocked('Only one new regular non-executable dated record may publish.')
        actual = self._git(checkout, 'show', data['head_sha'] + ':' + path, binary=True)
        if actual != text.encode('utf-8') or (checkout / path).read_bytes() != text.encode('utf-8'):
            raise MaintenanceBlocked('PR bytes differ from the validated original record.')
        if self._git(checkout, 'status', '--porcelain', '--untracked-files=all'):
            raise MaintenanceBlocked('Tracked or untracked changes appeared after artifact preparation.')

    def _verify(self, key: str, data: dict, checkout: Path, text: str):
        self._artifact(checkout, data, text)
        if data.get('verified_head') == data['head_sha']:
            return
        if data.get('failed_verification_head') == data['head_sha']:
            raise MaintenanceBlocked('This exact head already failed verification; owner repair is required, not a repeated check.')
        environment = {name: value for name, value in os.environ.items() if name in ('HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL')}
        environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', AIC_PYTHON=sys.executable)
        result = subprocess.run([sys.executable, '-B', str(checkout / 'scripts' / 'verify.py')], cwd=checkout, env=environment, text=True, capture_output=True, timeout=300, shell=False)
        log = result.stdout + result.stderr
        log_path = self.private / 'jobs' / key / ('verify-' + data['head_sha'] + '-' + str(time.time_ns()) + '.log')
        if log_path.is_symlink():
            raise MaintenanceBlocked('Linked verification evidence is refused.')
        with log_path.open('x', encoding='utf-8') as stream:
            stream.write(log)
        if result.returncode:
            data['failed_verification_head'] = data['head_sha']
            self._save(key, data, 'blocked')
            raise MaintenanceBlocked('Mac mini offline verification failed; no record branch was published.')
        self._artifact(checkout, data, text)
        data['verified_head'] = data['head_sha']
        data['local_check'] = dict(exit=0, python=platform.python_version(), machine=platform.machine(), system=platform.system(), log_sha256=hashlib.sha256(log.encode()).hexdigest())
        self._save(key, data, 'prepared')

    def _push(self, key: str, data: dict, checkout: Path):
        head = data['head_sha']
        def reconcile():
            remote = self.github.branch_sha(data['branch'])
            if remote is None:
                return False, None
            if remote == head:
                return True, dict(head_sha=head)
            if remote == data.get('pushed_head'):
                return False, None
            raise MaintenanceBlocked('The remote owned branch changed; no force push was attempted.')
        self._effect(key, 'push:' + head, dict(branch=data['branch'], head_sha=head), lambda: self._git(checkout, 'push', '--quiet', 'origin', 'HEAD:refs/heads/' + data['branch']), reconcile)
        data['pushed_head'] = head
        self._save(key, data, 'published')

    def _recover_integration(self, key: str, data: dict, checkout: Path, text: str):
        intent = data.get('integration')
        if intent is None:
            return
        if (data['head_sha'], data['base_sha']) != (intent['old_head'], intent['old_base']):
            raise MaintenanceBlocked('Integration intent no longer matches its saved artifact.')
        if self._git(checkout, 'branch', '--show-current') != data['branch']:
            raise MaintenanceBlocked('Unexpected integration branch is preserved.')
        head = self._git(checkout, 'rev-parse', 'HEAD')
        if self._git(checkout, 'status', '--porcelain', '--untracked-files=all'):
            raise MaintenanceBlocked('Conflicted or owner-modified integration is preserved; no reset was attempted.')
        merge_state = self._git(checkout, 'rev-parse', '--git-path', 'MERGE_HEAD')
        if (checkout / merge_state).exists():
            raise MaintenanceBlocked('An unfinished integration is held for owner inspection.')
        if self._git(checkout, 'rev-parse', 'origin/main') != intent['target_main']:
            raise MaintenanceBlocked('Integration target ref changed; preserve the checkout.')
        if head == intent['old_head']:
            self._artifact(checkout, data, text)
            self._git(checkout, '-c', 'user.name=' + policy.ACTOR, '-c', 'user.email=' + policy.ACTOR + '@users.noreply.github.com',
                      '-c', 'commit.gpgsign=false', 'merge', '--no-edit', '--no-ff', '--no-gpg-sign', '--no-log', '-m', intent['message'],
                      intent['target_main'], commit_time=intent['commit_time'])
            head = self._git(checkout, 'rev-parse', 'HEAD')
        if head != intent['expected_head'] or self._git(checkout, 'rev-parse', 'HEAD^{tree}') != intent['expected_tree']:
            raise MaintenanceBlocked('Unexpected integration head is preserved; only the exact intended commit can resume.')
        parents = self._git(checkout, 'show', '-s', '--format=%P', 'HEAD').split()
        if parents != [intent['old_head'], intent['target_main']]:
            raise MaintenanceBlocked('Integration parents differ from the saved intent.')
        updated = dict(data, base_sha=intent['target_main'], head_sha=head)
        self._artifact(checkout, updated, text)
        updated.pop('review', None)
        updated.pop('integration')
        self._save(key, updated, 'prepared')
        data.clear()
        data.update(updated)

    def _refresh(self, key: str, data: dict, checkout: Path, text: str):
        if 'integration' not in data:
            current_main = self.github.main_sha()
            if current_main == data['base_sha']:
                return
            self._artifact(checkout, data, text)
            if self.github.branch_sha(data['branch']) != data['head_sha']:
                raise MaintenanceBlocked('Owned remote head changed before integration.')
            self._git(checkout, 'fetch', '--quiet', 'origin', 'main')
            if self._git(checkout, 'rev-parse', 'origin/main') != current_main:
                raise MaintenanceBlocked('Main changed during integration; no stale merge is allowed.')
            tree = self._git(checkout, 'merge-tree', '--write-tree', data['head_sha'], current_main)
            commit_time = self.clock().astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S +0000')
            message = 'Merge approved main ' + current_main + ' into research record'
            expected = self._git(checkout, '-c', 'user.name=' + policy.ACTOR, '-c', 'user.email=' + policy.ACTOR + '@users.noreply.github.com',
                                 '-c', 'commit.gpgsign=false', 'commit-tree', tree, '-p', data['head_sha'], '-p', current_main, '-m', message, commit_time=commit_time)
            data['integration'] = dict(old_head=data['head_sha'], old_base=data['base_sha'], target_main=current_main,
                                       expected_tree=tree, expected_head=expected, commit_time=commit_time, message=message)
            self._save(key, data, 'integrating')
        self._recover_integration(key, data, checkout, text)
        self._verify(key, data, checkout, text)
        self._push(key, data, checkout)

    def _primary_evidence_tasks(self, key: str, data: dict, candidates: list[Candidate]):
        tasks = data.setdefault('primary_evidence_tasks', {})
        for candidate in candidates:
            tasks[candidate.key] = self._issue(key, candidate, 'Obtain complete primary-method and rights evidence before assessing this source. Abstract-only or partial evidence is not enough for automatic publication.')
            self.state.mark_seen(candidate.key, 'manual-primary-evidence')
            self._save(key, data, 'researched')

    def _reject(self, key: str, data: dict):
        snapshot = self.github.pr(data['pr']['number'])
        if (snapshot['merged'] is not False or snapshot['head_sha'] != data['head_sha']
                or snapshot['head_ref'] != data['branch'] or snapshot['state'] not in ('open', 'closed')):
            raise MaintenanceBlocked('Rejected PR identity changed; cleanup cannot proceed.')
        data['rejection_cleanup'] = True
        self._save(key, data, 'rejection-cleanup')
        def closed():
            snapshot = self.github.pr(data['pr']['number'])
            if snapshot['merged'] is not False or snapshot['head_sha'] != data['head_sha'] or snapshot['head_ref'] != data['branch']:
                raise MaintenanceBlocked('Rejected PR identity changed during close reconciliation.')
            return snapshot['state'] == 'closed', dict(closed=True)
        self._effect(key, 'close-rejected', dict(head_sha=data['head_sha']),
                     lambda: self.github.close_pr(data['pr']['number'], data['head_sha'], 'Independent review did not approve'), closed)
        self._delete(key, data)
        self._cleanup(key, data)
        self._save(key, data, 'rejected')
        return dict(status='review-rejected', pr=data['pr']['url'], findings=data['review']['findings'])

    def _resume(self, key: str, data: dict, agents):
        all_candidates = candidates_from_json(data['candidates'])
        candidates = [candidate for candidate in all_candidates if candidate.documents and all(doc.complete for doc in candidate.documents)]
        supplied = {candidate.key: candidate for candidate in all_candidates}
        incomplete = [candidate for candidate in all_candidates if candidate not in candidates]
        if not candidates:
            self._primary_evidence_tasks(key, data, incomplete)
            self._save(key, data, 'complete')
            return dict(status='manual-primary-evidence', candidates=len(all_candidates))
        templates = {item['id'] for item in json.loads((policy.ROOT / 'skills/aic/assets/workflows.json').read_text())['templates']}
        packet = research_packet(candidates, templates)
        research_directory = self.private / 'jobs' / key / 'agents' / 'research'
        if 'review' in data and 'research' not in data:
            raise MaintenanceBlocked('Persisted review is missing its research evidence.')
        if 'research' not in data and self.state.run_result(key, 'research') is None:
            self._primary_evidence_tasks(key, data, incomplete)
        if 'research' not in data:
            role_now = self.clock()
            output = agents.run('research', packet, directory=research_directory, now=role_now, job_key=key)
            result = policy.validate_research(output, candidates, templates)
            agents.accept('research', packet, output, now=role_now, job_key=key)
            data['research'] = result
            for disposition in ('records', 'manual_tasks', 'rejected'):
                for item in result[disposition]:
                    self.state.mark_seen(item['candidate_key'], disposition)
            self._save(key, data, 'researched')
        else:
            output = agents.accepted('research', packet, directory=research_directory, now=self.clock(), job_key=key)
            if policy.validate_research(output, candidates, templates) != data['research']:
                raise MaintenanceBlocked('Persisted research differs from its exact accepted evidence.')
        research = data['research']
        records = research['records']
        text = policy.render_records(data['day'], records, candidates) if records else ''
        if 'review' in data:
            if not records:
                raise MaintenanceBlocked('Persisted review has no research artifact.')
            packet = review_packet(candidates, records, text, data['head_sha'], policy.record_path(data['day']))
            review_key = key + '-review-' + data['head_sha'][:12]
            review_directory = self.private / 'jobs' / key / 'agents' / ('review-' + data['head_sha'][:12])
            output = agents.accepted('review', packet, directory=review_directory, now=self.clock(), job_key=review_key)
            if policy.validate_review(output, head_sha=data['head_sha'], bundle_digest=policy.source_digest(candidates), records=records, candidates=candidates) != data['review']:
                raise MaintenanceBlocked('Persisted review differs from its exact accepted evidence.')
        if data.get('rejection_cleanup'):
            if not data.get('review') or data['review']['verdict'] == 'approve':
                raise MaintenanceBlocked('Rejected cleanup requires its exact non-approval evidence.')
            return self._reject(key, data)
        if data.get('pr'):
            snapshot = self.github.pr(data['pr']['number'])
            if snapshot['merged'] is True:
                if snapshot['head_sha'] != data.get('head_sha') or snapshot['head_ref'] != data['branch']:
                    raise MaintenanceBlocked('Merged PR identity differs from the tracked artifact.')
                self._delete(key, data)
                self._cleanup(key, data)
                self._save(key, data, 'complete')
                return dict(status='merged-confirmed', pr=data['pr']['url'], daily_runs=self.state.runs(self.day))
        if 'integration' in data:
            self._recover_integration(key, data, self._job_directory(key) / 'checkout', text)
        self._primary_evidence_tasks(key, data, incomplete)
        for item in research['manual_tasks']:
            self._issue(key, supplied[item['candidate_key']], item['reason'])
        if not research['records']:
            self._save(key, data, 'complete')
            return dict(status='no-eligible-records', manual_tasks=len(research['manual_tasks']), rejected=len(research['rejected']))
        _private_json(self.private / 'jobs' / key / 'validated-research.json', research)
        checkout = self._prepare(key, data, text)
        self._verify(key, data, checkout, text)
        self._push(key, data, checkout)
        issues = [self._issue(key, supplied[item['candidate_key']], item['adoption_task']) for item in records]
        def reconcile_pr():
            value = self.github.find_pr(data['branch'])
            if value is None:
                return False, None
            if value['head_sha'] != data['head_sha']:
                raise MaintenanceBlocked('Existing research PR has an unexpected head.')
            return True, {field: value[field] for field in ('number', 'url', 'head_sha')}
        body = ('## Research-only proposal\n\nOne new original factual evidence record; no workflow instructions, code, CI or permission changes. '
                'Upstream publications remain reference-only.\n\n' + ('This is an explicit historical backfill smoke, not a newly published paper.\n\n' if data.get('bootstrap') else '')
                + 'Manual adoption tasks: ' + ', '.join('#' + str(item['number']) for item in issues) + '.\n\n'
                'Mac mini offline checks passed on the proposed head before pushing. A fresh no-tool review, exact source/head binding and required repository checks must pass before merge.\n\n'
                '<!-- aic-maintainer:batch:' + key + ' -->')
        data['pr'] = self._effect(key, 'create-pr', dict(branch=data['branch']), lambda: self.github.create_pr(data['branch'], 'research: evidence record ' + data['day'], body), reconcile_pr)
        self._save(key, data, 'published')
        self._refresh(key, data, checkout, text)
        snapshot = self.github.pr(data['pr']['number'])
        if snapshot['merged'] is True:
            data['merged'] = True
        elif snapshot['head_sha'] != data['head_sha'] or snapshot['head_ref'] != data['branch'] or not policy.record_only_files(snapshot['files'], data['day']):
            raise MaintenanceBlocked('Actual PR no longer matches the one permitted research artifact.')
        if not data.get('merged'):
            packet = review_packet(candidates, records, text, data['head_sha'], policy.record_path(data['day']))
            review_key = key + '-review-' + data['head_sha'][:12]
            if 'review' not in data:
                role_now = self.clock()
                output = agents.run('review', packet, directory=self.private / 'jobs' / key / 'agents' / ('review-' + data['head_sha'][:12]), now=role_now, job_key=review_key)
                result = policy.validate_review(output, head_sha=data['head_sha'], bundle_digest=policy.source_digest(candidates), records=records, candidates=candidates)
                agents.accept('review', packet, output, now=role_now, job_key=review_key)
                data['review'] = result
                self._save(key, data, 'reviewed')
            review = policy.validate_review(data['review'], head_sha=data['head_sha'], bundle_digest=policy.source_digest(candidates), records=records, candidates=candidates)
            marker = '<!-- aic-maintainer:review:' + data['head_sha'] + ' -->'
            comment = ('## Independent no-tool evidence review\n\n' + 'Head: `' + data['head_sha'] + '`; source packet: `' + policy.source_digest(candidates) + '`.\n\n'
                       + 'Verdict: **' + review['verdict'] + '**. This is an AI evidence assessment, not approval by a different GitHub identity or experimental reproduction.\n\n'
                       + '```json\n' + json.dumps(review, indent=2, ensure_ascii=False) + '\n```\n\n'
                       + 'Mac mini check: `' + json.dumps(data['local_check'], sort_keys=True) + '`.\n\n' + marker)
            self._effect(key, 'comment:' + data['head_sha'], dict(marker=marker), lambda: self.github.comment(data['pr']['number'], comment),
                lambda: (self.github.find_comment(data['pr']['number'], marker), dict(confirmed=True)))
            for context, state in (('aic/macmini', 'success'), ('aic/independent-review', 'success' if review['verdict'] == 'approve' else 'failure')):
                self._effect(key, 'status:' + data['head_sha'] + ':' + context, dict(head_sha=data['head_sha'], context=context, state=state),
                    lambda context=context, state=state: self.github.status(data['head_sha'], context, state, 'Source/head-bound research-only gate'),
                    lambda context=context, state=state: (self.github.checks(data['head_sha'])[context] == state, dict(confirmed=True)))
            if review['verdict'] != 'approve':
                return self._reject(key, data)
            checks = self.github.checks(data['head_sha'])
            if any(value != 'success' for value in checks.values()):
                self._save(key, data, 'awaiting-ci')
                return dict(status='awaiting-required-checks', pr=data['pr']['url'], checks=checks)
            self._artifact(checkout, data, text)
            if self.github.main_sha() != data['base_sha']:
                return dict(status='main-advanced', pr=data['pr']['url'], next_action='Reintegrate and independently review the new head on a subsequent cycle.')
            result = self._effect(key, 'merge:' + data['head_sha'], dict(head_sha=data['head_sha']), lambda: self.github.merge(data['pr']['number'], data['head_sha']),
                lambda: (self.github.pr(data['pr']['number'])['merged'] is True, dict(merged=True, confirmed_by_pr=data['pr']['number'])))
            if not result.get('merged'):
                raise MaintenanceBlocked('GitHub did not confirm the merge; no success was recorded.')
            data['merged'] = True
            self._save(key, data, 'reviewed')
        self._delete(key, data)
        self._cleanup(key, data)
        self._save(key, data, 'complete')
        return dict(status='merged', pr=data['pr']['url'], records=len(records), issues=issues, daily_runs=self.state.runs(self.day))

    def _delete(self, key: str, data: dict):
        remote = self.github.branch_sha(data['branch'])
        if remote is not None and remote != data['head_sha']:
            raise MaintenanceBlocked('The remote branch changed before deletion reconciliation.')
        self._effect(key, 'delete-branch', dict(branch=data['branch'], head_sha=data['head_sha']), lambda: self.github.delete_branch(data['branch'], data['head_sha']),
            lambda: (self.github.branch_sha(data['branch']) is None, dict(deleted=True)))

    def _cleanup(self, key: str, data: dict):
        directory = self._job_directory(key)
        checkout = directory / 'checkout'
        if not checkout.exists() and not checkout.is_symlink():
            return
        owner_path = directory / 'checkout-owner.json'
        if checkout.is_symlink() or not checkout.is_dir() or owner_path.is_symlink() or not owner_path.is_file():
            raise MaintenanceBlocked('Unmanaged or linked checkout is preserved during cleanup.')
        _private_json(owner_path, dict(owner='aic-maintainer-checkout-v1', job=key, repository=policy.REPO))
        if not shutil.rmtree.avoids_symlink_attacks:
            raise MaintenanceBlocked('Safe checkout cleanup is unavailable on this platform.')
        if self._git(checkout, 'config', '--get', 'remote.origin.url') != 'https://github.com/' + policy.REPO + '.git':
            raise MaintenanceBlocked('Unexpected checkout origin is preserved.')
        if self._git(checkout, 'rev-parse', 'HEAD') != data['head_sha']:
            raise MaintenanceBlocked('An owner-changed checkout head is preserved.')
        if self._git(checkout, 'status', '--porcelain', '--untracked-files=all') or self._git(checkout, 'ls-files', '--others', '--ignored', '--exclude-standard'):
            raise MaintenanceBlocked('Unexpected checkout files are preserved, including ignored files.')
        expected = {
            'refs/heads/main': data.get('initial_base_sha', data['base_sha']),
            'refs/heads/' + data['branch']: data['head_sha'],
            'refs/remotes/origin/main': data['base_sha'],
            'refs/remotes/origin/HEAD': data['base_sha'],
        }
        if data.get('pushed_head'):
            expected['refs/remotes/origin/' + data['branch']] = data['pushed_head']
        git_directory = checkout / '.git'
        if git_directory.is_symlink() or not git_directory.is_dir() or (git_directory / 'refs').is_symlink():
            raise MaintenanceBlocked('Linked or nonlocal Git storage is preserved.')
        # for-each-ref omits dangling symbolic refs; inspect loose refs as well.
        for path in (git_directory / 'refs').rglob('*'):
            if path.is_symlink():
                raise MaintenanceBlocked('Linked Git refs are preserved.')
            if path.is_dir():
                continue
            ref = path.relative_to(git_directory).as_posix()
            target = ('ref: refs/remotes/origin/main' if ref == 'refs/remotes/origin/HEAD' else expected.get(ref, ''))
            if ref not in expected or path.read_bytes() != (target + '\n').encode('ascii'):
                raise MaintenanceBlocked('Unexpected loose Git ref is preserved.')
        refs = self._git(checkout, 'for-each-ref', '--format=%(refname)%09%(objectname)%09%(symref)%09END')
        for row in refs.splitlines():
            ref, sha, symbolic, _ = row.split('\t')
            if ref not in expected or sha != expected[ref] or symbolic != ('refs/remotes/origin/main' if ref == 'refs/remotes/origin/HEAD' else ''):
                raise MaintenanceBlocked('Unexpected checkout ref or target is preserved, including stashes and tags.')
        worktrees = [line[9:] for line in self._git(checkout, 'worktree', 'list', '--porcelain').splitlines() if line.startswith('worktree ')]
        if worktrees != [str(checkout)]:
            raise MaintenanceBlocked('Additional linked worktrees are preserved.')
        shutil.rmtree(checkout)

    def run(self, *, bootstrap=None) -> dict:
        if not self.publish:
            return dict(status='preview', policy=policy.policy_document(), side_effects=False, next_action='Run with --publish only inside the owner-approved research-maintenance scope.')
        origin = self._git(self.project, 'config', '--get', 'remote.origin.url')
        if origin not in ('https://github.com/' + policy.REPO + '.git', 'git@github.com:' + policy.REPO + '.git'):
            raise MaintenanceBlocked('The requested maintenance project is not the approved repository.')
        self.state = State(self.private / 'state.sqlite3')
        try:
            with self.state.exclusive():
                self._ready()
                active = self.state.active_job()
                if active is None:
                    if self.state.runs(self.day) >= policy.MAX_RUNS_PER_DAY:
                        return dict(status='daily-budget-exhausted', runs=self.state.runs(self.day), next_action='Wait for the next UTC day; no new agent was started.')
                    if not bootstrap and self.state.meta('last_discovery_attempt') == self.day:
                        return dict(status='daily-discovery-already-attempted', errors=json.loads(self.state.meta('source_errors', '[]')))
                    if bootstrap:
                        batch = CollectionBatch((self.bootstrap_fetch(bootstrap, now=self.now),), (), self.now.isoformat())
                    else:
                        self.state.set_meta('last_discovery_attempt', self.day)
                        batch = self.collect(self.now, seen=self.state.seen(), limit=policy.MAX_CANDIDATES)
                        self.state.set_meta('source_errors', json.dumps(batch.errors))
                        if not batch.errors:
                            self.state.set_meta('last_discovery', self.day)
                    candidates = [candidate for candidate in batch.candidates if candidate.key not in self.state.seen()]
                    if not candidates:
                        return dict(status='source-check-partial' if batch.errors else 'no-new-candidates', errors=list(batch.errors))
                    key = self.day + '-' + policy.digest([asdict(candidate) for candidate in candidates])[:16]
                    data = dict(day=self.day, bootstrap=bootstrap, candidates=[asdict(candidate) for candidate in candidates], source_errors=list(batch.errors), branch='aic/research-' + key)
                    self._save(key, data, 'collecting')
                    active = dict(key=key, data=data)
                key, data = active['key'], active['data']
                agents = self.agents_factory(self.state, enabled=True, artifact_root=self.private, clock=self.clock)
                try:
                    result = self._resume(key, data, agents)
                except (MaintenanceBlocked, PolicyError, AgentError, GitHubError, StateError, OSError, subprocess.SubprocessError) as exc:
                    data['error'] = str(exc)
                    self._save(key, data, 'blocked')
                    result = dict(status='blocked', job=key, reason=str(exc), next_action='Inspect exact evidence/state. Uncertain writes are reconciled read-only, never blindly replayed.')
                result['source_errors'] = data.get('source_errors', [])
                self.state.set_meta('last_outcome', json.dumps(result, ensure_ascii=False))
                return result
        finally:
            self.state.close()


PolicyError = policy.PolicyError
