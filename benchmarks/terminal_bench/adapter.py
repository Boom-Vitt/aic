#!/usr/bin/env python3
"""Run pinned Terminal-Bench on plain Claude Code and Claude Code with AIC.

This adapter does not vendor Terminal-Bench or Harbor. It invokes the pinned
Harbor commit, which checks out the pinned Terminal-Bench tree. A missing
model credential stops before any job directory or receipt is created.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = Path(__file__).resolve().parent / "pins.json"
DEFAULT_JOBS = REPO_ROOT / ".work" / "terminal-bench" / "jobs"
SCHEMA = "aic.terminal-bench.receipt"
SCHEMA_VERSION = 1
MISSING_CREDENTIAL_EXIT = 3
MISSING_CREDENTIAL_MESSAGE = (
    "ANTHROPIC_API_KEY is unset or blank. "
    "Terminal-Bench was not started and no receipt was written."
)
CONFIGURATIONS = ("baseline", "aic")
PASS_REWARD = 1
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_CONCURRENT = 100


class AdapterFailure(Exception):
    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


def load_pins(path: Path = PIN_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AdapterFailure("Pin file must be a JSON object.")
    for name in ("terminal_bench", "harbor"):
        pin = data.get(name)
        if not isinstance(pin, dict):
            raise AdapterFailure(f"Pin file is missing {name}.")
        commit = pin.get("commit")
        if not _full_sha(commit):
            raise AdapterFailure(f"{name} commit is not a full SHA.")
        if pin.get("license") != "Apache-2.0":
            raise AdapterFailure(f"{name} pin is not Apache-2.0.")
    tasks_path = data["terminal_bench"].get("tasks_path")
    if tasks_path != "tasks":
        raise AdapterFailure("Terminal-Bench tasks path is not the pinned tasks directory.")
    return data


def credential_present(env: Mapping[str, str]) -> bool:
    value = env.get("ANTHROPIC_API_KEY")
    return isinstance(value, str) and value.strip() != ""


def _full_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def _token(value: str, *, allow_slash: bool) -> bool:
    if not value or value.startswith("-") or any(character.isspace() for character in value):
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:@+-")
    if allow_slash:
        allowed.add("/")
    return len(value) <= 200 and all(character in allowed for character in value)


def argument_problems(args: argparse.Namespace) -> str | None:
    if args.output is None:
        return "A run requires --output."
    if not isinstance(args.model, str) or not _token(args.model, allow_slash=True):
        return "Model id must be one token, such as provider/model."
    task_ids = args.task_ids or []
    if not task_ids:
        return "A run requires at least one --task-id."
    seen_tasks: set[str] = set()
    for task_id in task_ids:
        if not isinstance(task_id, str) or not _token(task_id, allow_slash=False):
            return f"Task id is not a single Terminal-Bench directory name: {task_id!r}."
        if task_id in seen_tasks:
            return f"Task id is repeated: {task_id}."
        seen_tasks.add(task_id)
    seeds = args.seeds or []
    if not seeds:
        return "A run requires at least one --seed."
    seen_seeds: set[int] = set()
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 or seed > 2_147_483_647:
            return "Each seed must be an integer from 0 through 2147483647."
        if seed in seen_seeds:
            return f"Seed is repeated: {seed}."
        seen_seeds.add(seed)
    if not isinstance(args.sandbox, str) or not _token(args.sandbox, allow_slash=False):
        return "Sandbox name must be one Harbor environment token."
    concurrent = args.n_concurrent
    if isinstance(concurrent, bool) or not isinstance(concurrent, int) or not 1 <= concurrent <= MAX_CONCURRENT:
        return f"Concurrency must be an integer from 1 through {MAX_CONCURRENT}."
    return None


def parse_trial(result: dict) -> dict:
    task_id = result.get("task_name")
    if not isinstance(task_id, str) or not task_id:
        raise AdapterFailure("A trial result is missing task_name.")
    exception = result.get("exception_info")
    error: str | None = None
    if exception is not None:
        kind = exception.get("exception_type") if isinstance(exception, dict) else None
        error = kind if isinstance(kind, str) and kind and len(kind) <= 200 else "exception"
    reward: int | float | None = None
    verifier = result.get("verifier_result")
    rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
    if isinstance(rewards, dict) and "reward" in rewards:
        raw = rewards["reward"]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            reward = None
        elif isinstance(raw, float) and not math.isfinite(raw):
            reward = None
        else:
            reward = raw
    passed = error is None and reward is not None and reward >= PASS_REWARD
    return {"task_id": task_id, "passed": passed, "reward": reward, "error": error}


def trials_from_job(job_dir: Path) -> list[dict]:
    if not job_dir.is_dir() or job_dir.is_symlink():
        raise AdapterFailure(f"Harbor job directory is missing: {job_dir.name}.")
    parsed: list[dict] = []
    for child in sorted(job_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.is_symlink() or child.name.startswith("."):
            continue
        result_path = child / "result.json"
        if not result_path.is_file() or result_path.is_symlink():
            continue
        if result_path.stat().st_size > MAX_RESULT_BYTES:
            raise AdapterFailure(f"Trial result is larger than {MAX_RESULT_BYTES} bytes.")
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AdapterFailure(f"Trial result is not UTF-8 JSON: {child.name}.") from exc
        if not isinstance(data, dict):
            raise AdapterFailure(f"Trial result is not an object: {child.name}.")
        parsed.append(parse_trial(data))
    return parsed


def select_trials(parsed: Sequence[dict], task_ids: Sequence[str]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for item in parsed:
        task_id = item["task_id"]
        if task_id in by_id:
            raise AdapterFailure(f"Harbor returned more than one trial for {task_id}.")
        by_id[task_id] = item
    missing = [task_id for task_id in task_ids if task_id not in by_id]
    extra = sorted(set(by_id) - set(task_ids))
    if missing or extra:
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        raise AdapterFailure("Harbor trials do not match the requested task ids: " + "; ".join(detail) + ".")
    return [by_id[task_id] for task_id in task_ids]


def build_receipt(
    *,
    model_id: str,
    pins: dict,
    aic_commit: str,
    aic_worktree_dirty: bool,
    task_ids: Sequence[str],
    seeds: Sequence[int],
    sandbox: str,
    n_concurrent: int,
    harbor_invocation: str,
    trials: Sequence[dict],
) -> dict:
    grouped: dict[str, list[dict]] = {name: [] for name in CONFIGURATIONS}
    for trial in trials:
        configuration = trial["configuration"]
        if configuration not in grouped:
            raise AdapterFailure(f"Unknown configuration {configuration}.")
        grouped[configuration].append(
            {
                "task_id": trial["task_id"],
                "seed": trial["seed"],
                "passed": trial["passed"],
                "reward": trial["reward"],
                "error": trial["error"],
                "job_name": trial["job_name"],
            }
        )
    receipt = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "sandbox": sandbox,
        "n_concurrent": n_concurrent,
        "task_ids": list(task_ids),
        "seeds": list(seeds),
        "pins": {
            "terminal_bench": {
                "repository": pins["terminal_bench"]["repository"],
                "commit": pins["terminal_bench"]["commit"],
                "license": pins["terminal_bench"]["license"],
                "tasks_path": pins["terminal_bench"]["tasks_path"],
            },
            "harbor": {
                "repository": pins["harbor"]["repository"],
                "commit": pins["harbor"]["commit"],
                "license": pins["harbor"]["license"],
                "invocation": harbor_invocation,
            },
            "aic": {
                "repository": "https://github.com/Boom-Vitt/aic",
                "commit": aic_commit,
                "worktree_dirty": aic_worktree_dirty,
            },
        },
        "configurations": {
            "baseline": {
                "agent": "claude-code",
                "plugin": None,
                "skills": [],
                "trials": grouped["baseline"],
            },
            "aic": {
                "agent": "claude-code",
                "plugin": {
                    "name": "aic",
                    "origin": "skills-dir",
                    "manifest": ".claude-plugin/plugin.json",
                },
                "skills": ["aic"],
                "trials": grouped["aic"],
            },
        },
    }
    problems = validate_receipt(receipt)
    if problems:
        raise AdapterFailure("Built receipt is invalid: " + "; ".join(problems) + ".")
    return receipt


def validate_receipt(data: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["Receipt is not a JSON object."]
    if data.get("schema") != SCHEMA:
        problems.append("Receipt schema is not aic.terminal-bench.receipt.")
    if data.get("schema_version") != SCHEMA_VERSION:
        problems.append("Receipt schema_version is not 1.")
    model_id = data.get("model_id")
    if not isinstance(model_id, str) or not _token(model_id, allow_slash=True):
        problems.append("Receipt model_id is missing.")
    task_ids = data.get("task_ids")
    seeds = data.get("seeds")
    if not isinstance(task_ids, list) or not task_ids or not all(isinstance(item, str) for item in task_ids):
        problems.append("Receipt task_ids must be a non-empty list of strings.")
        task_ids = []
    if not isinstance(seeds, list) or not seeds or not all(isinstance(item, int) and not isinstance(item, bool) for item in seeds):
        problems.append("Receipt seeds must be a non-empty list of integers.")
        seeds = []
    pins = data.get("pins")
    if not isinstance(pins, dict):
        problems.append("Receipt pins are missing.")
    else:
        for name in ("terminal_bench", "harbor", "aic"):
            pin = pins.get(name)
            if not isinstance(pin, dict) or not _full_sha(pin.get("commit")):
                problems.append(f"Receipt is missing a full {name} commit.")
        harbor = pins.get("harbor")
        if isinstance(harbor, dict) and harbor.get("invocation") not in ("pinned-uvx", "override"):
            problems.append("Receipt harbor invocation is not pinned-uvx or override.")
        bench = pins.get("terminal_bench")
        if isinstance(bench, dict) and bench.get("license") != "Apache-2.0":
            problems.append("Receipt Terminal-Bench license is not Apache-2.0.")
    configurations = data.get("configurations")
    if not isinstance(configurations, dict):
        problems.append("Receipt configurations are missing.")
        return problems
    expected = {(task_id, seed) for task_id in task_ids for seed in seeds}
    for name in CONFIGURATIONS:
        configuration = configurations.get(name)
        if not isinstance(configuration, dict):
            problems.append(f"Receipt is missing the {name} configuration.")
            continue
        if configuration.get("agent") != "claude-code":
            problems.append(f"{name} agent is not claude-code.")
        skills = configuration.get("skills")
        plugin = configuration.get("plugin")
        if name == "baseline":
            if skills != [] or plugin is not None:
                problems.append("Baseline must not include the AIC plugin or skill.")
        elif skills != ["aic"] or not isinstance(plugin, dict) or plugin.get("name") != "aic":
            problems.append("AIC configuration must record the aic plugin and skill.")
        trials = configuration.get("trials")
        if not isinstance(trials, list):
            problems.append(f"{name} trials are missing.")
            continue
        seen: set[tuple[str, int]] = set()
        for trial in trials:
            if not isinstance(trial, dict) or not isinstance(trial.get("passed"), bool):
                problems.append(f"{name} has a trial without a boolean pass/fail.")
                continue
            key = (trial.get("task_id"), trial.get("seed"))
            if key in seen:
                problems.append(f"{name} repeats task {key[0]} seed {key[1]}.")
            seen.add(key)
            reward = trial.get("reward")
            error = trial.get("error")
            if reward is not None and (isinstance(reward, bool) or not isinstance(reward, (int, float))):
                problems.append(f"{name} trial reward is not a number or null.")
                continue
            passing_reward = (
                error is None
                and isinstance(reward, (int, float))
                and not isinstance(reward, bool)
                and reward >= PASS_REWARD
            )
            if trial.get("passed") is not passing_reward:
                problems.append(f"{name} pass/fail does not match the reward and error.")
        if seen != expected:
            problems.append(f"{name} trials do not cover every task id and seed.")
    return problems


def _reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise AdapterFailure(f"Refusing to follow a symlink: {path.name}.")


def copy_tree(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise AdapterFailure(f"Refusing to copy {source.name}: it is not a real directory.")
    destination.mkdir(parents=True)
    for directory, dirnames, filenames in os.walk(source, followlinks=False):
        current = Path(directory)
        kept: list[str] = []
        for name in dirnames:
            child = current / name
            _reject_symlink(child)
            kept.append(name)
        dirnames[:] = kept
        target = destination / current.relative_to(source)
        target.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            child = current / name
            _reject_symlink(child)
            if not child.is_file():
                raise AdapterFailure(f"Refusing to copy a non-file: {name}.")
            shutil.copyfile(child, target / name)


def stage_plugin_and_skill(repo: Path, destination: Path) -> Path:
    """Build the directory Harbor uploads for the AIC configuration.

    The directory is the portable skill plus the native plugin manifest, with
    the same skill nested at skills/aic so Claude Code's plugin skill root
    resolves. Harbor's Claude Code agent copies this directory into
    $CLAUDE_CONFIG_DIR/skills, which is that client's skills-directory origin.
    """
    skill_source = repo / "skills" / "aic"
    manifest = repo / ".claude-plugin" / "plugin.json"
    _reject_symlink(skill_source)
    _reject_symlink(manifest)
    if not (skill_source / "SKILL.md").is_file():
        raise AdapterFailure("The AIC skill is missing SKILL.md.")
    try:
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterFailure("The AIC plugin manifest is not UTF-8 JSON.") from exc
    if not isinstance(manifest_data, dict) or manifest_data.get("name") != "aic":
        raise AdapterFailure("The AIC plugin manifest name is not aic.")
    skill_destination = destination / "aic"
    copy_tree(skill_source, skill_destination)
    plugin_dir = skill_destination / ".claude-plugin"
    plugin_dir.mkdir()
    shutil.copyfile(manifest, plugin_dir / "plugin.json")
    copy_tree(skill_source, skill_destination / "skills" / "aic")
    return skill_destination


def aic_commit(repo: Path) -> tuple[str, bool]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    commit = head.stdout.strip()
    if head.returncode != 0 or not _full_sha(commit):
        raise AdapterFailure("Cannot read a full AIC git commit.")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise AdapterFailure("Cannot read the AIC worktree status.")
    return commit, bool(status.stdout.strip())


def job_name(configuration: str, seed: int) -> str:
    return f"{configuration}-seed-{seed}"


def harbor_launch(env: Mapping[str, str], pins: dict) -> tuple[list[str], str]:
    override = env.get("AIC_TERMINAL_BENCH_HARBOR", "").strip()
    commit = pins["harbor"]["commit"]
    if override:
        path = Path(override)
        if path.is_symlink() or not path.is_file():
            raise AdapterFailure("AIC_TERMINAL_BENCH_HARBOR is not a real executable file.")
        return [str(path)], "override"
    uvx = shutil.which("uvx", path=env.get("PATH"))
    if uvx is None:
        raise AdapterFailure("uvx was not found. It is required to run the pinned Harbor commit.")
    return [
        uvx,
        "--from",
        f"git+https://github.com/harbor-framework/harbor.git@{commit}",
        "harbor",
    ], "pinned-uvx"


def harbor_run_command(
    launch: Sequence[str],
    *,
    pins: dict,
    model_id: str,
    task_ids: Sequence[str],
    jobs_dir: Path,
    name: str,
    sandbox: str,
    n_concurrent: int,
    skill: Path | None,
) -> list[str]:
    repository = pins["terminal_bench"]["repository"].removesuffix(".git")
    prefix = "https://github.com/"
    if not repository.startswith(prefix):
        raise AdapterFailure("Terminal-Bench repository pin is not a GitHub URL.")
    repo = repository[len(prefix):] + "@" + pins["terminal_bench"]["commit"]
    command = [
        *launch,
        "run",
        "--repo",
        repo,
        "--path",
        pins["terminal_bench"]["tasks_path"],
        "--agent",
        "claude-code",
        "--model",
        model_id,
        "--env",
        sandbox,
        "--jobs-dir",
        str(jobs_dir),
        "--job-name",
        name,
        "--n-attempts",
        "1",
        "--n-concurrent",
        str(n_concurrent),
        "--yes",
    ]
    for task_id in task_ids:
        command.extend(["--include-task-name", task_id])
    if skill is not None:
        command.extend(["--skill", str(skill)])
    return command


def _refuse_existing(path: Path, label: str) -> None:
    if path.is_symlink() or path.exists():
        raise AdapterFailure(f"Refusing to overwrite {label}: {path}.")


def write_receipt(path: Path, receipt: dict) -> None:
    _refuse_existing(path, "the receipt")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    if partial.is_symlink():
        raise AdapterFailure("Refusing to write the receipt through a symlink.")
    try:
        partial.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(partial, path)
    except OSError as exc:
        raise AdapterFailure("The receipt could not be written.") from exc


def execute(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    output = Path(args.output)
    jobs_dir = Path(args.jobs_dir)
    _refuse_existing(output, "the receipt")
    if jobs_dir.is_symlink() or (jobs_dir.exists() and not jobs_dir.is_dir()):
        raise AdapterFailure("Jobs path is not a directory.")
    names = [job_name(configuration, seed) for seed in args.seeds for configuration in CONFIGURATIONS]
    for name in names:
        _refuse_existing(jobs_dir / name, "a Harbor job directory")
    _refuse_existing(jobs_dir / "aic-surface", "the AIC staging directory")
    pins = load_pins()
    launch, invocation = harbor_launch(env, pins)
    commit, dirty = aic_commit(REPO_ROOT)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    skill = stage_plugin_and_skill(REPO_ROOT, jobs_dir / "aic-surface")
    collected: list[dict] = []
    for seed in args.seeds:
        for configuration in CONFIGURATIONS:
            name = job_name(configuration, seed)
            command = harbor_run_command(
                launch,
                pins=pins,
                model_id=args.model,
                task_ids=args.task_ids,
                jobs_dir=jobs_dir,
                name=name,
                sandbox=args.sandbox,
                n_concurrent=args.n_concurrent,
                skill=skill if configuration == "aic" else None,
            )
            print(f"Terminal-Bench adapter: starting {name}.", file=sys.stderr, flush=True)
            try:
                completed = subprocess.run(command, env=dict(env), check=False)
            except OSError as exc:
                raise AdapterFailure("The Harbor launcher could not be started.") from exc
            try:
                selected = select_trials(trials_from_job(jobs_dir / name), args.task_ids)
            except AdapterFailure:
                if completed.returncode != 0:
                    raise AdapterFailure(
                        f"Harbor exited {completed.returncode} for {name} before every requested trial was recorded. No receipt was written.",
                        code=1,
                    ) from None
                raise
            for trial in selected:
                collected.append({**trial, "configuration": configuration, "seed": seed, "job_name": name})
    receipt = build_receipt(
        model_id=args.model,
        pins=pins,
        aic_commit=commit,
        aic_worktree_dirty=dirty,
        task_ids=args.task_ids,
        seeds=args.seeds,
        sandbox=args.sandbox,
        n_concurrent=args.n_concurrent,
        harbor_invocation=invocation,
        trials=collected,
    )
    write_receipt(output, receipt)
    print(f"Terminal-Bench adapter: wrote {output}.", file=sys.stderr)
    return 0


def validate_command(path: Path) -> int:
    if path.is_symlink() or not path.is_file():
        raise AdapterFailure("Receipt path is not a real file.")
    if path.stat().st_size > MAX_RESULT_BYTES:
        raise AdapterFailure("Receipt is too large to validate.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterFailure("Receipt is not UTF-8 JSON.") from exc
    problems = validate_receipt(data)
    if problems:
        print("Terminal-Bench adapter: " + "; ".join(problems), file=sys.stderr)
        return 2
    print("Terminal-Bench adapter: receipt schema is valid.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run pinned Terminal-Bench on plain Claude Code and on Claude Code "
            "with the AIC plugin and skill. Writes one JSON receipt."
        )
    )
    parser.add_argument("--model", help="Claude model id passed to Harbor, such as provider/model.")
    parser.add_argument("--task-id", action="append", dest="task_ids", help="Terminal-Bench task directory name. Repeatable.")
    parser.add_argument("--seed", action="append", type=int, dest="seeds", help="Paired repetition id. Repeatable. Not an API sampling seed.")
    parser.add_argument("--output", type=Path, help="Receipt JSON path. Refused if it already exists.")
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS, help="Directory for Harbor job folders.")
    parser.add_argument("--sandbox", default="docker", help="Harbor environment name. Default: docker.")
    parser.add_argument("--n-concurrent", type=int, default=1, help=f"Harbor trial concurrency from 1 through {MAX_CONCURRENT}.")
    parser.add_argument("--validate-receipt", type=Path, help="Validate an existing receipt and do not start a run.")
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    environment = os.environ if env is None else env
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.validate_receipt is not None:
            return validate_command(args.validate_receipt)
        problem = argument_problems(args)
        if problem:
            print(f"Terminal-Bench adapter: {problem}", file=sys.stderr)
            return 2
        if not credential_present(environment):
            print(MISSING_CREDENTIAL_MESSAGE, file=sys.stderr)
            return MISSING_CREDENTIAL_EXIT
        return execute(args, environment)
    except AdapterFailure as exc:
        print(f"Terminal-Bench adapter: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
