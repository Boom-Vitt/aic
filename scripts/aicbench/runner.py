"""Plan or run the local smoke recorder. Public benchmarks stay blocked."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from aicbench.official import run_official
from aicbench.protocol import BenchError, catalog_entry, load_json, validate_suite


ROOT = Path(__file__).resolve().parents[2]


def _suite_for(catalog: dict, suite_id: str) -> tuple[dict, Path | None]:
    entry = catalog_entry(catalog, suite_id)
    if entry.get('executable') is not True:
        raise BenchError(str(entry.get('blocked') or 'suite is not executable.'), 3)
    relative = entry.get('path')
    if not isinstance(relative, str):
        raise BenchError('executable suite is missing a path.', 1)
    path = ROOT / relative
    suite = load_json(path)
    if suite.get('id') != suite_id:
        raise BenchError('suite file id does not match the catalog.', 1)
    validate_suite(suite)
    return suite, path.parent


def plan(catalog: dict, suite_id: str) -> dict:
    entry = catalog_entry(catalog, suite_id)
    if entry.get('executable') is not True:
        return {
            'ok': False,
            'executed': False,
            'suite': suite_id,
            'public_benchmark_scores': None,
            'blocked': entry.get('blocked'),
        }
    suite, _parent = _suite_for(catalog, suite_id)
    return {
        'ok': True,
        'executed': False,
        'suite': suite_id,
        'benchmark_revision': suite['benchmark_revision'],
        'model': suite['model'],
        'seed': suite['seed'],
        'budget': suite['budget'],
        'arms': suite['arms'],
        'tasks': [task['id'] for task in suite['tasks']],
        'invokes_model': False,
        'public_benchmark_scores': None,
    }


def execute_suite(suite: dict, parent: Path) -> dict:
    validate_suite(suite)
    if suite.get('invokes_model') is True or suite.get('public_benchmark') is True:
        raise BenchError('refusing to score a public or model suite.', 3)
    runs = []
    for arm in suite['arms']:
        for task in suite['tasks']:
            cwd = (parent / task['cwd']).resolve()
            if cwd.is_symlink():
                raise BenchError(f'refusing symlinked task directory: {cwd}', 3)
            try:
                cwd.relative_to(parent.resolve())
            except ValueError as exc:
                raise BenchError(f'task cwd escapes the suite: {task["id"]}', 3) from exc
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    task['argv'], cwd=cwd, check=False, capture_output=True, text=True,
                    timeout=suite['budget']['timeout_sec'],
                )
                code = completed.returncode
            except subprocess.TimeoutExpired:
                code = 124
            except OSError as exc:
                raise BenchError(f'task failed to start: {task["id"]}: {exc}', 1) from exc
            runs.append({
                'arm': arm,
                'task': task['id'],
                'exit_code': code,
                'seconds': round(time.monotonic() - started, 3),
                'workflow_loaded': False,
            })
    return {
        'ok': all(item['exit_code'] == 0 for item in runs),
        'executed': True,
        'suite': suite['id'],
        'benchmark_revision': suite['benchmark_revision'],
        'model': suite['model'],
        'seed': suite['seed'],
        'budget': suite['budget'],
        'arms': suite['arms'],
        'runs': runs,
        'recorded_runs': len(runs),
        'exit_zero_runs': sum(1 for item in runs if item['exit_code'] == 0),
        'invokes_model': False,
        'public_benchmark_scores': None,
        'note': 'Local recorder check only. Not a SWE-bench, Terminal-Bench, Aider, or real-task result.',
    }


def run_smoke(catalog: dict, suite_id: str) -> dict:
    suite, parent = _suite_for(catalog, suite_id)
    if parent is None:
        raise BenchError('smoke suite path is missing.', 1)
    return execute_suite(suite, parent)


def main(argv: list[str] | None = None, sandbox_runner=None) -> int:
    parser = argparse.ArgumentParser(prog='aicbench')
    parser.add_argument('command', nargs='?', choices=('plan', 'run'))
    parser.add_argument('--suite')
    parser.add_argument('--catalog', default=str(ROOT / 'benchmarks' / 'catalog.json'))
    parser.add_argument('--output')
    parser.add_argument('--sandbox', choices=('container',))
    parser.add_argument('--official', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.official or args.sandbox:
            if args.command is not None or args.suite is not None:
                raise BenchError('official container mode does not take a suite command.', 2)
            if args.sandbox != 'container' or not args.official:
                raise BenchError('the official run requires --sandbox container --official.', 2)
            payload = run_official(ROOT, sandbox_runner=sandbox_runner)
        else:
            if args.command is None or not args.suite:
                raise BenchError('plan or run requires --suite.', 2)
            catalog = load_json(Path(args.catalog))
            payload = plan(catalog, args.suite) if args.command == 'plan' else run_smoke(catalog, args.suite)
    except BenchError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    text = json.dumps(payload, indent=2, sort_keys=True) + '\n'
    if args.output:
        target = Path(args.output)
        if target.exists() or target.is_symlink():
            print(f'refusing to overwrite {target}', file=sys.stderr)
            return 3
        target.write_text(text, encoding='utf-8')
    print(text, end='')
    if args.command == 'plan' and payload.get('executed') is False and payload.get('ok') is False:
        return 3
    return 0 if payload.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
