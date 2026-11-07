"""Compare baseline Claude Code with Claude Code plus the installed AIC skill.

The runner shells out to the `claude` executable. It records pass@1, reported
tokens, reported cost, and measured wall time. Without ANTHROPIC_API_KEY it
exits 3 and does not start a model. Cost is copied from Claude Code's
`total_cost_usd` field; this module does not apply a price table.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from . import SCHEMA_VERSION
from .catalog import CatalogError, Task, load_catalog
from .grading import GradeError, grade, prepare_workspace
from .metrics import cost_from_payload, cost_text, mean, pass_at_k, sum_cost, sum_usage, usage_from_payload

EXIT_USAGE = 2
EXIT_NO_KEY = 3
ARMS = ("baseline", "claude_code_plus_aic")
APPROVAL = (
    "This task is already approved. Change only files inside the current workspace. "
    "Do not search outside it for tests, answers, or graders. "
    "Stop when the acceptance criteria in the task are met."
)
AIC_PREFACE = (
    "An AIC skill is installed for this session. Read .claude/skills/aic/SKILL.md in the "
    "additional directory and follow it: inspect this workspace before editing, choose a "
    "workflow family, stay inside the approved scope, and check the acceptance criteria "
    "before stopping. The approval in this prompt covers edits in the current workspace only."
)


class RunnerError(RuntimeError):
    """The comparison could not be executed as a measurement."""


@dataclass(frozen=True)
class Trial:
    passed: bool
    grade_passed: bool
    timed_out: bool
    returncode: int | None
    wall_time_seconds: float
    tokens: dict[str, int | None] | None
    cost_usd: str | None
    session_id: str | None
    harness_error: str | None
    grade_detail: str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aicbench",
        description="Grade Claude Code against aicbench, with and without the AIC skill.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path.")
    parser.add_argument("--tasks", help="Comma-separated task ids. Default: the full catalog.")
    parser.add_argument("--samples", type=int, default=1, help="Independent samples per task per arm (1-10).")
    parser.add_argument("--max-turns", type=int, default=30, help="Claude Code --max-turns value (1-100).")
    parser.add_argument("--agent-timeout", type=int, default=600, help="Seconds allowed for one Claude Code process.")
    parser.add_argument("--model", help="Optional model id forwarded to Claude Code. Omit to use Claude Code's default.")
    parser.add_argument("--claude-bin", default="claude", help="Claude Code executable. Default: claude on PATH.")
    parser.add_argument("--arm", choices=ARMS, action="append", dest="arms", help="Run one arm. Repeatable. Default: both.")
    return parser


def _api_key(environ: dict[str, str]) -> str | None:
    key = environ.get("ANTHROPIC_API_KEY", "")
    if not key.strip():
        return None
    return key


def _select(tasks: tuple[Task, ...], requested: str | None) -> tuple[Task, ...]:
    if not requested:
        return tasks
    wanted = [part.strip() for part in requested.split(",") if part.strip()]
    if not wanted or any("," in part for part in wanted):
        raise RunnerError(" --tasks needs comma-separated task ids.")
    by_id = {task.id: task for task in tasks}
    missing = [task_id for task_id in wanted if task_id not in by_id]
    if missing:
        raise RunnerError("Unknown task id: " + ", ".join(missing))
    return tuple(by_id[task_id] for task_id in wanted)


def _prompt(task: Task, arm: str) -> str:
    body = f"Task id: {task.id}\n\n{task.instruction}\n{APPROVAL}\n"
    if arm == "baseline":
        return body
    return f"{AIC_PREFACE}\n\n{body}"


def _command(binary: str, prompt: str, *, max_turns: int, model: str | None, skill_root: Path | None) -> list[str]:
    command = [
        binary,
        "--bare",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
        "--permission-prompts",
        "none",
        "--allowedTools",
        "Read,Edit,Write,Bash",
        "--max-turns",
        str(max_turns),
        "--no-session-persistence",
    ]
    if model:
        command.extend(["--model", model])
    if skill_root is not None:
        command.extend(["--add-dir", str(skill_root)])
    return command


def _child_env(parent: dict[str, str], *, key: str, home: Path, config: Path) -> dict[str, str]:
    env = {
        "PATH": parent.get("PATH", ""),
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(config),
        "ANTHROPIC_API_KEY": key,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": parent.get("LANG", "C.UTF-8"),
        "LC_ALL": parent.get("LC_ALL", "C.UTF-8"),
    }
    for name in ("TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR", "SYSTEMROOT"):
        if parent.get(name):
            env[name] = parent[name]
    for name, value in parent.items():
        if name.startswith("AICBENCH_") and name not in env:
            env[name] = value
    return env


def _parse_claude(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if not candidate.startswith("{"):
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            break
        if payload is None:
            return {}
    return payload if isinstance(payload, dict) else {}


def _install_aic(project: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "aic.py"
    completed = subprocess.run(
        [sys.executable, "-B", str(script), "install", "--agent", "claude-code", "--scope", "project", "--project", str(project)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    skill = project / ".claude" / "skills" / "aic" / "SKILL.md"
    if completed.returncode != 0 or not skill.is_file():
        detail = (completed.stderr or completed.stdout or "AIC install failed.").strip()
        raise RunnerError(detail[:1000])


def _run_trial(
    task: Task,
    arm: str,
    *,
    binary: str,
    key: str,
    parent_env: dict[str, str],
    max_turns: int,
    model: str | None,
    agent_timeout: int,
    skill_root: Path | None,
    home: Path,
    config: Path,
) -> Trial:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"aicbench-{task.id}-") as temporary:
        workspace = Path(temporary) / "workspace"
        try:
            prepare_workspace(task, workspace, solution=False)
        except GradeError as exc:
            elapsed = round(time.perf_counter() - started, 6)
            return Trial(False, False, False, None, elapsed, None, None, None, str(exc), "")
        command = _command(_prompt_binary(binary), _prompt(task, arm), max_turns=max_turns, model=model, skill_root=skill_root if arm == "claude_code_plus_aic" else None)
        timed_out = False
        stdout = ""
        returncode: int | None = None
        harness_error = None
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=_child_env(parent_env, key=key, home=home, config=config),
                capture_output=True,
                text=True,
                timeout=agent_timeout,
                check=False,
            )
            stdout = completed.stdout or ""
            returncode = completed.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            harness_error = "agent timeout"
        except OSError as exc:
            harness_error = str(exc)
        elapsed = round(time.perf_counter() - started, 6)
        payload = _parse_claude(stdout)
        try:
            result = grade(task, workspace)
        except GradeError as exc:
            return Trial(False, False, timed_out, returncode, elapsed, usage_from_payload(payload), cost_text(cost_from_payload(payload)), _session(payload), str(exc), "")
        passed = result.passed and not timed_out and harness_error is None
        return Trial(
            passed,
            result.passed,
            timed_out,
            returncode,
            elapsed,
            usage_from_payload(payload),
            cost_text(cost_from_payload(payload)),
            _session(payload),
            harness_error,
            result.detail[-500:],
        )


def _prompt_binary(binary: str) -> str:
    path = Path(binary)
    if path.is_file():
        return str(path)
    found = shutil.which(binary)
    if not found:
        raise RunnerError(f"Claude Code executable was not found: {binary}")
    return found


def _session(payload: dict) -> str | None:
    value = payload.get("session_id")
    if isinstance(value, str) and value:
        return value
    return None


def _trial_record(trial: Trial) -> dict:
    return {
        "passed": trial.passed,
        "grade_passed": trial.grade_passed,
        "timed_out": trial.timed_out,
        "returncode": trial.returncode,
        "wall_time_seconds": trial.wall_time_seconds,
        "tokens": trial.tokens,
        "cost_usd": trial.cost_usd,
        "session_id": trial.session_id,
        "harness_error": trial.harness_error,
        "detail": None if trial.passed else trial.grade_detail,
    }


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def _task_arm(samples: list[Trial]) -> dict:
    correct = sum(1 for trial in samples if trial.passed)
    return {
        "passed": correct == len(samples) and bool(samples),
        "pass_at_1": pass_at_k(len(samples), correct, 1),
        "tokens": sum_usage([trial.tokens for trial in samples]),
        "cost_usd": sum_cost([_decimal(trial.cost_usd) for trial in samples]),
        "wall_time_seconds": round(sum(trial.wall_time_seconds for trial in samples), 6),
        "samples": [_trial_record(trial) for trial in samples],
    }


def _suite_arm(task_records: list[dict]) -> dict:
    estimates = [record["pass_at_1"] for record in task_records]
    sample_tokens = []
    sample_costs = []
    wall = 0.0
    sample_count = 0
    for record in task_records:
        for sample in record["samples"]:
            sample_count += 1
            sample_tokens.append(sample["tokens"])
            sample_costs.append(_decimal(sample["cost_usd"]))
            wall += sample["wall_time_seconds"]
    return {
        "pass_at_1": mean(estimates),
        "tasks": len(task_records),
        "tasks_passed": sum(1 for record in task_records if record["pass_at_1"] == 1.0),
        "samples": sample_count,
        "tokens": sum_usage(sample_tokens),
        "cost_usd": sum_cost(sample_costs),
        "wall_time_seconds": round(wall, 6),
    }


def build_report(selected: tuple[Task, ...], arms: tuple[str, ...], results: dict[str, dict[str, list[Trial]]], *, samples: int) -> dict:
    tasks = []
    per_arm: dict[str, list[dict]] = {arm: [] for arm in arms}
    for task in selected:
        entry = {"id": task.id, "title": task.title, "category": task.category}
        for arm in arms:
            record = _task_arm(results[arm][task.id])
            entry[arm] = record
            per_arm[arm].append(record)
        tasks.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "aicbench",
        "samples_per_task": samples,
        "measured": True,
        "arms": {arm: _suite_arm(per_arm[arm]) for arm in arms},
        "tasks": tasks,
    }


def run_comparison(args: argparse.Namespace, environ: dict[str, str]) -> dict:
    if not 1 <= args.samples <= 10:
        raise RunnerError("--samples must be from 1 to 10.")
    if not 1 <= args.max_turns <= 100:
        raise RunnerError("--max-turns must be from 1 to 100.")
    if not 1 <= args.agent_timeout <= 7200:
        raise RunnerError("--agent-timeout must be from 1 to 7200 seconds.")
    key = _api_key(environ)
    if key is None:
        raise SystemExit(EXIT_NO_KEY)
    binary = _prompt_binary(args.claude_bin)
    catalog = load_catalog()
    selected = _select(catalog, args.tasks)
    arms = tuple(args.arms) if args.arms else ARMS
    with tempfile.TemporaryDirectory(prefix="aicbench-run-") as temporary:
        root = Path(temporary)
        home = root / "home"
        config = root / "claude-config"
        home.mkdir()
        config.mkdir()
        skill_root = None
        if "claude_code_plus_aic" in arms:
            skill_root = root / "aic-skill-project"
            skill_root.mkdir()
            _install_aic(skill_root)
        results: dict[str, dict[str, list[Trial]]] = {arm: {task.id: [] for task in selected} for arm in arms}
        for task in selected:
            for _sample in range(args.samples):
                for arm in arms:
                    trial = _run_trial(
                        task,
                        arm,
                        binary=binary,
                        key=key,
                        parent_env=environ,
                        max_turns=args.max_turns,
                        model=args.model,
                        agent_timeout=args.agent_timeout,
                        skill_root=skill_root,
                        home=home,
                        config=config,
                    )
                    results[arm][task.id].append(trial)
        return build_report(selected, arms, results, samples=args.samples)


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return EXIT_USAGE if code is None else int(code)
    parent = os.environ if environ is None else environ
    try:
        if _api_key(parent) is None:
            print("aicbench: ANTHROPIC_API_KEY is missing. No model was started.", file=sys.stderr)
            return EXIT_NO_KEY
        report = run_comparison(args, parent)
    except SystemExit as exc:
        if exc.code == EXIT_NO_KEY:
            print("aicbench: ANTHROPIC_API_KEY is missing. No model was started.", file=sys.stderr)
            return EXIT_NO_KEY
        raise
    except (RunnerError, CatalogError, GradeError, OSError) as exc:
        print(f"aicbench: {exc}", file=sys.stderr)
        return EXIT_USAGE
    text = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"aicbench: wrote {args.output}", file=sys.stderr)
    else:
        print(text, end="")
    return 0
