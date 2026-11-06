"""Bounded, read-only filename/size signals for a host AI's assessment.

No manifest or source contents are opened, no ignore files are interpreted, and
no commands, network calls, or model requests are made. Hidden paths and common
sensitive/dependency/build trees are conservatively excluded; this is not a
claim of complete secret detection or full Git-ignore semantics.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from .safety import AICError, checked_root, is_sensitive, relative_path, safe_path


_MAX_FILES = 10_000
_MAX_DEPTH = 32
_EXCLUDED_TREES = frozenset({
    "bower_components", "coverage", "deps", "htmlcov", "out", "target", "vendor",
})
_MANIFEST_STACKS = {
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "setup.py": "Python",
    "setup.cfg": "Python",
    "pipfile": "Python",
    "package.json": "JavaScript/TypeScript",
    "tsconfig.json": "TypeScript",
    "cargo.toml": "Rust",
    "go.mod": "Go",
    "gemfile": "Ruby",
    "composer.json": "PHP",
    "pom.xml": "Java",
    "build.gradle": "Java/Kotlin",
    "build.gradle.kts": "Java/Kotlin",
    "cmakelists.txt": "C/C++",
    "mix.exs": "Elixir",
    "pubspec.yaml": "Dart",
    "package.swift": "Swift",
}
_EXTENSION_STACKS = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".rs": "Rust", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".cs": "C#/.NET", ".fs": "F#/.NET", ".swift": "Swift",
    ".c": "C", ".h": "C/C++", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".ex": "Elixir", ".exs": "Elixir", ".dart": "Dart",
}


def _relative(value: Path) -> str | None:
    """Filter names before returning metadata or considering traversal."""
    if is_sensitive(value) or any(
        part.startswith(".") or part.lower() in _EXCLUDED_TREES
        for part in value.parts
    ):
        return None
    text = value.as_posix()
    try:
        relative_path(text)
    except AICError:
        return None
    return text


def _manifest_stack(path: Path) -> str | None:
    name = path.name.lower()
    if name in _MANIFEST_STACKS:
        return _MANIFEST_STACKS[name]
    if name.startswith("requirements-") and name.endswith(".txt"):
        return "Python"
    if path.suffix.lower() in {".csproj", ".sln"}:
        return "C#/.NET"
    if path.suffix.lower() == ".fsproj":
        return "F#/.NET"
    return None


def _test_signal(path: Path) -> bool:
    name = path.name.lower()
    return (
        any(part.lower() in {"test", "tests", "__tests__"} for part in path.parts[:-1])
        or name.startswith("test_")
        or name.endswith(("_test.go", "_test.py", "_spec.rb"))
        or ".test." in name
        or ".spec." in name
        or name in {"pytest.ini", "tox.ini", "conftest.py"}
    )


def inspect_project(root: Path, *, max_files: int = 200, max_depth: int = 4) -> dict:
    """Inventory regular files without reading contents or following symlinks.

    Root files have directory depth zero. Streaming depth-first traversal selects
    entries in filesystem enumeration order; only the bounded selected results
    are sorted. A truncated subset is not guaranteed to be the lexically first
    subset or identical across filesystems, because that would require scanning
    all siblings. No directory listing is materialized or sorted before bounds
    apply. ``max_files`` must be 1..10000 and ``max_depth`` 0..32; booleans are not
    integers. Global budgets of ``2 * max_files + 1`` directories and
    ``8 * max_files + 1`` enumerated entries also count empty and excluded trees.
    Reaching the entry budget reports truncation conservatively without consuming
    one more entry to determine whether the stream is exhausted. Filename signals
    are hints, not confirmed dependencies or AI conclusions.
    """
    if type(max_files) is not int or not 1 <= max_files <= _MAX_FILES:
        raise AICError(f"max_files must be an integer between 1 and {_MAX_FILES}.")
    if type(max_depth) is not int or not 0 <= max_depth <= _MAX_DEPTH:
        raise AICError(f"max_depth must be an integer between 0 and {_MAX_DEPTH}.")
    base = checked_root(root)
    max_directories = 2 * max_files + 1
    max_entries = 8 * max_files + 1
    inspected_directories = 0
    inspected_entries = 0
    files = []
    manifests = []
    stacks = set()
    test_signals = []
    truncation_reasons = set()
    stopped = False

    def visit(current_relative: Path, depth: int) -> None:
        nonlocal inspected_directories, inspected_entries, stopped
        if stopped:
            return
        if inspected_directories >= max_directories:
            truncation_reasons.add("max_directories")
            stopped = True
            return
        if inspected_entries >= max_entries:
            truncation_reasons.add("max_entries")
            stopped = True
            return
        try:
            current_path = safe_path(base, current_relative.as_posix(), must_exist=True, allow_dot=True)
        except (AICError, OSError):
            # A previously enumerated directory may have changed during the scan.
            truncation_reasons.add("changed_paths")
            return
        inspected_directories += 1
        try:
            with os.scandir(current_path) as entries:
                while not stopped:
                    if inspected_entries >= max_entries:
                        truncation_reasons.add("max_entries")
                        stopped = True
                        return
                    try:
                        entry = next(entries)
                    except StopIteration:
                        return
                    inspected_entries += 1
                    relative = current_relative / entry.name
                    text = _relative(relative)
                    if text is None:
                        continue
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                    except OSError:
                        truncation_reasons.add("unreadable_paths")
                        continue
                    if stat.S_ISDIR(metadata.st_mode):
                        if depth >= max_depth:
                            truncation_reasons.add("max_depth")
                        else:
                            visit(relative, depth + 1)
                        continue
                    if not stat.S_ISREG(metadata.st_mode):
                        # Symlinks, FIFOs and devices are not evidence.
                        continue
                    if len(files) >= max_files:
                        truncation_reasons.add("max_files")
                        stopped = True
                        return
                    files.append({"path": text, "size_bytes": metadata.st_size})
                    manifest_stack = _manifest_stack(relative)
                    if manifest_stack is not None:
                        manifests.append({"path": text, "stack": manifest_stack})
                        stacks.add(manifest_stack)
                    extension_stack = _EXTENSION_STACKS.get(relative.suffix.lower())
                    if extension_stack is not None:
                        stacks.add(extension_stack)
                    if _test_signal(relative):
                        test_signals.append(text)
        except OSError:
            # OS exception text can contain private names; do not return it.
            truncation_reasons.add("unreadable_paths")

    visit(Path("."), 0)
    return {
        "schema_version": 1,
        "project": str(base),
        "inventory_basis": "File names and sizes only; no file contents were read.",
        "selection_order": "Filesystem-order streaming traversal; selected results are sorted, but truncated subsets may differ across filesystems.",
        "files": sorted(files, key=lambda entry: entry["path"]),
        "manifests": sorted(manifests, key=lambda entry: entry["path"]),
        "stacks": sorted(stacks),
        "test_signals": sorted(test_signals),
        "limits": {
            "max_files": max_files, "max_depth": max_depth,
            "max_directories": max_directories, "max_entries": max_entries,
        },
        "inspected_directories": inspected_directories,
        "inspected_entries": inspected_entries,
        "truncated": bool(truncation_reasons),
        "truncation_reasons": sorted(truncation_reasons),
        "exclusions": ["Sensitive paths", "Hidden paths", "Common dependency/build trees", "Symlinks and special files"],
        "ignore_rules": "Ignore-file contents are not read; repository-specific ignore rules are not evaluated.",
    }
