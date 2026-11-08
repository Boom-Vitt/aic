"""Generate SWE-bench Lite predictions and score them with the pinned harness.

``main`` returns exit 3 before creating directories, downloading data, or
starting a process when ``ANTHROPIC_API_KEY`` is missing or blank. A present
key still refuses to start when bubblewrap or the egress proxy is missing.
Claude receives the key only inside the agent phase.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from benchmarks.aicbench.grading import GradeError, outside_repository_temp
from benchmarks.baselines.adapter import AdapterError, load_registry, stage_shipped_plugin
from benchmarks.budget import format_max_usd
from benchmarks.suite_runtime import PROXY_REFUSAL, open_suite_runtime, runtime_root
from benchmarks.swe_bench.constants import (
    AIC_CONDITION,
    CHECKED_ON,
    DATASET_CARD_LICENSE_FIELD,
    DATASET_ID,
    DATASET_REVISION,
    HARNESS_COMMIT,
    HARNESS_LICENSE,
    HARNESS_REPOSITORY,
    MISSING_KEY_EXIT,
    MISSING_KEY_MESSAGE,
    REPO_ROOT,
)
from benchmarks.swe_bench.contract import (
    ContractError,
    api_key_present,
    assert_not_vendored,
    child_env,
    claude_command,
    conditions_for,
    dataset_export_command,
    final_exit,
    git_materialize_commands,
    git_patch_commands,
    help_requested,
    issue_prompt,
    lexical_absolute,
    missing_commands,
    official_count_line,
    open_nofollow,
    pip_install_command,
    prediction_record,
    prepare_output,
    redact,
    require_instance_id,
    reject_score_only_smoke,
    reject_symlink_ancestors,
    required_commands,
    score_command,
    select_instances,
    validate_test_split,
    venv_command,
)

_SIDECAR_LIMIT = 100_000


def run_official_arm(
    runtime,
    argv: list[str],
    *,
    key: str,
    workspace: Path,
    home: Path,
    config: Path,
    skill_root: Path | None,
    timeout: int,
    seed: int,
    launch=None,
):
    """Run one official arm in the agent phase.

    The API key is an environment value of that phase only. It is not a
    command argument, and the install phase never receives it.
    """
    if runtime is None:
        raise ContractError(PROXY_REFUSAL)
    if not argv or any("\x00" in part for part in argv):
        raise ContractError("Refusing to run an empty agent command.")
    if key and any(key in part for part in argv):
        raise ContractError("Refusing to put the API key on a command line.")
    for path in (workspace, home, config):
        path.mkdir(parents=True, exist_ok=True)
    return runtime.run(
        list(argv),
        phase="agent",
        key=key,
        workspace=workspace,
        home=home,
        config=config,
        skill_root=skill_root,
        timeout=timeout,
        seed=seed,
        launch=launch,
    )


def _outside_work(name: str) -> Path:
    try:
        parent = outside_repository_temp()
    except GradeError as exc:
        raise ContractError(str(exc)) from exc
    return Path(tempfile.mkdtemp(prefix=f"aic-swe-{name}-", dir=parent))


def parse_args(argv: list[str]) -> argparse.Namespace:
    budget = load_registry()["budget"]
    spend = format_max_usd(budget["max_usd"])
    parser = argparse.ArgumentParser(
        prog="python -m benchmarks.swe_bench",
        description=(
            "Generate SWE-bench Lite predictions with baseline Claude Code and "
            "Claude Code plus AIC, then score them with the pinned MIT harness."
        ),
    )
    parser.add_argument("--output", required=True, type=Path, help="Disposable directory. Created only after the API key and preflight checks.")
    parser.add_argument("--cache", type=Path, help="Reusable harness and dataset cache. Defaults to OUTPUT/cache.")
    parser.add_argument("--smoke", action="store_true", help="Score the lexicographic first 10 test instances.")
    parser.add_argument("--condition", choices=("both", "baseline", "aic"), default="both")
    parser.add_argument("--score-only", action="store_true", help="Score predictions.jsonl files already in the output directory.")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=budget["max_turns"])
    parser.add_argument("--instance-timeout", type=int, default=budget["timeout_sec"])
    parser.add_argument("--score-timeout", type=int, default=86400)
    parser.add_argument("--max-budget-usd", default=spend)
    parser.add_argument("--model", help="Claude Code model id. Omit to use the CLI default.")
    args = parser.parse_args(argv)
    if min(args.max_workers, args.max_turns, args.instance_timeout, args.score_timeout) < 1:
        parser.error("Worker, turn, and timeout limits must be positive integers.")
    if (
        args.max_turns != budget["max_turns"]
        or args.instance_timeout != budget["timeout_sec"]
        or args.max_budget_usd != spend
    ):
        parser.error("SWE-bench Lite must use the shared baseline budget. Official comparisons do not accept a null dollar cap.")
    try:
        conditions_for(args.condition)
        reject_score_only_smoke(args.score_only, args.smoke)
        if args.model is not None or args.max_budget_usd is not None:
            claude_command(
                prompt="check",
                plugin_dir=None,
                model=args.model,
                max_turns=args.max_turns,
                max_budget_usd=args.max_budget_usd,
            )
    except ContractError as exc:
        parser.error(str(exc))
    return args


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    environ = os.environ if env is None else env
    if not help_requested(arguments) and not api_key_present(environ):
        print(MISSING_KEY_MESSAGE, file=sys.stderr)
        return MISSING_KEY_EXIT
    args = parse_args(arguments)
    try:
        return execute_run(args, environ)
    except (ContractError, OSError) as exc:
        print(f"AIC swe-bench: {exc}", file=sys.stderr)
        return 2


def execute_run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    key = str(env.get("ANTHROPIC_API_KEY", "")).strip()
    if not key:
        print(MISSING_KEY_MESSAGE, file=sys.stderr)
        return MISSING_KEY_EXIT
    egress = None
    runtime = None
    try:
        egress = runtime_root()
        try:
            runtime = open_suite_runtime(dict(env), egress)
        except AdapterError as exc:
            print(str(exc), file=sys.stderr)
            return exc.code
        return _execute_with_runtime(args, env, key, runtime)
    finally:
        if runtime is not None:
            runtime.close()
        if egress is not None:
            shutil.rmtree(egress, ignore_errors=True)


def _execute_with_runtime(args: argparse.Namespace, env: Mapping[str, str], key: str, runtime) -> int:
    output = lexical_absolute(Path(args.output), Path.cwd())
    cache = lexical_absolute(Path(args.cache), Path.cwd()) if args.cache else output / "cache"
    assert_not_vendored(output, REPO_ROOT)
    assert_not_vendored(cache, REPO_ROOT)
    prepare_output(output, score_only=args.score_only)
    reject_symlink_ancestors(cache)
    if cache.is_symlink() or (cache.exists() and not cache.is_dir()):
        raise ContractError(f"Cache must be a real directory, not {cache}.")
    selected = conditions_for(args.condition)
    if AIC_CONDITION in selected:
        manifest = REPO_ROOT / ".claude-plugin" / "plugin.json"
        if not manifest.is_file() or manifest.is_symlink():
            raise ContractError("The AIC Claude Code plugin manifest is not a regular file.")
    absent = missing_commands(
        {name for name in required_commands(score_only=args.score_only) if shutil.which(name)},
        score_only=args.score_only,
    )
    if absent:
        print(
            "Missing required commands: "
            + ", ".join(absent)
            + ". No predictions or scores were recorded.",
            file=sys.stderr,
        )
        return 2
    with tempfile.TemporaryDirectory(prefix="aic-swe-preflight-") as temporary:
        preflight_home = Path(temporary)
        docker = run_command(
            ["docker", "info"],
            cwd=None,
            env=child_env(env, home=preflight_home, hf_home=preflight_home / "hf", api_key=None),
            timeout=60,
        )
    if docker.returncode != 0:
        print("Docker is not available. No predictions or scores were recorded.", file=sys.stderr)
        detail = redact(docker.stderr or "", key).strip()
        if detail:
            print(detail[-2000:], file=sys.stderr)
        return 2
    if not args.score_only:
        output.mkdir()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "home").mkdir(exist_ok=True)
    (cache / "hf-home").mkdir(exist_ok=True)
    harness_python = ensure_harness(cache, env, key)
    if args.score_only:
        return score_existing(args, env, key, output, cache, harness_python, selected)
    rows = load_public_split(cache, env, harness_python, key)
    chosen = select_instances(rows, smoke=args.smoke)
    metadata = base_metadata(args, chosen, selected)
    write_json(output / "run.json", metadata)
    failures = 0
    plugin_root = None
    metadata["status"] = "failed"
    code = 1
    try:
        if AIC_CONDITION in selected:
            plugin_root = Path(tempfile.mkdtemp(prefix="aic-swe-plugin-", dir=outside_repository_temp()))
            stage_shipped_plugin(plugin_root)
        for condition in selected:
            failures += generate_condition(
                condition,
                chosen,
                output,
                cache,
                env,
                key,
                runtime,
                plugin_dir=plugin_root if condition == AIC_CONDITION else None,
                model=args.model,
                max_turns=args.max_turns,
                max_budget_usd=args.max_budget_usd,
                timeout=args.instance_timeout,
            )
        codes = score_conditions(
            args,
            env,
            output,
            cache,
            harness_python,
            key,
            selected,
            [row["instance_id"] for row in chosen],
        )
        code = final_exit(failures, codes)
        metadata["status"] = "completed" if code == 0 else "failed"
        metadata["official_reports"] = report_index(output, selected)
        return code
    finally:
        if plugin_root is not None:
            shutil.rmtree(plugin_root, ignore_errors=True)
        write_json(output / "run.json", metadata)


def score_existing(
    args: argparse.Namespace,
    env: Mapping[str, str],
    key: str,
    output: Path,
    cache: Path,
    harness_python: Path,
    selected: tuple[str, ...],
) -> int:
    codes: list[int] = []
    for condition in selected:
        identifiers = prediction_identifiers(output / condition / "predictions.jsonl")
        codes.extend(
            score_conditions(args, env, output, cache, harness_python, key, (condition,), identifiers)
        )
    return final_exit(0, codes)


def base_metadata(args: argparse.Namespace, chosen: list[dict[str, str]], selected: tuple[str, ...]) -> dict[str, object]:
    return {
        "benchmark": "swe-bench-lite",
        "checked_on": CHECKED_ON,
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "dataset_split": "test",
        "dataset_card_license_field": DATASET_CARD_LICENSE_FIELD,
        "harness_repository": HARNESS_REPOSITORY,
        "harness_commit": HARNESS_COMMIT,
        "harness_license": HARNESS_LICENSE,
        "smoke": bool(args.smoke),
        "instance_ids": [row["instance_id"] for row in chosen],
        "conditions": list(selected),
        "status": "generating",
        "model_name_or_path_is": "arm label, not a reported resolve rate",
    }


def ensure_harness(cache: Path, env: Mapping[str, str], key: str) -> Path:
    venv = cache / "harness-venv"
    python = venv / "bin" / "python"
    marker = cache / "harness-commit.txt"
    if _marker_matches(marker, HARNESS_COMMIT) and python.is_file():
        return python
    if venv.exists() or venv.is_symlink():
        if venv.is_symlink():
            raise ContractError("Refusing to replace a symlinked harness virtualenv.")
        shutil.rmtree(venv)
    if marker.exists() or marker.is_symlink():
        if marker.is_symlink():
            raise ContractError("Refusing to replace a symlinked harness pin.")
        marker.unlink()
    home = cache / "home"
    install_env = child_env(env, home=home, hf_home=cache / "hf-home", api_key=None)
    created = run_command(venv_command(Path(sys.executable), venv), cwd=cache, env=install_env, timeout=180)
    if created.returncode != 0:
        _fail_process("Could not create the harness virtualenv.", created, key)
    installed = run_command(pip_install_command(python), cwd=cache, env=install_env, timeout=3600)
    if installed.returncode != 0:
        _fail_process("Could not install the pinned SWE-bench harness.", installed, key)
    write_text(marker, HARNESS_COMMIT + "\n")
    return python


def load_public_split(cache: Path, env: Mapping[str, str], python: Path, key: str) -> list[dict[str, str]]:
    dataset_file = cache / "swe-bench-lite-test.jsonl"
    revision_file = cache / "dataset-revision.txt"
    if _marker_matches(revision_file, DATASET_REVISION) and dataset_file.is_file() and not dataset_file.is_symlink():
        try:
            return _rows_from_jsonl(read_text(dataset_file))
        except ContractError:
            dataset_file.unlink()
            revision_file.unlink()
    exported = run_command(
        dataset_export_command(python),
        cwd=cache,
        env=child_env(env, home=cache / "home", hf_home=cache / "hf-home", api_key=None),
        timeout=1800,
    )
    if exported.returncode != 0:
        _fail_process("Could not download SWE-bench Lite.", exported, key)
    rows = _rows_from_jsonl(exported.stdout)
    write_text(dataset_file, exported.stdout)
    write_text(revision_file, DATASET_REVISION + "\n")
    return rows


def _rows_from_jsonl(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError("The dataset download was not JSONL.") from exc
        rows.append(value)
    return validate_test_split(rows)


def generate_condition(
    condition: str,
    chosen: list[dict[str, str]],
    output: Path,
    cache: Path,
    env: Mapping[str, str],
    key: str,
    runtime,
    *,
    plugin_dir: Path | None,
    model: str | None,
    max_turns: int,
    max_budget_usd: str | None,
    timeout: int,
) -> int:
    root = output / condition
    attempts = root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    predictions = root / "predictions.jsonl"
    work = _outside_work(condition)
    home = work / "home"
    config = work / "config"
    home.mkdir()
    config.mkdir()
    failures = 0
    try:
        for instance in chosen:
            destination = work / instance["instance_id"]
            destination.mkdir()
            try:
                cloned = _materialize(instance, destination, runtime, seed=load_registry()["seed"], key=key)
                if not cloned:
                    failures += 1
                    continue
                prompt = issue_prompt(instance["problem_statement"], use_aic=plugin_dir is not None)
                command = claude_command(
                    prompt=prompt,
                    plugin_dir=plugin_dir,
                    model=model,
                    max_turns=max_turns,
                    max_budget_usd=max_budget_usd,
                )
                timed_out = False
                try:
                    completed = run_official_arm(
                        runtime,
                        command,
                        key=key,
                        workspace=destination,
                        home=home,
                        config=config,
                        skill_root=plugin_dir,
                        timeout=timeout,
                        seed=load_registry()["seed"],
                    )
                    exit_code = completed.returncode
                    stdout = completed.stdout
                    stderr = completed.stderr
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    exit_code = 124
                    stdout = _text(exc.output)
                    stderr = _text(exc.stderr)
                    failures += 1
                patch = _working_tree_patch(destination, env)
                append_line(predictions, json.dumps(prediction_record(instance["instance_id"], patch, condition), ensure_ascii=False) + "\n")
                write_json(attempts / f"{instance['instance_id']}.json", {
                    "instance_id": instance["instance_id"],
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "stdout": redact(stdout, key)[:_SIDECAR_LIMIT],
                    "stderr": redact(stderr, key)[:_SIDECAR_LIMIT],
                })
                if not timed_out and exit_code != 0:
                    failures += 1
            finally:
                if destination.is_dir() and not destination.is_symlink() and destination.parent == work:
                    shutil.rmtree(destination)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return failures


def score_conditions(
    args: argparse.Namespace,
    env: Mapping[str, str],
    output: Path,
    cache: Path,
    python: Path,
    key: str,
    selected: tuple[str, ...],
    instance_ids: list[str],
) -> list[int]:
    codes = []
    for condition in selected:
        predictions = output / condition / "predictions.jsonl"
        if not predictions.is_file() or predictions.is_symlink():
            raise ContractError(f"Missing predictions for {condition}.")
        score_root = output / "scores" / condition
        home = score_root / "home"
        score_root.mkdir(parents=True, exist_ok=True)
        home.mkdir(exist_ok=True)
        command = score_command(python, predictions, condition, instance_ids, args.max_workers)
        completed = run_command(
            command,
            cwd=score_root,
            env=child_env(env, home=home, hf_home=cache / "hf-home", api_key=None),
            timeout=args.score_timeout,
        )
        codes.append(completed.returncode)
        report = score_root / "logs" / "evaluation" / condition / "results.json"
        print(f"Official harness report ({condition}): {report}", file=sys.stderr)
        if report.is_file() and not report.is_symlink():
            try:
                parsed = json.loads(read_text(report))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ContractError(f"Could not read the official report for {condition}.") from exc
            if isinstance(parsed, dict):
                line = official_count_line(parsed)
                if line:
                    print(line, file=sys.stderr)
        elif completed.returncode != 0:
            detail = redact(completed.stderr or completed.stdout or "", key).strip()
            if detail:
                print(detail[-4000:], file=sys.stderr)
    return codes


def prediction_identifiers(path: Path) -> list[str]:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"Missing predictions file {path}.")
    identifiers = []
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError("Predictions must be JSONL.") from exc
        if not isinstance(row, dict):
            raise ContractError("Each prediction must be a JSON object.")
        for field in ("instance_id", "model_patch", "model_name_or_path"):
            if not isinstance(row.get(field), str):
                raise ContractError(f"Prediction field {field} must be a string.")
        identifiers.append(require_instance_id(row["instance_id"]))
    if not identifiers:
        raise ContractError("The predictions file has no instances.")
    return identifiers


def report_index(output: Path, selected: tuple[str, ...]) -> dict[str, str]:
    index = {}
    for condition in selected:
        report = output / "scores" / condition / "logs" / "evaluation" / condition / "results.json"
        if report.is_file() and not report.is_symlink():
            index[condition] = str(report)
    return index


def _materialize(instance: dict[str, str], destination: Path, runtime, *, seed: int, key: str) -> bool:
    """Fetch the instance without the API key, through the install-phase proxy."""
    home = destination.parent / "install-home"
    config = destination.parent / "install-config"
    home.mkdir(exist_ok=True)
    config.mkdir(exist_ok=True)
    for command in git_materialize_commands(instance["repo"], instance["base_commit"], destination):
        completed = runtime.run(
            command,
            phase="install",
            key=None,
            workspace=destination.parent,
            home=home,
            config=config,
            skill_root=None,
            timeout=600,
            seed=seed,
        )
        if completed.returncode != 0:
            print(
                f"Could not check out {instance['instance_id']}. No prediction was recorded for it.",
                file=sys.stderr,
            )
            detail = redact(completed.stderr or "", key).strip()
            if detail:
                print(detail[-2000:], file=sys.stderr)
            return False
    return True


def _working_tree_patch(destination: Path, env: Mapping[str, str]) -> str:
    tool_env = child_env(env, home=destination.parent, hf_home=destination.parent, api_key=None)
    add, diff = git_patch_commands(destination)
    added = run_command(add, cwd=destination, env=tool_env, timeout=120)
    if added.returncode != 0:
        return ""
    compared = run_command(diff, cwd=destination, env=tool_env, timeout=120)
    if compared.returncode != 0:
        return ""
    return compared.stdout if compared.stdout.strip() else ""


def _marker_matches(path: Path, expected: str) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    return read_text(path).strip() == expected


def _fail_process(message: str, completed: subprocess.CompletedProcess[str], key: str) -> None:
    detail = redact((completed.stderr or completed.stdout or ""), key).strip()
    text = message if not detail else f"{message}\n{detail[-4000:]}"
    raise ContractError(text)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def run_command(
    argv: list[str],
    *,
    cwd: Path | None,
    env: Mapping[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    if not argv or any("\x00" in part for part in argv):
        raise ContractError("Refusing to run an empty or NUL-containing command.")
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
        shell=False,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(process.pid)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
    if process.returncode is None:
        raise ContractError("The child process ended without a status.")
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def read_text(path: Path) -> str:
    fd = open_nofollow(path, append=False)
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    if path.is_symlink():
        raise ContractError(f"Refusing to follow symlink {path}.")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def append_line(path: Path, text: str) -> None:
    fd = open_nofollow(path, append=True)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
