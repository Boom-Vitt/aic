"""Run plain Claude Code, AIC, and pinned workflow repositories as one comparison.

A live run fetches each git arm at its pinned commit, checks the root license
file, and passes that checkout to Claude Code. Nothing from those repositories
is written into this tree. The stub command uses benchmarks/aicbench/stub/agent.py
and the task oracle. It does not fetch and it does not call a model.
public_benchmark_scores stays null on every report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from benchmarks.aicbench.catalog import CatalogError, load_catalog
from benchmarks.aicbench.grading import (
    GradeError,
    IntegrityError,
    ORACLE_KEY,
    grade,
    outside_repository_temp,
    prepare_workspace,
    protected_bytes,
    sha256_manifest,
    verified_bytes,
)
from benchmarks.aicbench.metrics import cost_from_payload, cost_text


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"
STUB_AGENT = ROOT / "benchmarks" / "aicbench" / "stub" / "agent.py"
PLUMBING_TASK = "bugfix-ledger-signs"
STAND_IN_MARK = "AIC baseline stub stand-in. Not upstream text."
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_ARM = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MOUNTS = frozenset({"none", "plugin-dir", "add-dir"})
_GIT_FIELDS = frozenset({
    "id",
    "role",
    "kind",
    "mount",
    "fetches",
    "repository",
    "url",
    "commit",
    "license_spdx",
    "license_path",
    "license_sha256",
    "copyright_notice",
    "plugin_manifest",
    "plugin_name",
    "plugin_version",
    "skill_name",
    "skill_path",
})


class AdapterError(Exception):
    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


def load_json(path: Path) -> dict:
    if path.is_symlink():
        raise AdapterError(f"refusing a symlinked file: {path}", 3)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"unreadable JSON: {path}", 1) from exc
    if not isinstance(value, dict):
        raise AdapterError(f"JSON object required: {path}", 1)
    return value


def _relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in value.split("/"):
        raise AdapterError(f"{label} must be a relative path.", 2)
    return value


def _notice(value: object) -> str:
    if not isinstance(value, str) or "\n" in value or not value.startswith("Copyright") or not 8 <= len(value) <= 200:
        raise AdapterError("copyright notice must be one Copyright line.", 2)
    return value


def _git_arm(entry: dict) -> None:
    extra = set(entry) - _GIT_FIELDS
    if extra:
        raise AdapterError("git arm has unknown fields: " + ", ".join(sorted(extra)), 2)
    if entry.get("role") != "comparable" or entry.get("fetches") is not True:
        raise AdapterError(f"{entry.get('id')} must be a fetched comparable arm.", 2)
    if entry.get("license_spdx") != "MIT":
        raise AdapterError(f"{entry.get('id')} license must be MIT.", 2)
    repository = entry.get("repository")
    if not isinstance(repository, str) or _REPO.fullmatch(repository) is None:
        raise AdapterError(f"{entry.get('id')} repository is not owner/name.", 2)
    if entry.get("url") != f"https://github.com/{repository}":
        raise AdapterError(f"{entry.get('id')} url does not match the repository.", 2)
    if not isinstance(entry.get("commit"), str) or _SHA.fullmatch(entry["commit"]) is None:
        raise AdapterError(f"{entry.get('id')} commit is not a full lowercase SHA.", 2)
    if not isinstance(entry.get("license_sha256"), str) or _HEX.fullmatch(entry["license_sha256"]) is None:
        raise AdapterError(f"{entry.get('id')} license sha256 is not 64 hex characters.", 2)
    _relative_path(entry.get("license_path"), "license_path")
    _notice(entry.get("copyright_notice"))
    mount = entry.get("mount")
    if mount == "plugin-dir":
        _relative_path(entry.get("plugin_manifest"), "plugin_manifest")
        if not isinstance(entry.get("plugin_name"), str) or not entry["plugin_name"]:
            raise AdapterError(f"{entry.get('id')} plugin name is required.", 2)
        if not isinstance(entry.get("plugin_version"), str) or not entry["plugin_version"]:
            raise AdapterError(f"{entry.get('id')} plugin version is required.", 2)
        if "skill_name" in entry or "skill_path" in entry:
            raise AdapterError(f"{entry.get('id')} plugin arm does not use a skill mount.", 2)
    elif mount == "add-dir":
        _relative_path(entry.get("skill_path"), "skill_path")
        if not isinstance(entry.get("skill_name"), str) or not entry["skill_name"]:
            raise AdapterError(f"{entry.get('id')} skill name is required.", 2)
        for field in ("plugin_manifest", "plugin_name", "plugin_version"):
            if field in entry:
                raise AdapterError(f"{entry.get('id')} add-dir arm does not use a plugin manifest.", 2)
    else:
        raise AdapterError(f"{entry.get('id')} git mount must be plugin-dir or add-dir.", 2)


def validate_registry(data: dict) -> dict:
    if data.get("schema_version") != 1:
        raise AdapterError("baseline registry schema_version must be 1.", 2)
    if data.get("vendored") is not False or data.get("public_benchmark_scores") is not None:
        raise AdapterError("baseline registry must stay unvendored and unscored.", 2)
    if data.get("seed_sent_to_provider") is not False:
        raise AdapterError("the recorded seed is not sent to the provider.", 2)
    if not isinstance(data.get("model"), str) or not data["model"] or data["model"].startswith("-"):
        raise AdapterError("baseline model id is required.", 2)
    if isinstance(data.get("seed"), bool) or not isinstance(data.get("seed"), int) or data["seed"] < 0:
        raise AdapterError("baseline seed must be a non-negative integer.", 2)
    budget = data.get("budget")
    if not isinstance(budget, dict) or set(budget) != {"max_turns", "timeout_sec", "max_usd"}:
        raise AdapterError("baseline budget must set max_turns, timeout_sec, and max_usd.", 2)
    turns, timeout, spend = budget["max_turns"], budget["timeout_sec"], budget["max_usd"]
    if isinstance(turns, bool) or isinstance(timeout, bool) or not isinstance(turns, int) or not isinstance(timeout, int):
        raise AdapterError("baseline turn and timeout limits must be integers.", 2)
    if not 1 <= turns <= 100 or not 1 <= timeout <= 7200:
        raise AdapterError("baseline budget is outside the allowed range.", 2)
    if spend is not None and (isinstance(spend, bool) or not isinstance(spend, (int, float)) or spend < 0):
        raise AdapterError("baseline max_usd must be null or a non-negative number.", 2)
    arms = data.get("arms")
    if not isinstance(arms, list) or len(arms) < 2:
        raise AdapterError("baseline registry needs the plain arm, AIC, and any comparables.", 2)
    seen: set[str] = set()
    for entry in arms:
        if not isinstance(entry, dict):
            raise AdapterError("each baseline arm must be an object.", 2)
        arm_id = entry.get("id")
        if not isinstance(arm_id, str) or _ARM.fullmatch(arm_id) is None:
            raise AdapterError("baseline arm id must be a short lowercase token.", 2)
        if arm_id in seen:
            raise AdapterError(f"duplicate baseline arm: {arm_id}", 2)
        seen.add(arm_id)
        if entry.get("kind") not in {"builtin", "git"} or entry.get("mount") not in _MOUNTS:
            raise AdapterError(f"{arm_id} kind or mount is not supported.", 2)
        if entry.get("kind") == "git":
            _git_arm(entry)
            continue
        if entry.get("fetches") is not False:
            raise AdapterError(f"{arm_id} builtin arm must not fetch.", 2)
    if [item["id"] for item in arms[:2]] != ["plain-claude-code", "aic"]:
        raise AdapterError("the first arms must be plain-claude-code and aic.", 2)
    plain, treated = arms[0], arms[1]
    if plain.get("mount") != "none" or plain.get("license_spdx") is not None or plain.get("role") != "plain":
        raise AdapterError("plain-claude-code mounts nothing.", 2)
    if treated.get("role") != "aic" or treated.get("mount") != "plugin-dir" or treated.get("plugin_name") != "aic":
        raise AdapterError("the aic arm must mount this repository's plugin.", 2)
    if treated.get("license_spdx") != "Apache-2.0":
        raise AdapterError("the aic arm license must be Apache-2.0.", 2)
    return data


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    registry = validate_registry(load_json(path))
    _assert_pinned(registry)
    return registry


def _assert_pinned(registry: dict, root: Path = ROOT) -> None:
    settings = load_json(root / "benchmarks" / "pinned.json")
    if registry["model"] != settings.get("model") or registry["seed"] != settings.get("seed"):
        raise AdapterError("baseline registry model and seed must match benchmarks/pinned.json.", 2)


def git_fetch_commands(repository: str, commit: str, dest: Path) -> list[list[str]]:
    if _REPO.fullmatch(repository) is None or _SHA.fullmatch(commit) is None:
        raise AdapterError("refusing to pass an unexpected repository or commit to git.", 2)
    git = ["git", "-c", "core.hooksPath=/dev/null"]
    url = f"https://github.com/{repository}.git"
    return [
        [*git, "init", str(dest)],
        [*git, "-C", str(dest), "remote", "add", "origin", url],
        [*git, "-C", str(dest), "fetch", "--depth", "1", "origin", commit],
        [*git, "-C", str(dest), "checkout", "--detach", "FETCH_HEAD"],
    ]


def assert_outside_repo(path: Path, repo: Path = ROOT) -> None:
    resolved = path.resolve()
    repo_resolved = repo.resolve()
    if resolved == repo_resolved or repo_resolved in resolved.parents:
        raise AdapterError("refusing to materialize a baseline inside the repository.", 3)


def assert_license(entry: dict, dest: Path) -> None:
    """Check a fetched checkout. Stub stand-ins do not call this."""
    if dest.is_symlink() or not dest.is_dir():
        raise AdapterError(f"{entry['id']} checkout is not a real directory.", 3)
    license_path = dest / entry["license_path"]
    if license_path.is_symlink() or not license_path.is_file():
        raise AdapterError(f"{entry['id']} license file is missing at the pin.", 3)
    digest = hashlib.sha256(license_path.read_bytes()).hexdigest()
    if digest != entry["license_sha256"]:
        raise AdapterError(f"{entry['id']} license file does not match the pinned sha256.", 3)
    text = license_path.read_text(encoding="utf-8", errors="replace")
    if entry["copyright_notice"] not in text.splitlines():
        raise AdapterError(f"{entry['id']} license file is missing its copyright notice.", 3)
    if STAND_IN_MARK in text:
        raise AdapterError(f"{entry['id']} checkout is a stub stand-in, not the pinned tree.", 3)
    if entry["mount"] == "plugin-dir":
        manifest = dest / entry["plugin_manifest"]
        if manifest.is_symlink() or not manifest.is_file():
            raise AdapterError(f"{entry['id']} plugin manifest is missing at the pin.", 3)
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AdapterError(f"{entry['id']} plugin manifest is unreadable.", 3) from exc
        if not isinstance(payload, dict) or payload.get("name") != entry["plugin_name"]:
            raise AdapterError(f"{entry['id']} plugin name does not match the registry.", 3)
        return
    skill = dest / entry["skill_path"]
    if skill.is_symlink() or not skill.is_file():
        raise AdapterError(f"{entry['id']} SKILL.md is missing at the pin.", 3)
    try:
        head = skill.read_text(encoding="utf-8")[:500]
    except (OSError, UnicodeError) as exc:
        raise AdapterError(f"{entry['id']} SKILL.md is unreadable.", 3) from exc
    if STAND_IN_MARK in head:
        raise AdapterError(f"{entry['id']} checkout is a stub stand-in, not the pinned tree.", 3)
    if f"name: {entry['skill_name']}" not in head.splitlines()[:20]:
        raise AdapterError(f"{entry['id']} skill name does not match the registry.", 3)


def _write_git_standin(entry: dict, dest: Path) -> None:
    if dest.exists() or dest.is_symlink():
        raise AdapterError(f"refusing to overwrite a baseline checkout: {entry['id']}", 3)
    assert_outside_repo(dest)
    dest.mkdir(parents=True)
    (dest / entry["license_path"]).write_text(
        f"{STAND_IN_MARK}\nExpected license sha256: {entry['license_sha256']}\n",
        encoding="utf-8",
    )
    (dest / "ATTRIBUTION.json").write_text(
        json.dumps(
            {
                "commit": entry["commit"],
                "copyright_notice": entry["copyright_notice"],
                "license_sha256": entry["license_sha256"],
                "license_spdx": entry["license_spdx"],
                "repository": entry["repository"],
                "stub": True,
                "upstream_bytes": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if entry["mount"] == "plugin-dir":
        manifest = dest / entry["plugin_manifest"]
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"name": entry["plugin_name"], "stub": True}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return
    (dest / entry["skill_path"]).write_text(
        f"---\nname: {entry['skill_name']}\n---\n\n{STAND_IN_MARK}\n",
        encoding="utf-8",
    )


def stand_in_mount(entry: dict, dest: Path) -> tuple[str, Path | None]:
    """Prepare one arm without network. Git arms get an AIC-authored stand-in."""
    if entry["kind"] == "builtin" and entry["id"] == "plain-claude-code":
        return "none", None
    if entry["kind"] == "builtin" and entry["id"] == "aic":
        return "plugin-dir", ROOT
    if entry["kind"] != "git":
        raise AdapterError(f"unsupported arm: {entry.get('id')}", 2)
    _write_git_standin(entry, dest)
    return entry["mount"], dest


def fetch_and_verify(entry: dict, dest: Path, runner=subprocess.run) -> None:
    if entry["kind"] != "git":
        raise AdapterError(f"{entry['id']} is not a fetched arm.", 2)
    if dest.exists() or dest.is_symlink():
        raise AdapterError(f"refusing to reuse a checkout: {entry['id']}", 3)
    assert_outside_repo(dest)
    for argv in git_fetch_commands(entry["repository"], entry["commit"], dest):
        for item in argv[1:]:
            if item.startswith("-") and item not in {"-c", "-C", "--depth", "--detach"}:
                raise AdapterError("refusing an unexpected git flag.", 2)
        completed = runner(argv, check=False, capture_output=True, text=True, timeout=180)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "git failed").strip()
            raise AdapterError(f"{entry['id']} fetch failed: {detail[:300]}", 1)
    observed = runner(
        ["git", "-C", str(dest), "-c", "core.hooksPath=/dev/null", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if observed.returncode != 0 or observed.stdout.strip() != entry["commit"]:
        raise AdapterError(f"{entry['id']} checkout is not the pinned commit.", 3)
    assert_license(entry, dest)


def live_mount(entry: dict, dest: Path, runner=subprocess.run) -> tuple[str, Path | None]:
    if entry["kind"] == "builtin" and entry["id"] == "plain-claude-code":
        return "none", None
    if entry["kind"] == "builtin" and entry["id"] == "aic":
        return "plugin-dir", ROOT
    fetch_and_verify(entry, dest, runner)
    return entry["mount"], dest


def _prompt(task) -> str:
    return (
        f"Task id: {task.id}\n\n{task.instruction}\n"
        "This task is already approved. Change only files inside the current workspace. "
        "Do not search outside it for tests, answers, or graders. "
        "Stop when the acceptance criteria in the task are met.\n"
    )


def agent_argv(
    binary: str,
    *,
    prompt: str,
    model: str,
    max_turns: int,
    mount: str,
    mount_path: Path | None,
) -> list[str]:
    if "\x00" in prompt or "\x00" in binary or "\x00" in model:
        raise AdapterError("refusing a NUL in the agent command.", 2)
    argv = [
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
        "--model",
        model,
    ]
    if mount == "none":
        if mount_path is not None:
            raise AdapterError("the plain arm must not receive a mount.", 2)
        return argv
    if mount_path is None:
        raise AdapterError("a mounted arm needs a directory.", 2)
    if mount == "plugin-dir":
        argv.extend(["--plugin-dir", str(mount_path)])
        return argv
    if mount == "add-dir":
        argv.extend(["--add-dir", str(mount_path)])
        return argv
    raise AdapterError(f"unknown mount: {mount}", 2)


def _task(task_id: str):
    try:
        matches = [item for item in load_catalog() if item.id == task_id]
    except CatalogError as exc:
        raise AdapterError(str(exc), 1) from exc
    if len(matches) != 1:
        raise AdapterError(f"unknown aicbench task: {task_id}", 2)
    return matches[0]


def _child_env(
    parent: dict[str, str],
    *,
    task,
    seed: int,
    home: Path,
    stub: bool,
    key: str | None,
) -> dict[str, str]:
    env = {
        "AIC_BENCH_SEED": str(seed),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": parent.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if stub:
        env["AICBENCH_BASELINE_STUB"] = "1"
        env["AICBENCH_STUB_REFERENCE"] = str(task.reference.resolve())
        env["AICBENCH_STUB_REMOVE"] = json.dumps(list(task.remove))
        return env
    if not key:
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    env["ANTHROPIC_API_KEY"] = key
    return env


def _parse_payload(stdout: str) -> dict:
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


def _blank_receipt(entry: dict, registry: dict, *, invokes_model: bool, seconds: float, error: str) -> dict:
    return {
        "arm": entry["id"],
        "budget": dict(registry["budget"]),
        "commit": entry.get("commit"),
        "copyright_notice": entry.get("copyright_notice"),
        "cost_usd": None,
        "exit_code": None,
        "fetched": False,
        "harness_error": error[:500],
        "invalid": True,
        "invokes_model": invokes_model,
        "license_spdx": entry.get("license_spdx"),
        "model": registry["model"],
        "mount": entry["mount"],
        "passed": False,
        "prompt_sha256": None,
        "public_benchmark_scores": None,
        "repository": entry.get("repository"),
        "seed": registry["seed"],
        "wall_time_seconds": seconds,
    }


def _stub_observed(payload: dict, *, mount: str, mount_path: Path | None, entry: dict) -> str | None:
    if payload.get("role") != "baseline-stub" or payload.get("invokes_model") is not False:
        return "stub payload was not a baseline stub result."
    if payload.get("api_key_visible") is not False:
        return "stub process saw an API key."
    if payload.get("reference_applied") is not True:
        return "stub did not apply the reference."
    if mount == "none":
        if payload.get("plugin_dir") is not None or payload.get("add_dir") is not None:
            return "plain arm received a mount."
        return None
    expected = None if mount_path is None else str(mount_path)
    if mount == "plugin-dir":
        if payload.get("plugin_dir") != expected or payload.get("add_dir") is not None:
            return "plugin mount was not visible to the stub."
        if payload.get("plugin_name") != entry.get("plugin_name"):
            return "stub read a different plugin name."
        return None
    if mount == "add-dir":
        if payload.get("add_dir") != expected or payload.get("plugin_dir") is not None:
            return "add-dir mount was not visible to the stub."
        if payload.get("skill_stand_in") is not True:
            return "stub did not see the stand-in skill marker."
        return None
    return f"unknown mount: {mount}"


def execute_arms(
    registry: dict,
    task,
    *,
    binary: str,
    parent_env: dict[str, str],
    materialize,
    kind: str,
    invokes_model: bool,
    key: str | None,
    launch=subprocess.run,
) -> dict:
    prompt = _prompt(task)
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    expected = sha256_manifest(protected_bytes(task))
    receipts = []
    with tempfile.TemporaryDirectory(prefix="aic-baselines-", dir=outside_repository_temp()) as temporary:
        root = Path(temporary)
        home = root / "home"
        home.mkdir()
        for entry in registry["arms"]:
            started = time.perf_counter()
            workspace = root / f"{entry['id']}-workspace"
            checkout = root / f"{entry['id']}-checkout"
            try:
                mount, mount_path = materialize(entry, checkout)
                if key and mount_path is not None and key in str(mount_path):
                    raise AdapterError("refusing to put the API key in a path.", 1)
                prepare_workspace(task, workspace, solution=False)
                argv = agent_argv(
                    binary,
                    prompt=prompt,
                    model=registry["model"],
                    max_turns=registry["budget"]["max_turns"],
                    mount=mount,
                    mount_path=mount_path,
                )
                if key and key in argv:
                    raise AdapterError("refusing to put the API key on a command line.", 1)
                env = _child_env(
                    parent_env,
                    task=task,
                    seed=registry["seed"],
                    home=home,
                    stub=not invokes_model,
                    key=key,
                )
                completed = launch(
                    argv,
                    cwd=workspace,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=registry["budget"]["timeout_sec"],
                )
            except subprocess.TimeoutExpired:
                receipts.append(
                    _blank_receipt(
                        entry,
                        registry,
                        invokes_model=invokes_model,
                        seconds=round(time.perf_counter() - started, 6),
                        error="agent timeout",
                    )
                )
                continue
            except (AdapterError, GradeError, OSError) as exc:
                receipts.append(
                    _blank_receipt(
                        entry,
                        registry,
                        invokes_model=invokes_model,
                        seconds=round(time.perf_counter() - started, 6),
                        error=str(exc),
                    )
                )
                continue
            elapsed = round(time.perf_counter() - started, 6)
            payload = _parse_payload(completed.stdout or "")
            cost = cost_text(cost_from_payload(payload))
            harness_error = None
            invalid = False
            grade_passed = False
            if not invokes_model:
                harness_error = _stub_observed(payload, mount=mount, mount_path=mount_path, entry=entry)
                if payload.get("model") != registry["model"] or payload.get("seed") != str(registry["seed"]):
                    harness_error = harness_error or "stub did not observe the shared model and seed."
                if payload.get("max_turns") != str(registry["budget"]["max_turns"]):
                    harness_error = harness_error or "stub did not observe the shared turn budget."
                if payload.get("task_id") != task.id:
                    harness_error = harness_error or "stub did not observe the task id."
            try:
                current = verified_bytes(task, expected)
            except IntegrityError as exc:
                invalid = True
                harness_error = str(exc)
                current = None
            if current is not None and harness_error is None:
                try:
                    result = grade(task, workspace, oracle_bytes=current[ORACLE_KEY])
                    grade_passed = result.passed and not result.timed_out
                    if not grade_passed:
                        harness_error = result.detail[-300:] or "oracle did not pass."
                except GradeError as exc:
                    harness_error = str(exc)
            passed = (
                grade_passed
                and completed.returncode == 0
                and harness_error is None
                and not invalid
            )
            receipts.append(
                {
                    "arm": entry["id"],
                    "budget": dict(registry["budget"]),
                    "commit": entry.get("commit"),
                    "copyright_notice": entry.get("copyright_notice"),
                    "cost_usd": cost,
                    "exit_code": completed.returncode,
                    "fetched": bool(invokes_model and entry["kind"] == "git"),
                    "harness_error": harness_error,
                    "invalid": invalid,
                    "invokes_model": invokes_model,
                    "license_spdx": entry.get("license_spdx"),
                    "model": registry["model"],
                    "mount": mount,
                    "passed": passed,
                    "prompt_sha256": prompt_sha,
                    "public_benchmark_scores": None,
                    "repository": entry.get("repository"),
                    "seed": registry["seed"],
                    "wall_time_seconds": elapsed,
                }
            )
    ok = bool(receipts) and all(item["passed"] is True and item["public_benchmark_scores"] is None for item in receipts)
    if not invokes_model:
        ok = ok and all(item["cost_usd"] == "0" and item["fetched"] is False for item in receipts)
    return {
        "agent": "benchmarks/aicbench/stub/agent.py" if not invokes_model else binary,
        "budget": dict(registry["budget"]),
        "invokes_model": invokes_model,
        "kind": kind,
        "measured": False,
        "model": registry["model"],
        "note": (
            "Stub agent and oracle only. A pass here proves the adapter, the mount, and the grader. "
            "It is not a public benchmark score."
            if not invokes_model
            else "Live agents may call a model. This report is not a public benchmark score."
        ),
        "official": False,
        "ok": ok,
        "public_benchmark_scores": None,
        "receipts": receipts,
        "sample_size": 1,
        "sandbox": "none",
        "seed": registry["seed"],
        "seed_sent_to_provider": False,
        "suite": "aicbench",
        "task": task.id,
    }


def _key(parent: dict[str, str]) -> str | None:
    value = parent.get("ANTHROPIC_API_KEY", "")
    if not value or any(character.isspace() or ord(character) < 32 for character in value):
        return None
    return value


def run_stub(parent: dict[str, str] | None = None, *, registry: dict | None = None) -> dict:
    loaded = registry if registry is not None else load_registry()
    if not STUB_AGENT.is_file() or STUB_AGENT.is_symlink():
        raise AdapterError("aicbench stub agent is missing.", 1)
    report = execute_arms(
        loaded,
        _task(PLUMBING_TASK),
        binary=str(STUB_AGENT),
        parent_env=os.environ if parent is None else parent,
        materialize=stand_in_mount,
        kind="baseline-stub",
        invokes_model=False,
        key=None,
    )
    if report["public_benchmark_scores"] is not None:
        raise AdapterError("stub report must leave public scores null.", 1)
    return report


def run_live(
    parent: dict[str, str],
    *,
    binary: str = "claude",
    task_id: str = PLUMBING_TASK,
    registry: dict | None = None,
    runner=subprocess.run,
) -> dict:
    key = _key(parent)
    if key is None:
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    loaded = registry if registry is not None else load_registry()

    def materialize(entry: dict, dest: Path) -> tuple[str, Path | None]:
        return live_mount(entry, dest, runner)

    return execute_arms(
        loaded,
        _task(task_id),
        binary=binary,
        parent_env=parent,
        materialize=materialize,
        kind="baseline-live",
        invokes_model=True,
        key=key,
        launch=runner,
    )


def _emit(report: dict, output: Path | None) -> None:
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is not None:
        if output.exists() or output.is_symlink():
            raise AdapterError(f"refusing to overwrite {output}", 3)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks.baselines")
    parser.add_argument("command", choices=("stub", "live"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--task", default=PLUMBING_TASK)
    parser.add_argument("--claude-bin", default="claude")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return 2 if code is None else int(code)
    parent = os.environ if environ is None else environ
    try:
        if args.command == "stub":
            if args.task != PLUMBING_TASK:
                raise AdapterError("the stub proof runs one plumbing task.", 2)
            report = run_stub(parent)
        else:
            report = run_live(parent, binary=args.claude_bin, task_id=args.task)
        _emit(report, args.output)
    except AdapterError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    return 0 if report.get("ok") else 1
