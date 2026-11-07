"""Copy a task workspace and grade it with its hidden oracle.

The oracle process has no API key and no model client. It runs under
``python -I`` so the workspace cannot shadow the standard library. A nonzero
oracle exit, including a timeout, is a failed grade.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .catalog import Task

ORACLE_KEY = "oracle/test_oracle.py"
ORACLE_LAUNCHER = """
import importlib.util
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
workspace = Path(sys.argv[1]).resolve()
oracle = Path(sys.argv[2]).resolve()
os.environ["AICBENCH_WORKSPACE"] = str(workspace)
sys.path = [entry for entry in sys.path if entry not in {"", "."}]
blocked = set(getattr(sys, "stdlib_module_names", ()))
blocked.update({"__main__", "test", "unittest"})


class WorkspaceFinder:
    def find_spec(self, fullname, path, target=None):
        if path is not None or "." in fullname or fullname in blocked:
            return None
        package = workspace / fullname
        module = workspace / (fullname + ".py")
        init = package / "__init__.py"
        if package.is_dir() and not package.is_symlink() and init.is_file() and not init.is_symlink():
            if not _inside(init):
                return None
            return importlib.util.spec_from_file_location(
                fullname, init, submodule_search_locations=[str(package.resolve())]
            )
        if module.is_file() and not module.is_symlink() and _inside(module):
            return importlib.util.spec_from_file_location(fullname, module)
        return None


def _inside(path):
    resolved = path.resolve()
    return resolved == workspace or workspace in resolved.parents


sys.meta_path.insert(0, WorkspaceFinder())
spec = importlib.util.spec_from_file_location("__main__", oracle)
if spec is None or spec.loader is None:
    raise SystemExit(2)
module = importlib.util.module_from_spec(spec)
sys.modules["__main__"] = module
spec.loader.exec_module(module)
"""


class GradeError(RuntimeError):
    """The workspace could not be prepared or graded safely."""


class IntegrityError(GradeError):
    """Oracle or reference bytes no longer match the pre-agent snapshot."""


@dataclass(frozen=True)
class GradeResult:
    passed: bool
    timed_out: bool
    returncode: int | None
    detail: str


def _copy_tree(source: Path, dest: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise GradeError("A task tree must be a real directory.")
    dest.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in {"__pycache__", ".git"} or part.startswith(".") for part in relative.parts):
            continue
        target = dest.joinpath(*relative.parts)
        if path.is_symlink():
            raise GradeError("Refusing to copy a symlink from a task tree.")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            raise GradeError("A task tree contains an unsupported file type.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def _contained(dest: Path, relative: str) -> Path:
    root = dest.resolve()
    candidate = root.joinpath(*relative.split("/")).resolve()
    if candidate != root and root not in candidate.parents:
        raise GradeError("A reference removal escapes the workspace.")
    return candidate


def prepare_workspace(task: Task, dest: Path, *, solution: bool) -> None:
    """Write the public starting tree, optionally overlaid with the reference solution."""
    if dest.exists():
        raise GradeError("Refusing to prepare a workspace that already exists.")
    _copy_tree(task.workspace, dest)
    if solution:
        overlay_reference(task, dest)


def overlay_reference(task: Task, dest: Path) -> None:
    """Replace workspace files with the reference solution. `dest` must already exist."""
    if dest.is_symlink() or not dest.is_dir():
        raise GradeError("The reference overlay needs an existing workspace directory.")
    _copy_tree(task.reference, dest)
    for relative in task.remove:
        target = _contained(dest, relative)
        if target.is_dir() and not target.is_symlink():
            for child in sorted(target.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            target.rmdir()
        elif target.is_file() and not target.is_symlink():
            target.unlink()
        else:
            raise GradeError(f"The reference removal is missing: {relative}")


def outside_repository_temp() -> Path:
    """Return a temp directory whose resolved path is not inside this repository."""
    repo = Path(__file__).resolve().parents[2].resolve()
    seen: set[Path] = set()
    for candidate in (Path("/tmp"), Path("/var/tmp"), Path(tempfile.gettempdir())):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        if resolved == repo or repo in resolved.parents or resolved in repo.parents:
            continue
        return resolved
    raise GradeError("No temp directory outside the repository is available.")


def grade_env(workspace: Path) -> dict[str, str]:
    """Environment for an oracle. Model credentials and PYTHONPATH are not forwarded."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "AICBENCH_WORKSPACE": str(workspace),
        "LANG": "C",
        "LC_ALL": "C",
    }


def _protected_paths(task: Task) -> list[tuple[str, Path]]:
    if task.oracle.is_symlink() or not task.oracle.is_file():
        raise IntegrityError("oracle/reference integrity mismatch: oracle/test_oracle.py")
    if task.reference.is_symlink() or not task.reference.is_dir():
        raise IntegrityError("oracle/reference integrity mismatch: reference")
    pairs = [(ORACLE_KEY, task.oracle)]
    for path in sorted(task.reference.rglob("*")):
        relative = path.relative_to(task.reference).as_posix()
        if any(part == "__pycache__" for part in path.relative_to(task.reference).parts):
            continue
        key = f"reference/{relative}"
        if path.is_symlink():
            raise IntegrityError(f"oracle/reference integrity mismatch: {key}")
        if path.is_file():
            if path.suffix == ".pyc":
                continue
            pairs.append((key, path))
        elif not path.is_dir():
            raise IntegrityError(f"oracle/reference integrity mismatch: {key}")
    return pairs


def protected_bytes(task: Task) -> dict[str, bytes]:
    """Read oracle and reference bytes. Symlinks are an integrity failure."""
    return {key: path.read_bytes() for key, path in _protected_paths(task)}


def sha256_manifest(files: dict[str, bytes]) -> dict[str, str]:
    """SHA-256 hex digest for each protected file."""
    return {key: hashlib.sha256(files[key]).hexdigest() for key in sorted(files)}


def verified_bytes(task: Task, expected: dict[str, str]) -> dict[str, bytes]:
    """Re-read protected files and return them only when the manifest matches."""
    current = protected_bytes(task)
    actual = sha256_manifest(current)
    if actual != expected:
        changed = set(actual) ^ set(expected)
        changed.update(key for key in actual.keys() & expected.keys() if actual[key] != expected[key])
        names = ", ".join(sorted(changed))
        raise IntegrityError(f"oracle/reference integrity mismatch: {names}")
    return current


def oracle_command(workspace: Path, oracle_path: Path) -> list[str]:
    """Isolated interpreter. The workspace is not on PYTHONPATH or sys.path."""
    return [sys.executable, "-I", "-B", "-c", ORACLE_LAUNCHER, str(workspace), str(oracle_path)]


def _tail(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    return text[-4000:]


def grade(task: Task, workspace: Path, *, oracle_bytes: bytes | None = None) -> GradeResult:
    """Run a copy of the hidden oracle. The copy is created here, at grade time."""
    if workspace.is_symlink() or not workspace.is_dir():
        raise GradeError("The graded workspace must be a real directory.")
    payload = oracle_bytes if oracle_bytes is not None else protected_bytes(task)[ORACLE_KEY]
    if not payload:
        raise GradeError("The hidden oracle is empty.")
    with tempfile.TemporaryDirectory(prefix="aicbench-oracle-", dir=outside_repository_temp()) as temporary:
        oracle_path = Path(temporary) / "aicbench_oracle.py"
        oracle_path.write_bytes(payload)
        command = oracle_command(workspace.resolve(), oracle_path)
        try:
            completed = subprocess.run(
                command,
                cwd=temporary,
                env=grade_env(workspace),
                capture_output=True,
                text=True,
                timeout=task.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return GradeResult(False, True, None, _tail(exc.stdout) + _tail(exc.stderr))
    detail = _tail(completed.stdout) + _tail(completed.stderr)
    return GradeResult(completed.returncode == 0, False, completed.returncode, detail)
