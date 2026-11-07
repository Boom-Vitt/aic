"""Load the on-disk aicbench task catalog."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
CATEGORIES = frozenset({"bugfix", "feature", "refactor", "docs"})


class CatalogError(ValueError):
    """A task directory does not match the aicbench contract."""


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    category: str
    timeout_seconds: int
    remove: tuple[str, ...]
    instruction: str
    root: Path

    @property
    def workspace(self) -> Path:
        return self.root / "workspace"

    @property
    def reference(self) -> Path:
        return self.root / "reference"

    @property
    def oracle(self) -> Path:
        return self.root / "oracle" / "test_oracle.py"


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("Task metadata contains a duplicate JSON key.")
        result[key] = value
    return result


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CatalogError(f"{label} must be a nonempty relative path.")
    if "\x00" in value or "\\" in value or value.startswith("/"):
        raise CatalogError(f"{label} cannot be absolute or contain NUL or backslashes.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CatalogError(f"{label} cannot contain empty, current, or parent parts.")
    return value


def _regular_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        raise CatalogError(f"Expected a real directory: {directory.name}")
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise CatalogError(f"Task files cannot be symlinks: {path.name}")
        if path.is_file():
            files.append(path)
    if not files:
        raise CatalogError(f"{directory.name} does not contain a file.")
    return files


def _task(directory: Path) -> Task:
    meta_path = directory / "task.json"
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"), object_pairs_hook=_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{directory.name} metadata is not UTF-8 JSON.") from exc
    if not isinstance(metadata, dict):
        raise CatalogError(f"{directory.name} metadata must be an object.")
    task_id = metadata.get("id")
    title = metadata.get("title")
    category = metadata.get("category")
    timeout = metadata.get("timeout_seconds")
    remove = metadata.get("remove", [])
    if not isinstance(task_id, str) or task_id != directory.name:
        raise CatalogError(f"{directory.name} id must match its directory name.")
    if not isinstance(title, str) or not title.strip():
        raise CatalogError(f"{task_id} requires a title.")
    if category not in CATEGORIES:
        raise CatalogError(f"{task_id} has an unknown category.")
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise CatalogError(f"{task_id} timeout must be an integer from 1 to 120 seconds.")
    if not isinstance(remove, list):
        raise CatalogError(f"{task_id} remove must be a list.")
    removed = tuple(_relative(item, f"{task_id} remove") for item in remove)
    try:
        instruction = (directory / "instruction.md").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise CatalogError(f"{task_id} instruction is not UTF-8 text.") from exc
    if len(instruction) < 200:
        raise CatalogError(f"{task_id} instruction is too short to be a complete task.")
    task = Task(task_id, title.strip(), category, timeout, removed, instruction + "\n", directory)
    _regular_files(task.workspace)
    _regular_files(task.reference)
    if task.oracle.is_symlink() or not task.oracle.is_file():
        raise CatalogError(f"{task_id} is missing its hidden oracle.")
    return task


def load_catalog() -> tuple[Task, ...]:
    """Return every valid task, sorted by id."""
    if not TASKS.is_dir():
        raise CatalogError("The aicbench task directory is missing.")
    directories = [path for path in TASKS.iterdir() if path.is_dir() and not path.name.startswith(".")]
    tasks = tuple(sorted((_task(path) for path in directories), key=lambda item: item.id))
    seen: set[str] = set()
    for task in tasks:
        if task.id in seen:
            raise CatalogError(f"Duplicate task id: {task.id}")
        seen.add(task.id)
    if len(tasks) < 20:
        raise CatalogError("aicbench requires at least 20 tasks.")
    return tasks
