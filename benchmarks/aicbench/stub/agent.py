#!/usr/bin/env python3
"""Pipeline smoke test for the aicbench sandbox. Not a model result."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROBE_NAME = "pipeline-smoke.json"
LABEL = "pipeline smoke test"
TAMPER_BODY = "raise SystemExit('pipeline-smoke-tamper')\n"


def _refuse(message: str) -> int:
    print(f"pipeline smoke test: {message}", file=sys.stderr)
    return 2


def _readable(path: Path) -> bool:
    """True when this process can read the path. File bytes are not returned."""
    try:
        if path.is_symlink():
            return False
        if path.is_dir():
            tuple(path.iterdir())
            return True
        if path.is_file():
            path.read_bytes()
            return True
    except OSError:
        return False
    return False


def _probe() -> int:
    probe_path = Path.cwd() / PROBE_NAME
    try:
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _refuse("probe file is missing.")
    if not isinstance(probe, dict) or probe.get("role") != "pipeline-smoke":
        return _refuse("probe role is not pipeline-smoke.")
    try:
        reference = Path(probe["reference"])
        oracle = Path(probe["oracle"])
    except (KeyError, TypeError):
        return _refuse("probe paths are missing.")
    payload = {
        "api_key_visible": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "label": LABEL,
        "oracle_readable": _readable(oracle),
        "pythonpath_visible": "PYTHONPATH" in os.environ,
        "reference_readable": _readable(reference),
        "role": "pipeline-smoke",
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _tamper(target: Path) -> int:
    if target.is_symlink() or target.is_dir():
        return _refuse("refusing to tamper with that path.")
    target.write_text(TAMPER_BODY, encoding="utf-8")
    return 0


def _flag_values(flag: str) -> list[str]:
    found = []
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        if args[index] == flag and index + 1 < len(args):
            found.append(args[index + 1])
            index += 2
        else:
            index += 1
    return found


def _one(flag: str) -> str | None:
    values = _flag_values(flag)
    if not values:
        return None
    if len(values) != 1:
        return ""
    return values[0]


def _overlay_reference(reference: Path, dest: Path, remove: list[str]) -> str | None:
    """Copy reference files onto dest. The oracle directory is never a source."""
    if reference.is_symlink() or not reference.is_dir():
        return "reference is not a real directory."
    if "oracle" in reference.parts:
        return "refusing an oracle path."
    root = dest.resolve()
    for path in sorted(reference.rglob("*")):
        relative = path.relative_to(reference)
        if any(part in {"__pycache__", ".git", "oracle"} for part in relative.parts):
            continue
        if path.is_symlink():
            return "refusing a symlinked reference file."
        target = root.joinpath(*relative.parts).resolve()
        if target != root and root not in target.parents:
            return "reference copy escapes the workspace."
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        else:
            return "reference contains an unsupported file."
    for relative in remove:
        if not isinstance(relative, str) or not relative or relative.startswith("/") or ".." in relative.split("/"):
            return "refusing an unsafe removal."
        target = root.joinpath(*relative.split("/")).resolve()
        if target != root and root not in target.parents:
            return "removal escapes the workspace."
        if target.is_symlink():
            return "refusing to remove a symlink."
        if target.is_file():
            target.unlink()
        elif target.exists():
            return "removal is not a file."
    return None


def _plugin_name(directory: str) -> tuple[str | None, str | None]:
    path = Path(directory) / ".claude-plugin" / "plugin.json"
    if path.is_symlink() or not path.is_file():
        return None, "plugin manifest missing."
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "plugin manifest unreadable."
    name = payload.get("name") if isinstance(payload, dict) else None
    if not isinstance(name, str) or not name:
        return None, "plugin name missing."
    return name, None


def _skill_stand_in(directory: str) -> bool:
    path = Path(directory) / "SKILL.md"
    if path.is_symlink() or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")[:500]
    except (OSError, UnicodeError):
        return False
    return "AIC baseline stub stand-in. Not upstream text." in text


def _home_skill() -> tuple[bool, str | None]:
    """Stand-in skill written into this arm's fresh HOME. Symlinks are ignored."""
    home = os.environ.get("HOME", "")
    if not home:
        return False, None
    root = Path(home) / ".claude" / "skills"
    if root.is_symlink() or not root.is_dir():
        return False, None
    try:
        children = sorted(root.iterdir())
    except OSError:
        return False, None
    for path in children:
        if path.is_symlink() or not path.is_dir():
            continue
        if _skill_stand_in(str(path)):
            return True, path.name
    return False, None


def _baseline_stub() -> int:
    """Offline baseline adapter proof.

    The pipeline-smoke copy of this file must start with no repository imports.
    This mode stays in the same file so CI can point the baseline adapters at
    the existing stub agent. It is not a model.
    """
    reference = os.environ.get("AICBENCH_STUB_REFERENCE", "")
    if not reference:
        return _refuse("baseline stub is missing its reference directory.")
    try:
        remove = json.loads(os.environ.get("AICBENCH_STUB_REMOVE", "[]"))
    except json.JSONDecodeError:
        return _refuse("baseline stub removals are not JSON.")
    if not isinstance(remove, list):
        return _refuse("baseline stub removals must be a list.")
    problem = _overlay_reference(Path(reference), Path.cwd(), remove)
    if problem:
        return _refuse(problem)
    model = _one("--model")
    turns = _one("--max-turns")
    spend = _one("--max-budget-usd")
    if not model or not turns or not spend:
        return _refuse("baseline stub requires one --model, one --max-turns, and one --max-budget-usd.")
    plugin_dirs = _flag_values("--plugin-dir")
    add_dirs = _flag_values("--add-dir")
    if len(plugin_dirs) > 1 or len(add_dirs) > 1 or (plugin_dirs and add_dirs):
        return _refuse("baseline stub accepts only one mount.")
    plugin_name = None
    skill_stand_in = False
    if plugin_dirs:
        plugin_name, error = _plugin_name(plugin_dirs[0])
        if error:
            return _refuse(error)
    if add_dirs:
        skill_stand_in = _skill_stand_in(add_dirs[0])
        if not skill_stand_in:
            return _refuse("add-dir mount has no stand-in skill marker.")
    home_skill, home_skill_name = _home_skill()
    prompt = next((arg for arg in sys.argv[1:] if arg.startswith("Task id:")), "")
    task_id = ""
    if prompt.startswith("Task id:"):
        task_id = prompt.split("Task id:", 1)[1].splitlines()[0].strip()
    payload = {
        "add_dir": add_dirs[0] if add_dirs else None,
        "api_key_visible": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "home_skill": home_skill,
        "home_skill_name": home_skill_name,
        "invokes_model": False,
        "max_budget_usd": spend,
        "max_turns": turns,
        "model": model,
        "plugin_dir": plugin_dirs[0] if plugin_dirs else None,
        "plugin_name": plugin_name,
        "reference_applied": True,
        "result": "baseline-stub",
        "role": "baseline-stub",
        "seed": os.environ.get("AIC_BENCH_SEED", ""),
        "session_id": "baseline-stub",
        "skill_stand_in": skill_stand_in,
        "task_id": task_id,
        "total_cost_usd": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def main() -> int:
    if os.environ.get("AICBENCH_BASELINE_STUB") == "1":
        return _baseline_stub()
    if os.environ.get("AICBENCH_PIPELINE_SMOKE") != "1":
        return _refuse("refusing to run outside the aicbench harness. This is not a model.")
    if len(sys.argv) == 1:
        return _probe()
    if len(sys.argv) == 3 and sys.argv[1] == "tamper":
        return _tamper(Path(sys.argv[2]))
    return _refuse("usage is a probe with no arguments, or tamper PATH.")


if __name__ == "__main__":
    raise SystemExit(main())
