"""Find skill directories without following symlinks."""

from __future__ import annotations

import os
from pathlib import Path

class LintError(ValueError):
    """The requested path cannot be linted."""


SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "venv",
    }
)


def open_root(value: str | Path) -> Path:
    """Return the real directory a user asked to lint.

    The final path component must not be a symlink. A direct ``SKILL.md``
    argument selects its parent skill directory.
    """

    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise LintError("A non-empty path is required.")
    path = Path(os.path.abspath(raw))
    if path.is_symlink():
        raise LintError("Refusing to follow a symlinked path.")
    if path.is_file() and path.name.lower() == "skill.md":
        return open_root(path.parent)
    if not path.is_dir():
        raise LintError(f"Expected a skill or repository directory: {path}")
    return path


def discover_skills(root: Path) -> list[tuple[Path, Path]]:
    """Return ``(skill directory, entry file)`` pairs sorted by relative path.

    ``SKILL.md`` wins when both casings exist. Directory symlinks are not
    entered, so an alias of a skill is not scored a second time. Dependency
    and VCS directories are skipped. ``.github`` is not skipped.
    """

    found: list[tuple[Path, Path]] = []

    def walk(directory: Path) -> None:
        try:
            children = list(directory.iterdir())
        except OSError as exc:
            raise LintError(f"Cannot list {directory}: {exc.strerror or exc}") from exc
        entry = _entry_file(children)
        if entry is not None:
            found.append((directory, entry))
        for child in sorted(children, key=lambda item: item.name):
            if not child.is_dir() or child.is_symlink():
                continue
            if child.name in SKIP_DIRECTORIES:
                continue
            walk(child)

    walk(root)
    return sorted(found, key=lambda item: _relative(root, item[0]))


def iter_skill_files(skill: Path, nested: frozenset[Path]) -> list[Path]:
    """Return regular files inside one skill, excluding nested skills."""

    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(skill, followlinks=False):
        current = Path(directory)
        kept: list[str] = []
        for name in sorted(dirnames):
            child = current / name
            if child in nested or child.is_symlink() or name in SKIP_DIRECTORIES:
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink() or not path.is_file():
                continue
            files.append(path)
    return files


def relative_path(root: Path, path: Path) -> str:
    """POSIX path of ``path`` relative to ``root``."""

    return _relative(root, path)


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() or "."


def _entry_file(children: list[Path]) -> Path | None:
    by_name = {child.name: child for child in children}
    for name in ("SKILL.md", "skill.md"):
        candidate = by_name.get(name)
        if candidate is None or candidate.is_symlink() or not candidate.is_file():
            continue
        return candidate
    return None


def read_text(path: Path) -> str:
    """Read a UTF-8 skill entry. Binary and non-UTF-8 files raise ``UnicodeError``."""

    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        raise UnicodeError("binary skill entry")
    return data.decode("utf-8")
