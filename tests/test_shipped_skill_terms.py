"""Shipped skill files must not name this repository's benchmark internals."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "aic"
TASKS = ROOT / "benchmarks" / "aicbench" / "tasks"
_TEXT_SUFFIXES = {".md", ".py", ".json", ".txt", ".conf"}
_WORDS = ("oracle", "grader", "aicbench")


def _task_ids() -> list[str]:
    return sorted(
        path.name
        for path in TASKS.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def _hits(text: str, task_ids: list[str]) -> list[str]:
    folded = text.casefold()
    found: list[str] = []
    for word in _WORDS:
        if re.search(rf"\b{word}\b", folded):
            found.append(word)
    if re.search(r"(?<![a-z])reference/", folded):
        found.append("reference/")
    if "reference solution" in folded:
        found.append("reference solution")
    for task_id in task_ids:
        if re.search(rf"(?<![a-z0-9-]){re.escape(task_id)}(?![a-z0-9-])", folded):
            found.append(task_id)
    return found


class ShippedSkillTermTests(unittest.TestCase):
    def test_shipped_skill_files_omit_benchmark_internals(self):
        task_ids = _task_ids()
        self.assertGreater(len(task_ids), 0)
        offenders: list[str] = []
        files = [path for path in SKILL.rglob("*") if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES]
        self.assertGreater(len(files), 0)
        for path in files:
            if "__pycache__" in path.parts:
                continue
            found = _hits(path.read_text(encoding="utf-8"), task_ids)
            if found:
                relative = path.relative_to(ROOT).as_posix()
                offenders.append(f"{relative}: {', '.join(found)}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
