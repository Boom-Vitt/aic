"""Dry-run by default. ``--apply`` is the only path that starts ``claude``."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from orca_claude.plan import PlanError, load_plan, plan_hash, validate_plan
from orca_claude.policy import RESULT_SCHEMA, PolicyError, build_claude_argv, interpret_claude_result, parse_version
from orca_claude.review import assess_readiness


LOW_DISK_KB = 8 * 1024 * 1024
REFUSE_DISK_KB = 2 * 1024 * 1024
CEILING_AGENTS = 4
CEILING_WORKTREES = 6
PROMPT = (
    'You are the Orca orchestrator inside Claude Code. Read the accepted .orca/plan.json. '
    'Use AIC only to restate scope, owners, and acceptance. Implement ready streams in their '
    'existing git worktrees, staying inside owned paths. For a bug stream, reproduce the failure '
    'on the baseline, then show the same command passing and the existing suite passing. '
    'Do not treat an import error or a missing dependency as a reproduction. '
    'Ask a separate read-only reviewer for the diff, SHAs, and command evidence. '
    'Do not push, force-push, delete branches, delete worktrees, deploy, or change credentials. '
    'Do not pass --bare or a permission bypass. Stop when the budget or a blocker is reached. '
    'Return structured output with push_performed false and delete_performed false.'
)


class LoopError(RuntimeError):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def free_kb(path: Path) -> int | None:
    override = os.environ.get('AIC_ORCA_FREE_KB')
    if override:
        try:
            return int(override)
        except ValueError:
            return None
    try:
        result = subprocess.run(['df', '-kP', str(path)], check=False, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or len(lines) < 2:
        return None
    parts = lines[-1].split()
    if len(parts) < 4 or not parts[3].isdigit():
        return None
    return int(parts[3])


def select_budget(max_agents: int, max_worktrees: int, available: int | None, *, enforce_floor: bool) -> tuple[int, int, list[str]]:
    if isinstance(max_agents, bool) or isinstance(max_worktrees, bool):
        raise LoopError('budgets must be positive integers.', 2)
    if not isinstance(max_agents, int) or not isinstance(max_worktrees, int) or max_agents < 1 or max_worktrees < 1:
        raise LoopError('budgets must be positive integers.', 2)
    if max_agents > CEILING_AGENTS or max_worktrees > CEILING_WORKTREES:
        raise LoopError(f'budgets cannot exceed {CEILING_AGENTS} agents and {CEILING_WORKTREES} worktrees.', 3)
    notes: list[str] = []
    agents, trees = max_agents, max_worktrees
    if available is not None and available < REFUSE_DISK_KB:
        notes.append(f'free disk {available} KiB is below the {REFUSE_DISK_KB} KiB floor.')
        if enforce_floor:
            raise LoopError(notes[0], 3)
        agents, trees = 1, 1
    elif available is not None and available < LOW_DISK_KB:
        notes.append('free disk is under 8 GiB; budget is capped at one stream.')
        agents, trees = 1, 1
    return agents, trees, notes


def common_dir(project: Path) -> Path | None:
    try:
        result = subprocess.run(
            ['git', '-C', str(project), 'rev-parse', '--git-common-dir'],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    raw = Path(result.stdout.strip())
    if not raw.is_absolute():
        raw = (project / raw).resolve()
    return raw


def append_ledger(project: Path, event: dict) -> Path | None:
    root = common_dir(project)
    if root is None or root.is_symlink():
        return None
    destination = root / 'orca'
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / 'aic-headless.jsonl'
    if target.is_symlink():
        return None
    with target.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, sort_keys=True) + '\n')
    return target


def accept_plan(path: Path) -> dict:
    plan = load_plan(path)
    report = validate_plan(plan, max_worktrees=CEILING_WORKTREES, min_acceptance=1)
    if report.errors:
        raise LoopError('plan is invalid: ' + '; '.join(report.errors), 1)
    digest = plan_hash(plan)
    if plan.get('status') == 'accepted':
        if plan.get('planHash') != digest:
            raise LoopError('accepted plan hash does not match its content.', 3)
        return plan
    plan['status'] = 'accepted'
    plan['planHash'] = digest
    plan['acceptedAt'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
    return plan


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


def _read_json(path: str | None) -> dict | None:
    if not path:
        return None
    file = Path(path)
    if file.is_symlink():
        raise LoopError(f'refusing symlink: {file}', 3)
    try:
        value = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LoopError(f'unreadable JSON: {file}', 1) from exc
    if not isinstance(value, dict):
        raise LoopError(f'JSON object required: {file}', 1)
    return value


def review_payload(head: str, patch_id: str, gate_path: str | None, review_path: str | None) -> dict:
    decision = assess_readiness(head=head, patch_id=patch_id, gate=_read_json(gate_path), review=_read_json(review_path))
    return {'ok': decision['ready'], 'mode': 'review-check', 'invoked_claude': False, 'push': False, 'delete': False, **decision}


def run_claude(argv: list[str], *, timeout: int, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, check=False, capture_output=True, text=True, timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='orca-headless')
    parser.add_argument('--project', default='.')
    parser.add_argument('--plan')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--accept', action='store_true')
    parser.add_argument('--max-turns', type=int, default=40)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--max-agents', type=int, default=1)
    parser.add_argument('--max-worktrees', type=int, default=1)
    parser.add_argument('--review-check', action='store_true')
    parser.add_argument('--head')
    parser.add_argument('--patch-id')
    parser.add_argument('--gate')
    parser.add_argument('--review')
    parser.add_argument('--settings')
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    try:
        if args.review_check and (args.apply or args.accept):
            raise LoopError('review-check cannot be combined with apply or accept.', 2)
        if args.apply and args.accept:
            raise LoopError('accept the plan, then run apply as a separate command.', 2)
        if isinstance(args.timeout, bool) or not isinstance(args.timeout, int) or not 1 <= args.timeout <= 7200:
            raise LoopError('timeout must be from 1 through 7200 seconds.', 2)
        if args.review_check:
            if not args.head or not args.patch_id:
                raise LoopError('review-check requires --head and --patch-id.', 2)
            decision = review_payload(args.head, args.patch_id, args.gate, args.review)
            return _emit(decision, int(decision['code']))
        plan_path = Path(args.plan) if args.plan else project / '.orca' / 'plan.json'
        if not plan_path.is_absolute():
            plan_path = (project / plan_path).resolve()
        if args.accept:
            plan = accept_plan(plan_path)
        else:
            plan = load_plan(plan_path)
        available = free_kb(project if project.exists() else Path('/'))
        agents, trees, budget_notes = select_budget(
            args.max_agents, args.max_worktrees, available, enforce_floor=args.apply,
        )
        report = validate_plan(plan, max_worktrees=min(agents, trees), min_acceptance=1)
        payload = {
            'ok': report.ok and not args.apply,
            'mode': 'apply' if args.apply else 'dry-run',
            'errors': report.errors,
            'warnings': [*budget_notes, *report.warnings],
            'order': report.order,
            'budget': {'max_agents': agents, 'max_worktrees': trees, 'ceilings': {'agents': CEILING_AGENTS, 'worktrees': CEILING_WORKTREES}},
            'disk_kib': available,
            'fan_out': False,
            'invoked_claude': False,
            'push': False,
            'delete': False,
            'plan_status': plan.get('status'),
        }
        if not report.ok:
            if args.apply:
                append_ledger(project, {'status': 'failed', 'reason': 'budget-or-plan'})
            return _emit(payload, 1)
        if not args.apply:
            payload['ok'] = True
            return _emit(payload, 0)
        if plan.get('status') != 'accepted' or plan.get('planHash') != plan_hash(plan):
            payload['ok'] = False
            payload['errors'] = ['apply requires an accepted plan whose planHash matches its content.']
            append_ledger(project, {'status': 'failed', 'reason': 'unaccepted-plan'})
            return _emit(payload, 3)
        settings = Path(args.settings) if args.settings else project / '.claude' / 'settings.headless.json'
        if not settings.is_file() or settings.is_symlink():
            raise LoopError(f'headless settings are missing: {settings}', 2)
        executable = os.environ.get('AIC_ORCA_CLAUDE', 'claude')
        try:
            version_run = subprocess.run([executable, '--version'], check=False, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise LoopError('claude is not runnable. Install it and sign in before --apply.', 2) from exc
        version = parse_version((version_run.stdout or '') + (version_run.stderr or ''))
        try:
            command = build_claude_argv(
                executable=executable, prompt=PROMPT, max_turns=args.max_turns,
                settings=str(settings), schema=RESULT_SCHEMA, version=version,
            )
        except PolicyError as exc:
            raise LoopError(str(exc), 2) from exc
        if '--bare' in command or '--dangerously-skip-permissions' in command:
            raise LoopError('refusing a bare or permission-bypass invocation.', 3)
        try:
            completed = run_claude(command, timeout=args.timeout, cwd=project)
        except subprocess.TimeoutExpired:
            payload['ok'] = False
            payload['errors'] = [f'claude exceeded the {args.timeout}s wall-clock limit.']
            append_ledger(project, {'status': 'failed', 'reason': 'timeout', 'timeout_sec': args.timeout})
            return _emit(payload, 124)
        payload['invoked_claude'] = True
        payload['claude_exit'] = completed.returncode
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        failures = interpret_claude_result(parsed, completed.stderr)
        if completed.returncode != 0:
            failures.append(f'claude exited {completed.returncode}.')
        payload['errors'] = failures
        payload['ok'] = not failures
        append_ledger(project, {
            'status': 'passed' if payload['ok'] else 'failed',
            'reason': 'claude',
            'claude_exit': completed.returncode,
            'plan_hash': plan.get('planHash'),
        })
        return _emit(payload, 0 if payload['ok'] else 1)
    except LoopError as exc:
        if exc.code in {3, 124}:
            append_ledger(project, {'status': 'failed', 'reason': exc.code, 'message': str(exc)})
        print(str(exc), file=sys.stderr)
        return exc.code
    except PlanError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
