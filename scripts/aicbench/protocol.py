"""Validate a benchmark run before any command starts."""
from __future__ import annotations

import json
from pathlib import Path


REQUIRED_BUDGET = ('max_turns', 'timeout_sec', 'max_usd')
CONDITION_FIELDS = ('id', 'benchmark_revision', 'model', 'seed')


class BenchError(ValueError):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def load_json(path: Path) -> dict:
    if path.is_symlink():
        raise BenchError(f'refusing a symlinked file: {path}', 3)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchError(f'unreadable JSON: {path}', 1) from exc
    if not isinstance(value, dict):
        raise BenchError(f'JSON object required: {path}', 1)
    return value


def catalog_entry(catalog: dict, suite_id: str) -> dict:
    suites = catalog.get('suites')
    if not isinstance(suites, list):
        raise BenchError('catalog suites must be a list.', 1)
    matches = [item for item in suites if isinstance(item, dict) and item.get('id') == suite_id]
    if len(matches) != 1:
        raise BenchError(f'unknown suite: {suite_id}', 2)
    return matches[0]


def _budget_ok(budget: object) -> bool:
    if not isinstance(budget, dict):
        return False
    if set(budget) != set(REQUIRED_BUDGET):
        return False
    turns, timeout, spend = budget['max_turns'], budget['timeout_sec'], budget['max_usd']
    if isinstance(turns, bool) or isinstance(timeout, bool) or not isinstance(turns, int) or not isinstance(timeout, int):
        return False
    if turns < 0 or not 1 <= timeout <= 7200:
        return False
    if isinstance(spend, bool) or not isinstance(spend, (int, float)) or spend < 0:
        return False
    return True


def validate_suite(suite: dict) -> None:
    if suite.get('schema_version') != 1:
        raise BenchError('suite schema_version must be 1.', 1)
    if not isinstance(suite.get('id'), str) or not suite['id']:
        raise BenchError('suite id is required.', 1)
    if not isinstance(suite.get('benchmark_revision'), str) or not suite['benchmark_revision']:
        raise BenchError('benchmark_revision is required.', 1)
    if not isinstance(suite.get('model'), str) or not suite['model']:
        raise BenchError('model is required. Use "none" only for a local recorder check.', 1)
    if isinstance(suite.get('seed'), bool) or not isinstance(suite.get('seed'), int):
        raise BenchError('seed must be an integer.', 1)
    if not _budget_ok(suite.get('budget')):
        raise BenchError('budget must set max_turns, timeout_sec, and max_usd.', 1)
    arms = suite.get('arms')
    if not isinstance(arms, list) or not arms or any(not isinstance(item, str) or not item for item in arms):
        raise BenchError('arms must be a nonempty list of names.', 1)
    if len(set(arms)) != len(arms):
        raise BenchError('arm names must be unique.', 1)
    if suite.get('executable') is True:
        tasks = suite.get('tasks')
        if not isinstance(tasks, list) or not tasks:
            raise BenchError('an executable suite needs tasks.', 1)
        for task in tasks:
            if not isinstance(task, dict):
                raise BenchError('each task must be an object.', 1)
            argv = task.get('argv')
            cwd = task.get('cwd')
            if not isinstance(task.get('id'), str) or not isinstance(cwd, str) or cwd.startswith('/') or '..' in cwd.split('/'):
                raise BenchError('task id and relative cwd are required.', 1)
            if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item or item.startswith('-') or '\x00' in item for item in argv):
                raise BenchError('task argv must be a list of safe strings.', 1)
    if suite.get('invokes_model') is True and suite.get('executable') is True:
        raise BenchError('this skeleton does not execute a model suite.', 3)


def conditions(suite: dict) -> dict:
    return {field: suite.get(field) for field in CONDITION_FIELDS} | {'budget': suite.get('budget')}


def same_conditions(left: dict, right: dict) -> bool:
    return conditions(left) == conditions(right) and left.get('id') == right.get('id')
