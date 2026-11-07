"""Orca v0.4 plan checks compatible with boom-big-nose-workflow.

The plugin schema is the contract. This module does not copy that schema file.
``plan_hash`` matches ``orca-plan.mjs``: SHA-256 of the compact JSON object
``{goal, base, streams}``, first 16 hex characters. ``base`` uses an empty
string when omitted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


SLUG = re.compile(r'^[a-z0-9][a-z0-9._-]{0,59}$')
ROLES = {'claude-code', 'codex'}
TOP_KEYS = {
    '$schema', 'version', 'title', 'status', 'acceptedAt', 'planHash', 'goal',
    'nonGoals', 'base', 'risks', 'replanTriggers', 'streams',
}
STREAM_KEYS = {'slug', 'role', 'summary', 'paths', 'dependsOn', 'acceptance'}
REQUIRED = ('version', 'title', 'status', 'goal', 'streams')


class PlanError(ValueError):
    """A plan file cannot be accepted or read safely."""


class PlanReport:
    def __init__(self, errors: list[str], warnings: list[str], order: list[str]):
        self.errors = errors
        self.warnings = warnings
        self.order = order

    @property
    def ok(self) -> bool:
        return not self.errors


def plan_hash(plan: dict) -> str:
    payload = {'goal': plan.get('goal'), 'base': plan.get('base') or '', 'streams': plan.get('streams')}
    encoded = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()[:16]


def _norm(path: str) -> str:
    return path[2:] if path.startswith('./') else path.rstrip('/')


def _overlaps(left: str, right: str) -> bool:
    one, two = _norm(left), _norm(right)
    return one == two or one.startswith(two + '/') or two.startswith(one + '/') or one == '' or two == ''


def _strings(value, label: str, errors: list[str], *, minimum: int) -> bool:
    if not isinstance(value, list) or len(value) < minimum or any(not isinstance(item, str) or not item for item in value):
        errors.append(f'{label} must list at least {minimum} nonempty string(s).')
        return False
    return True


def validate_plan(plan: object, *, max_worktrees: int = 6, min_acceptance: int = 1) -> PlanReport:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(plan, dict):
        return PlanReport(['plan must be a JSON object.'], warnings, [])
    unknown = sorted(set(plan) - TOP_KEYS)
    if unknown:
        errors.append('unknown plan fields: ' + ', '.join(unknown))
    for key in REQUIRED:
        if key not in plan:
            errors.append(f'missing {key}.')
    if plan.get('version') != 1:
        errors.append('version must be 1.')
    if not isinstance(plan.get('title'), str) or not plan.get('title'):
        errors.append('title must be a nonempty string.')
    if plan.get('status') not in {'draft', 'accepted'}:
        errors.append('status must be draft or accepted.')
    if not isinstance(plan.get('goal'), str) or not plan.get('goal'):
        errors.append('goal must be a nonempty string.')
    for key in ('nonGoals', 'risks', 'replanTriggers'):
        if key in plan and (not isinstance(plan[key], list) or any(not isinstance(item, str) for item in plan[key])):
            errors.append(f'{key} must be an array of strings.')
    if 'base' in plan and not isinstance(plan['base'], str):
        errors.append('base must be a string.')
    if 'acceptedAt' in plan and not isinstance(plan['acceptedAt'], str):
        errors.append('acceptedAt must be a string.')
    if 'planHash' in plan and not isinstance(plan['planHash'], str):
        errors.append('planHash must be a string.')
    streams = plan.get('streams')
    if not isinstance(streams, list) or not streams:
        errors.append('streams must be a nonempty array.')
        return PlanReport(errors, warnings, [])
    if any(not isinstance(stream, dict) for stream in streams):
        errors.append('every stream must be an object.')
        return PlanReport(errors, warnings, [])
    if len(streams) > max_worktrees:
        errors.append(f'streams: {len(streams)} exceeds the worktree budget ({max_worktrees}).')
    slugs: dict[str, dict] = {}
    for stream in streams:
        extra = sorted(set(stream) - STREAM_KEYS)
        if extra:
            errors.append(f"{stream.get('slug', '?')}: unknown fields: " + ', '.join(extra))
        slug = stream.get('slug')
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            errors.append(f'invalid stream slug: {slug!r}.')
            continue
        if slug in slugs:
            errors.append(f'duplicate slug: {slug}.')
        slugs[slug] = stream
        if stream.get('role') not in ROLES:
            errors.append(f'{slug}: role must be claude-code or codex.')
        if 'summary' in stream and not isinstance(stream['summary'], str):
            errors.append(f'{slug}: summary must be a string.')
        if _strings(stream.get('paths'), f'{slug} paths', errors, minimum=1):
            for owned in stream['paths']:
                if owned.startswith('/') or '\\' in owned or '..' in owned.split('/'):
                    errors.append(f'{slug}: path must be repo-relative: {owned}')
        if _strings(stream.get('acceptance'), f'{slug} acceptance', errors, minimum=min_acceptance):
            pass
        depends = stream.get('dependsOn', [])
        if not isinstance(depends, list) or any(not isinstance(item, str) for item in depends):
            errors.append(f'{slug}: dependsOn must be an array of slugs.')
    if errors:
        return PlanReport(errors, warnings, [])
    for stream in streams:
        for dependency in stream.get('dependsOn', []):
            if dependency == stream['slug']:
                errors.append(f"{stream['slug']}: depends on itself.")
            elif dependency not in slugs:
                errors.append(f"{stream['slug']}: depends on unknown stream {dependency}.")
    order = _topo(streams, errors)
    reach: dict[str, set[str]] = {}
    for slug in order:
        found: set[str] = set()
        for dependency in slugs[slug].get('dependsOn', []):
            if dependency in slugs:
                found.add(dependency)
                found.update(reach.get(dependency, set()))
        reach[slug] = found
    for index, left in enumerate(streams):
        for right in streams[index + 1:]:
            shared = [item for item in left['paths'] if any(_overlaps(item, other) for other in right['paths'])]
            if not shared:
                continue
            ordered = right['slug'] in reach.get(left['slug'], set()) or left['slug'] in reach.get(right['slug'], set())
            shown = ', '.join(shared)
            if ordered:
                warnings.append(f"{left['slug']} and {right['slug']} share {shown}; dependsOn orders them.")
            else:
                errors.append(f"{left['slug']} and {right['slug']} both own {shown} without dependsOn.")
    return PlanReport(errors, warnings, order)


def _topo(streams: list[dict], errors: list[str]) -> list[str]:
    dependencies = {stream['slug']: [item for item in stream.get('dependsOn', []) if item != stream['slug']] for stream in streams}
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(slug: str, stack: list[str]) -> None:
        if state.get(slug) == 2:
            return
        if state.get(slug) == 1:
            errors.append('dependsOn cycle: ' + ' -> '.join([*stack, slug]))
            return
        state[slug] = 1
        for dependency in dependencies.get(slug, []):
            if dependency in dependencies:
                visit(dependency, [*stack, slug])
        state[slug] = 2
        order.append(slug)

    for stream in streams:
        visit(stream['slug'], [])
    return order


def load_plan(path: Path) -> dict:
    if path.is_symlink():
        raise PlanError(f'refusing to read a symlinked plan: {path}')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f'plan is not readable JSON: {path}') from exc
    if not isinstance(value, dict):
        raise PlanError('plan must be a JSON object.')
    return value
