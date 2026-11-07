#!/usr/bin/env python3
"""PreToolUse guard. Exit 2 blocks the tool. Exit 0 allows it.

The script path may use CLAUDE_PROJECT_DIR. Decisions use the hook's cwd,
because CLAUDE_PROJECT_DIR stays at the original checkout after EnterWorktree.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

from orca_claude.policy import decide_tool


def _toplevel(cwd: str) -> str | None:
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ['git', '-C', cwd, 'rev-parse', '--show-toplevel'],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return str(Path(result.stdout.strip()).resolve())


def _plan(cwd: str, headless: bool) -> dict | None:
    candidates = []
    if os.environ.get('ORCA_PLAN'):
        candidates.append(Path(os.environ['ORCA_PLAN']))
    if os.environ.get('CLAUDE_PROJECT_DIR'):
        candidates.append(Path(os.environ['CLAUDE_PROJECT_DIR']) / '.orca' / 'plan.json')
    if cwd:
        candidates.append(Path(cwd) / '.orca' / 'plan.json')
    for path in candidates:
        if path.is_symlink() or not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            if headless:
                raise
            continue
        if isinstance(value, dict):
            return value
    return None


def main() -> int:
    headless = os.environ.get('ORCA_HEADLESS') == '1'
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            print('hook input must be a JSON object.', file=sys.stderr)
            return 2
        cwd = data.get('cwd') if isinstance(data.get('cwd'), str) else ''
        active = os.environ.get('ORCA_ACTIVE_WORKTREE') or None
        code, message = decide_tool(
            str(data.get('tool_name') or ''),
            data.get('tool_input'),
            headless=headless,
            active_stream=os.environ.get('ORCA_ACTIVE_STREAM') or None,
            active_worktree=active,
            resolved_toplevel=_toplevel(cwd) if active else None,
            plan=_plan(cwd, headless),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f'guard failed closed: {exc}', file=sys.stderr)
        return 2
    if code != 0:
        print(message, file=sys.stderr)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
