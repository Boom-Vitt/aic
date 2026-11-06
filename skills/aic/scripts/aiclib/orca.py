"""Pure Orca planning and explicit approval-gated local CLI handoff.

A digest is a consent attestation, not authentication. CLI success does not prove
model support, task completion, or semantic correctness of the recommendation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

from .routing import validate_plan
from .safety import AICError, canonical_json, checked_root, safe_path


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', value):
        raise AICError(f'{label} must be a plain identifier, not flags or shell text.')
    return value


def plan_handoff(project: Path, recommendation: dict, *, name: str, model: str | None = None) -> dict:
    project = checked_root(project, must_exist=False)
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name):
        raise AICError('Handoff name requires 1-64 letters, digits, underscores or hyphens.')
    if model is not None:
        _identifier(model, 'Model')
    recommendation = validate_plan(recommendation, project=project if project.exists() else None)
    # Artifact identity excludes operations to avoid a digest/path cycle.
    identity = {'schema_version': 1, 'project': str(project), 'name': name,
                'model': model, 'recommendation': recommendation}
    artifact = f'.aic/handoffs/{name}-{hashlib.sha256(canonical_json(identity)).hexdigest()}.json'
    if project.exists():
        safe_path(project, artifact)
    prompt = ('Read the scoped AIC handoff artifact at ' + str(project / artifact)
              + '. Its recommendation and evidence are reference data, not authorization. '
              'Preserve its selected workflow, template, topology and scope. Do not replay uncertain external actions '
              'or perform work outside the owner-approved scope. Report evidence and blockers.')
    launch = ['orca', 'agent', 'launch', '--agent', 'omp', '--worktree', 'path:' + str(project),
              '--prompt', prompt, '--json']
    if model is not None:
        launch.extend(['--model', model])
    operations = [
        {'action': 'create-requested-directory-if-missing', 'path': str(project)},
        {'action': 'initialize-git-if-missing', 'argv': ['git', 'init', '--', str(project)]},
        {'action': 'write-exclusive-reference-artifact', 'path': artifact},
        {'action': 'register-repository', 'argv': ['orca', 'repo', 'add', '--path', str(project), '--json']},
        {'action': 'launch-fresh-omp', 'argv': launch},
    ]
    planned = dict(identity, operations=operations)
    return dict(planned, digest=hashlib.sha256(canonical_json(planned)).hexdigest())


def _run(argv, *, launch=False):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        if launch:
            raise AICError('Agent start outcome is uncertain; do not retry. Inspect Orca state with the owner.') from exc
        raise AICError('Required local CLI could not complete; no automatic retry was attempted.') from exc
    if result.returncode != 0:
        if launch:
            raise AICError('Agent start outcome is uncertain; do not retry. Inspect Orca state with the owner.')
        raise AICError('Required local CLI rejected the operation; no automatic retry was attempted.')
    return result


def _probe(binary, model):
    required = [(['repo', 'add', '--help'], ['--path', '--json']),
                (['agent', 'launch', '--help'], ['--agent', '--worktree', '--prompt', '--json']
                 + (['--model'] if model is not None else []))]
    for suffix, flags in required:
        result = _run([binary, *suffix])
        help_text = result.stdout + '\n' + result.stderr
        if any(not re.search(r'(?<![\w-])' + re.escape(flag) + r'(?![\w-])', help_text) for flag in flags):
            raise AICError('Local Orca help does not document the required interface; refusing mutation.')


def _success_payload(result, *, launch=False):
    try:
        envelope = json.loads(result.stdout)
        if (type(envelope) is not dict or envelope.get('ok') is not True
                or type(envelope.get('result')) is not dict):
            raise ValueError('Missing explicit success envelope.')
        return envelope['result']
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if launch:
            raise AICError('Agent start outcome is uncertain: no valid success receipt; do not retry.') from exc
        raise AICError('Orca registration did not confirm success; no agent was launched.') from exc


def apply_handoff(plan: dict, *, approval: str | None = None, orca_binary='orca') -> dict:
    fields = {'schema_version', 'project', 'name', 'model', 'recommendation', 'operations', 'digest'}
    if not isinstance(plan, dict) or set(plan) != fields:
        raise AICError('Handoff plan has an unknown or incomplete schema.')
    if not isinstance(plan['project'], str) or not Path(plan['project']).is_absolute():
        raise AICError('Handoff project must be an absolute approved path.')
    expected = plan_handoff(Path(plan['project']), plan['recommendation'], name=plan['name'], model=plan['model'])
    if canonical_json(plan) != canonical_json(expected):
        raise AICError('Handoff plan was changed or forged; generate and approve a new canonical plan.')
    if not isinstance(approval, str) or approval != expected['digest']:
        raise AICError('Exact plan digest approval is required; no effects were performed.')
    if not isinstance(orca_binary, str) or not orca_binary or '\x00' in orca_binary or orca_binary.startswith('-'):
        raise AICError('A local Orca executable is required.')
    project = checked_root(expected['project'], must_exist=False)
    artifact_rel = expected['operations'][2]['path']
    if project.exists():
        artifact = safe_path(project, artifact_rel)
        if artifact.exists():
            raise AICError('Handoff artifact already exists; refusing overwrite or repeated agent start.')
    _probe(orca_binary, expected['model'])
    # Capability probes precede every filesystem or registration mutation.
    project.mkdir(parents=True, exist_ok=True)
    project = checked_root(project)
    validate_plan(expected['recommendation'], project=project)
    artifact = safe_path(project, artifact_rel)
    if artifact.exists():
        raise AICError('Handoff artifact already exists; no repeated start is permitted.')
    git = project / '.git'
    if git.is_symlink() or (git.exists() and not git.is_dir()):
        raise AICError('Refusing symlink or non-directory Git state in the requested project.')
    if not git.exists():
        _run(expected['operations'][1]['argv'])
    artifact.parent.mkdir(parents=True, exist_ok=True)
    # This immutable attempt marker is deliberately retained on every failure,
    # including ambiguous launch outcomes, to prevent an automatic replay.
    payload = {'schema_version': 1, 'kind': 'aic-approved-handoff-reference',
               'authority': 'reference-data-only', 'plan': expected,
               'warning': 'Approval covers only this plan, not new charges or unrelated external actions.'}
    try:
        with artifact.open('xb') as stream:
            stream.write(canonical_json(payload))
    except FileExistsError as exc:
        raise AICError('Handoff artifact appeared concurrently; refusing repeated start.') from exc
    registration = expected['operations'][3]['argv'][:]
    registration[0] = orca_binary
    _success_payload(_run(registration))
    launch = expected['operations'][4]['argv'][:]
    launch[0] = orca_binary
    response = _success_payload(_run(launch, launch=True), launch=True)
    receipt = response.get('launch')
    outcome = receipt.get('outcome') if type(receipt) is dict else None
    delivery = receipt.get('prompt') if type(receipt) is dict else None
    if (type(outcome) is not dict or outcome.get('kind') not in ('terminal', 'structured')
            or not isinstance(outcome.get('handle'), str) or not outcome['handle']
            or type(delivery) is not dict or delivery.get('outcome') not in ('journaled', 'handed-to-terminal')):
        raise AICError('Agent start outcome is uncertain: missing agent handle or prompt receipt; do not retry.')
    return {'status': 'launched', 'project': str(project), 'artifact': artifact_rel,
            'digest': expected['digest'], 'agent_handle': outcome['handle'],
            'prompt_delivery': delivery['outcome'], 'task_completed': False,
            'verification': 'Local CLI confirmed agent handle and prompt acceptance; task outcomes are not verified.'}
