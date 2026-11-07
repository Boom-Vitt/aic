"""Run a command only in the git worktree the caller named."""
from __future__ import annotations

from pathlib import Path
import subprocess


class WorktreeError(RuntimeError):
    """The active checkout is not the worktree that should run the command."""


def toplevel(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ['git', '-C', str(cwd), 'rev-parse', '--show-toplevel'],
            check=False, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorktreeError('git could not resolve the worktree.') from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise WorktreeError('cwd is not inside a git worktree.')
    return Path(result.stdout.strip()).resolve()


def run_in(cwd: Path, argv: list[str], *, expected: Path) -> subprocess.CompletedProcess[str]:
    if not argv or argv[0].startswith('-') or any(not isinstance(item, str) or '\x00' in item for item in argv):
        raise WorktreeError('refusing an empty or unsafe argv.')
    actual = toplevel(cwd)
    if actual != expected.resolve():
        raise WorktreeError(f'refusing to run in {actual}; expected {expected.resolve()}.')
    return subprocess.run(argv, cwd=actual, check=False, capture_output=True, text=True, timeout=120)
