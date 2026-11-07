"""Copy the Orca project template into a new absolute directory.

The destination must not already exist. Symlinked parents and symlinked
template files are refused. Nothing inside the destination is overwritten
because the directory is created only for this copy.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys


REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / 'templates' / 'orca-claude'
EXTRA_SCRIPTS = (
    'scripts/orca-headless.sh',
    'scripts/bootstrap-orca-project.sh',
    'scripts/macos-setup-orca.sh',
    'scripts/orca-gate.sh',
)


class BootstrapError(RuntimeError):
    """The new project path cannot be created safely."""


def _refuse_symlink(path: Path) -> None:
    if path.is_symlink():
        raise BootstrapError(f'refusing symlink: {path}')


def assert_destination(dest: Path) -> Path:
    if not dest.is_absolute():
        raise BootstrapError('project path must be absolute.')
    if dest.is_symlink():
        raise BootstrapError(f'refusing symlink destination: {dest}')
    resolved = Path(os.path.realpath(dest))
    current = resolved
    while True:
        if current.is_symlink():
            raise BootstrapError(f'refusing symlinked path component: {current}')
        if current == current.parent:
            break
        current = current.parent
    if resolved.exists():
        raise BootstrapError(f'refusing existing path: {resolved}')
    try:
        relative = resolved.relative_to(REPO.resolve())
    except ValueError:
        relative = None
    if relative is not None and not (relative.parts and relative.parts[0] == '.work'):
        raise BootstrapError('refusing to create a project inside this repository.')
    return resolved


def _copy_file(source: Path, target: Path) -> None:
    _refuse_symlink(source)
    if not source.is_file():
        raise BootstrapError(f'missing template file: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise BootstrapError(f'refusing to overwrite {target}')
    shutil.copy2(source, target, follow_symlinks=False)


def _remove_partial(dest: Path) -> None:
    if dest.is_symlink() or not dest.is_dir():
        return
    shutil.rmtree(dest)


def copy_template(dest: Path) -> list[str]:
    dest = assert_destination(dest)
    written: list[str] = []
    created = False
    try:
        dest.mkdir(parents=True, exist_ok=False)
        created = True
        for source in sorted(TEMPLATE.rglob('*')):
            if source.is_dir() and not source.is_symlink():
                continue
            relative = source.relative_to(TEMPLATE).as_posix()
            _copy_file(source, dest / relative)
            written.append(relative)
        package = REPO / 'scripts' / 'orca_claude'
        for source in sorted(package.glob('*.py')):
            relative = f'scripts/orca_claude/{source.name}'
            _copy_file(source, dest / relative)
            written.append(relative)
        for relative in EXTRA_SCRIPTS:
            _copy_file(REPO / relative, dest / relative)
            written.append(relative)
        gate = dest / 'gate.sh'
        if not gate.exists():
            _copy_file(REPO / 'scripts' / 'orca-gate.sh', gate)
            written.append('gate.sh')
        gate.chmod(gate.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        orca_gate = dest / '.orca' / 'gate.sh'
        _copy_file(REPO / 'scripts' / 'orca-gate.sh', orca_gate)
        orca_gate.chmod(orca_gate.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append('.orca/gate.sh')
    except Exception:
        if created:
            _remove_partial(dest)
        raise
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='bootstrap-orca-project')
    parser.add_argument('path', help='absolute path of a directory that does not exist yet')
    args = parser.parse_args(argv)
    try:
        written = copy_template(Path(args.path))
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(f'created {args.path} ({len(written)} files)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
