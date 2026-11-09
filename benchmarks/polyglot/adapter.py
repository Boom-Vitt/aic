"""Fetch pinned Exercism exercises and score the official arms.

Aider-AI/polyglot-benchmark has no root license file, so this adapter does
not fetch that tree and does not copy exercise bytes into this repository.
Included tracks are fetched at the pinned commit into a temporary directory,
scored, and discarded. The key-free stub uses an original local fixture.
public_benchmark_scores stays null.
"""
from __future__ import annotations

import argparse
import decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from benchmarks.aicbench.grading import GradeError, outside_repository_temp
from benchmarks.aicbench.metrics import cost_from_payload, cost_text
from benchmarks.aicbench.sandbox import container_command
from benchmarks.baselines.adapter import (
    ROOT,
    STUB_AGENT,
    AdapterError,
    _key,
    _parse_payload,
    _require_bwrap,
    _resolve_tool,
    _run_in_container,
    agent_argv,
    assert_outside_repo,
    load_registry,
)
from benchmarks.baselines.proxy import PROXY_PORT, PhaseProxies, network_policy, system_python
from benchmarks.budget import format_max_usd, shared_stop
from benchmarks.suite_arms import OFFICIAL_IDS, load_pinned, prepare_live_official_arms, prepare_stand_in_arms


PIN_PATH = Path(__file__).resolve().parent / "pins.json"
SCHEMA = "aic.aider-polyglot.receipt"
SCHEMA_VERSION = 1
PERMISSIVE = frozenset({"Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MIT"})
TRACK_IDS = ("cpp", "go", "java", "javascript", "python", "rust")
SOURCE_IDS = ("polyglot-benchmark", "aider")
LICENSE_SHA = "e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df"
COPYRIGHT = "Copyright (c) 2021 Exercism"
MISSING_KEY = (
    "ANTHROPIC_API_KEY is required. No Exercism exercise was fetched and no polyglot score was recorded."
)
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_LICENSE_NAME = re.compile(r"LICENSE(?:\.txt)?\Z")
_SKIP = frozenset({".git", ".meta", "__pycache__"})
FIXTURE_SLUG = "sum-digits"
FIXTURE_COPYRIGHT = "Copyright (c) 2026 AIC polyglot fixture"
DECOY_MARKER = "polyglot-fixture-decoy-not-exercism"
_GIT = ("git", "-c", "core.hooksPath=/dev/null")


class _PhaseTask:
    reference = Path("/tmp")
    remove: list[str] = []


def load_pins(path: Path = PIN_PATH) -> dict:
    if path.is_symlink():
        raise AdapterError("refusing a symlinked polyglot pin.", 3)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError("polyglot pins are unreadable.", 1) from exc
    validate_pins(data)
    return data


def validate_pins(data: dict) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise AdapterError("polyglot pins must be a schema 1 object.", 2)
    if data.get("suite") != "aider-polyglot" or data.get("vendored") is not False:
        raise AdapterError("polyglot pins must stay an unvendored aider-polyglot suite.", 2)
    if data.get("public_benchmark_scores") is not None:
        raise AdapterError("polyglot pins must leave public scores null.", 2)
    limit = data.get("max_exercises")
    if type(limit) is not int or not 1 <= limit <= 225:
        raise AdapterError("polyglot max_exercises must be an integer from 1 through 225.", 2)
    sources = data.get("sources")
    tracks = data.get("tracks")
    if not isinstance(sources, list) or not isinstance(tracks, list):
        raise AdapterError("polyglot pins need sources and tracks.", 2)
    if [item.get("id") for item in sources if isinstance(item, dict)] != list(SOURCE_IDS):
        raise AdapterError("polyglot sources must be the benchmark mirror and the aider harness.", 2)
    if [item.get("id") for item in tracks if isinstance(item, dict)] != list(TRACK_IDS):
        raise AdapterError("polyglot tracks must be the six Exercism languages, in order.", 2)
    for source in sources:
        _validate_source(source)
    total = 0
    for track in tracks:
        _validate_track(track)
        total += len(track["exercises"])
    if total != 225:
        raise AdapterError("polyglot exercise index must name 225 exercises.", 2)


def _validate_source(source: dict) -> None:
    if source.get("included") is not False:
        raise AdapterError(f"{source.get('id')} is not an exercise source.", 2)
    if not isinstance(source.get("reason"), str) or not source["reason"]:
        raise AdapterError(f"{source.get('id')} needs an exclusion reason.", 2)
    commit = source.get("commit")
    if not isinstance(commit, str) or _SHA.fullmatch(commit) is None:
        raise AdapterError(f"{source.get('id')} commit is not a full SHA.", 2)
    if source["id"] == "polyglot-benchmark":
        if source.get("license_spdx") is not None or source.get("license_path") is not None:
            raise AdapterError("polyglot-benchmark has no root license file.", 2)
        if source["commit"] != "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f":
            raise AdapterError("polyglot-benchmark pin drifted.", 2)
        return
    if source.get("license_spdx") != "Apache-2.0" or source.get("license_path") != "LICENSE.txt":
        raise AdapterError("the aider harness pin is not Apache-2.0 LICENSE.txt.", 2)


def _validate_track(track: dict) -> None:
    if track.get("included") is not True:
        raise AdapterError(f"{track.get('id')} is missing a reviewed inclusion decision.", 2)
    if track.get("license_spdx") not in PERMISSIVE:
        raise AdapterError(f"{track.get('id')} is not a permissive root license.", 2)
    if track.get("license_path") is None or _LICENSE_NAME.fullmatch(str(track.get("license_path"))) is None:
        raise AdapterError(f"{track.get('id')} license path is not a root license file.", 2)
    if track.get("license_sha256") != LICENSE_SHA or track.get("copyright_notice") != COPYRIGHT:
        raise AdapterError(f"{track.get('id')} license pin does not match the reviewed MIT file.", 2)
    if track.get("repository") != f"exercism/{track['id']}":
        raise AdapterError(f"{track.get('id')} repository is not the Exercism track.", 2)
    commit = track.get("commit")
    if not isinstance(commit, str) or _SHA.fullmatch(commit) is None:
        raise AdapterError(f"{track.get('id')} commit is not a full SHA.", 2)
    if not isinstance(track.get("commit_date"), str) or len(track["commit_date"]) != 10:
        raise AdapterError(f"{track.get('id')} commit date is missing.", 2)
    exercises = track.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        raise AdapterError(f"{track.get('id')} has no exercise index.", 2)
    if len(exercises) != len(set(exercises)):
        raise AdapterError(f"{track.get('id')} repeats an exercise name.", 2)
    for slug in exercises:
        if not isinstance(slug, str) or _SLUG.fullmatch(slug) is None:
            raise AdapterError(f"{track.get('id')} has an unsafe exercise name.", 2)
    commands = track.get("test_commands")
    if not isinstance(commands, list) or not commands:
        raise AdapterError(f"{track.get('id')} has no test command.", 2)
    for argv in commands:
        _validate_argv(argv, track["id"])


def _validate_argv(argv: object, label: str) -> None:
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise AdapterError(f"{label} test command is empty.", 2)
    if any(item.startswith("-") and item != "--" for item in (argv[0],)) or "\x00" in "".join(argv):
        raise AdapterError(f"{label} test command is unsafe.", 2)
    if any(character in item for item in argv for character in "\n;|&$`"):
        raise AdapterError(f"{label} test command contains a shell operator.", 2)


def included_tracks(pins: dict) -> list[dict]:
    return [track for track in pins["tracks"] if track.get("included") is True]


def planned_exercises(pins: dict) -> list[tuple[dict, str]]:
    chosen: list[tuple[dict, str]] = []
    for track in included_tracks(pins):
        for slug in track["exercises"]:
            chosen.append((track, slug))
            if len(chosen) >= pins["max_exercises"]:
                return chosen
    return chosen


def github_url(repository: str) -> str:
    if _REPO.fullmatch(repository) is None:
        raise AdapterError("refusing an unexpected repository.", 2)
    return f"https://github.com/{repository}.git"


def _remote(url: str) -> str:
    if not isinstance(url, str) or not url or url.startswith("-") or any(character.isspace() or character == "\x00" for character in url):
        raise AdapterError("refusing an unsafe git remote.", 2)
    if url.startswith("https://github.com/") and url.endswith(".git") and url.count("/") == 4:
        repository = url[len("https://github.com/"):-len(".git")]
        if _REPO.fullmatch(repository) is None:
            raise AdapterError("refusing an unsafe git remote.", 2)
        return url
    path = Path(url)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise AdapterError("refusing an unsafe git remote.", 2)
    resolved = path.resolve()
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents:
        raise AdapterError("refusing to fetch a remote inside the repository.", 3)
    return str(resolved)


def _git_env(parent: dict[str, str] | None = None) -> dict[str, str]:
    source = os.environ if parent is None else parent
    env = {
        "PATH": source.get("PATH", ""),
        "HOME": source.get("HOME", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return {key: value for key, value in env.items() if key != "ANTHROPIC_API_KEY"}


def fetch_commands(repository: str, commit: str, dest: Path, url: str, license_path: str, slug: str) -> list[list[str]]:
    if _REPO.fullmatch(repository) is None or _SHA.fullmatch(commit) is None:
        raise AdapterError("refusing to pass an unexpected repository or commit to git.", 2)
    if _LICENSE_NAME.fullmatch(license_path) is None or _SLUG.fullmatch(slug) is None:
        raise AdapterError("refusing an unsafe sparse checkout path.", 2)
    remote = _remote(url)
    exercise = f"exercises/practice/{slug}"
    return [
        [*_GIT, "init", "-b", "main", str(dest)],
        [*_GIT, "-C", str(dest), "remote", "add", "origin", remote],
        [*_GIT, "-C", str(dest), "sparse-checkout", "set", "--no-cone", license_path, exercise],
        [*_GIT, "-C", str(dest), "fetch", "--depth", "1", "origin", commit],
        [*_GIT, "-C", str(dest), "checkout", "--detach", "FETCH_HEAD"],
    ]


def fetch_track(
    track: dict,
    dest: Path,
    slug: str,
    *,
    url: str,
    runner=subprocess.run,
    parent: dict[str, str] | None = None,
) -> list[list[str]]:
    if track.get("included") is not True or track.get("license_spdx") not in PERMISSIVE:
        raise AdapterError(f"{track.get('id')} is not an included permissive track.", 2)
    if dest.exists() or dest.is_symlink():
        raise AdapterError(f"refusing to reuse a checkout: {track.get('id')}", 3)
    assert_outside_repo(dest.parent)
    commands = fetch_commands(track["repository"], track["commit"], dest, url, track["license_path"], slug)
    env = _git_env(parent)
    try:
        for argv in commands:
            completed = runner(argv, check=False, capture_output=True, text=True, timeout=180, env=env)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "git failed").strip()
                raise AdapterError(f"{track['id']} fetch failed: {detail[:300]}", 1)
        observed = runner(
            [*_GIT, "-C", str(dest), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if observed.returncode != 0 or observed.stdout.strip() != track["commit"]:
            raise AdapterError(f"{track['id']} checkout is not the pinned commit.", 3)
        _assert_license(track, dest)
        exercise = dest / "exercises" / "practice" / slug
        if exercise.is_symlink() or not exercise.is_dir():
            raise AdapterError(f"{track['id']} exercise is missing at the pin: {slug}.", 3)
    except Exception:
        if dest.exists() or dest.is_symlink():
            shutil.rmtree(dest, ignore_errors=True)
        raise
    return commands


def _assert_license(track: dict, dest: Path) -> None:
    license_path = dest / track["license_path"]
    if license_path.is_symlink() or not license_path.is_file():
        raise AdapterError(f"{track['id']} license file is missing at the pin.", 3)
    digest = hashlib.sha256(license_path.read_bytes()).hexdigest()
    if digest != track["license_sha256"]:
        raise AdapterError(f"{track['id']} license file does not match the pinned sha256.", 3)
    text = license_path.read_text(encoding="utf-8", errors="replace")
    if track["copyright_notice"] not in text.splitlines():
        raise AdapterError(f"{track['id']} license file is missing its copyright notice.", 3)


def prepare_workspace(checkout: Path, slug: str, dest: Path) -> None:
    if _SLUG.fullmatch(slug) is None:
        raise AdapterError("refusing an unsafe exercise name.", 2)
    source = checkout / "exercises" / "practice" / slug
    if source.is_symlink() or not source.is_dir():
        raise AdapterError(f"exercise directory is missing: {slug}.", 3)
    if dest.exists() or dest.is_symlink():
        raise AdapterError("refusing to reuse an exercise workspace.", 3)
    assert_outside_repo(dest.parent)
    dest.mkdir(parents=True)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in _SKIP or part == ".." for part in relative.parts):
            continue
        if path.is_symlink():
            raise AdapterError(f"refusing a symlinked exercise file: {relative}.", 3)
        target = dest.joinpath(*relative.parts)
        if target != dest and dest.resolve() not in target.resolve().parents and target.resolve() != dest.resolve():
            raise AdapterError("exercise copy escapes the workspace.", 3)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        else:
            raise AdapterError(f"refusing an unsupported exercise file: {relative}.", 3)
    if any(part == ".meta" for path in dest.rglob("*") for part in path.relative_to(dest).parts):
        raise AdapterError("exercise workspace still contains exemplar metadata.", 3)


def score_exercise(
    workspace: Path,
    commands: list[list[str]],
    *,
    parent: dict[str, str] | None = None,
    timeout: int = 180,
) -> dict:
    if workspace.is_symlink() or not workspace.is_dir():
        raise AdapterError("score workspace is missing.", 3)
    env = _git_env(parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    exit_code = 0
    error = None
    for argv in commands:
        _validate_argv(argv, "score")
        try:
            completed = subprocess.run(
                argv,
                cwd=workspace,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            error = f"score command was not found: {argv[0]}."
            exit_code = 127
            break
        except subprocess.TimeoutExpired:
            error = "score command exceeded its timeout."
            exit_code = 124
            break
        exit_code = completed.returncode
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "tests failed").strip()
            error = detail[:300] or "tests failed."
            break
    elapsed = round(time.monotonic() - started, 6)
    return {
        "exit_code": exit_code,
        "harness_error": error,
        "passed": error is None and exit_code == 0,
        "wall_time_seconds": elapsed,
    }


def _temp_root(prefix: str) -> Path:
    try:
        parent = outside_repository_temp()
    except GradeError as exc:
        raise AdapterError(str(exc), 1) from exc
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def _fixture_license() -> str:
    return (
        "MIT License\n"
        "\n"
        f"{FIXTURE_COPYRIGHT}\n"
        "\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\"), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n"
        "\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n"
        "\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n"
    )


def _git(argv: list[str], env: dict[str, str]) -> None:
    completed = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=30, env=env)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "git failed").strip()
        raise AdapterError(f"fixture git failed: {detail[:300]}", 1)


def write_fixture(source: Path) -> dict:
    """Create an original local track. It is not an Exercism exercise."""
    if source.exists() or source.is_symlink():
        raise AdapterError("refusing to reuse a fixture source.", 3)
    assert_outside_repo(source.parent)
    env = _git_env()
    source.mkdir(parents=True)
    practice = source / "exercises" / "practice" / FIXTURE_SLUG
    practice.mkdir(parents=True)
    (practice / ".docs").mkdir()
    (practice / ".meta").mkdir()
    (practice / ".docs" / "instructions.md").write_text(
        "Add two integers. This fixture was written for the offline adapter proof.\n",
        encoding="utf-8",
    )
    (practice / "sum_digits.py").write_text("def add(left, right):\n    return left - right\n", encoding="utf-8")
    (practice / "sum_digits_test.py").write_text(
        "import unittest\n"
        "from sum_digits import add\n"
        "\n"
        "\n"
        "class AddTests(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (practice / ".meta" / "example.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    decoy = source / "exercises" / "practice" / "decoy"
    decoy.mkdir()
    (decoy / "secret.py").write_text(f"# {DECOY_MARKER}\n", encoding="utf-8")
    license_text = _fixture_license()
    (source / "LICENSE").write_text(license_text, encoding="utf-8")
    _git([*_GIT, "-C", str(source), "init", "-b", "main"], env)
    _git([*_GIT, "-C", str(source), "config", "user.email", "fixture@example.invalid"], env)
    _git([*_GIT, "-C", str(source), "config", "user.name", "aic-polyglot-fixture"], env)
    _git([*_GIT, "-C", str(source), "config", "uploadpack.allowReachableSHA1InWant", "true"], env)
    _git([*_GIT, "-C", str(source), "add", "."], env)
    _git([*_GIT, "-C", str(source), "commit", "-m", "fixture"], env)
    observed = subprocess.run(
        [*_GIT, "-C", str(source), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if observed.returncode != 0:
        raise AdapterError("fixture commit is missing.", 1)
    digest = hashlib.sha256(license_text.encode("utf-8")).hexdigest()
    return {
        "id": "fixture",
        "repository": "aic/polyglot-fixture",
        "commit": observed.stdout.strip(),
        "license_path": "LICENSE",
        "license_spdx": "MIT",
        "license_sha256": digest,
        "copyright_notice": FIXTURE_COPYRIGHT,
        "included": True,
        "exercises": [FIXTURE_SLUG],
        "test_commands": [[sys.executable, "-m", "unittest", "sum_digits_test"]],
    }


def _ratio(passed: int, attempted: int) -> str:
    return f"{passed}/{attempted}"


def phase_invocation(
    argv: list[str],
    *,
    phase: str,
    key: str | None,
    bwrap: str,
    proxies,
    workspace: Path,
    home: Path,
    config: Path,
    seed: int,
    timeout: int,
    parent: dict[str, str],
    skill_root: Path | None = None,
) -> dict:
    if phase not in {"install", "agent"}:
        raise AdapterError("polyglot sandbox wiring only has install and agent phases.", 2)
    captured: dict = {}

    def launch(command, **kwargs):
        captured["command"] = list(command)
        captured["env"] = dict(kwargs.get("env") or {})
        return subprocess.CompletedProcess(command, 0, "", "")

    _run_in_container(
        list(argv),
        workspace=workspace,
        home=home,
        config=config,
        skill_root=skill_root,
        parent=parent,
        timeout=timeout,
        task=_PhaseTask(),
        seed=seed,
        key=key if phase == "agent" else None,
        bwrap=bwrap,
        phase=phase,
        proxies=proxies,
        launch=launch,
    )
    command = captured.get("command") or []
    env = captured.get("env") or {}
    repo = str(ROOT.resolve())
    if "--unshare-net" not in command or repo in command:
        raise AdapterError("sandbox command is missing the network unshare or includes the repository.", 1)
    if key and key in command:
        raise AdapterError("refusing to put the API key on a command line.", 1)
    if phase == "install" and ("ANTHROPIC_API_KEY" in env or (key and any(key in str(value) for value in env.values()))):
        raise AdapterError("install phase environment contains a secret.", 1)
    if phase == "agent" and (not key or env.get("ANTHROPIC_API_KEY") != key):
        raise AdapterError("agent phase did not receive the API key in its environment.", 1)
    return {
        "agent_env_has_key": phase == "agent" and env.get("ANTHROPIC_API_KEY") == key,
        "command_has_key": bool(key and key in command),
        "command_has_repository": repo in command,
        "install_env_has_key": "ANTHROPIC_API_KEY" in env,
        "seed_flag": "--seed" in command,
        "unshare_net": "--unshare-net" in command,
        "uses_forwarder": any(str(item).endswith(".aic-egress-forward.py") for item in command),
        "proxy_port": PROXY_PORT in command or str(PROXY_PORT) in " ".join(str(item) for item in command),
    }


def score_sandbox_command(
    argv: list[str],
    *,
    workspace: Path,
    home: Path,
    config: Path,
    bwrap: str,
    parent: dict[str, str],
) -> list[str]:
    tool = _resolve_tool(argv[0], parent)
    inner = [tool, *argv[1:]]
    try:
        command = container_command(
            inner,
            workspace=workspace,
            skill_root=None,
            home=home,
            config=config,
            binary=Path(tool),
            repo=ROOT,
            unshare_net=True,
        )
    except GradeError as exc:
        raise AdapterError(str(exc), 1) from exc
    command[0] = bwrap
    if "--unshare-net" not in command or str(ROOT.resolve()) in command:
        raise AdapterError("score sandbox is missing the network unshare or includes the repository.", 1)
    return command


def _observer(payload: dict, arm: dict, registry: dict) -> bool:
    spend = format_max_usd(registry["budget"]["max_usd"])
    return (
        arm["id"] == "aic"
        and payload.get("plugin_name") == "aic"
        and payload.get("invokes_model") is False
        and payload.get("api_key_visible") is False
        and payload.get("model") == registry["model"]
        and payload.get("max_turns") == str(registry["budget"]["max_turns"])
        and payload.get("max_budget_usd") == spend
        and payload.get("seed") == str(registry["seed"])
        and payload.get("reference_applied") is True
    )


def _run_stub_arm(registry: dict, arm: dict, workspace: Path, reference: Path, commands: list[list[str]]) -> dict:
    prompt = f"Task id: polyglot-{FIXTURE_SLUG}\nEdit the solution so its tests pass. Do not read outside this workspace.\n"
    mount_path = None if arm["mount_path"] is None else Path(arm["mount_path"])
    argv = agent_argv(
        str(STUB_AGENT),
        prompt=prompt,
        model=registry["model"],
        max_turns=registry["budget"]["max_turns"],
        max_usd=registry["budget"]["max_usd"],
        mount=arm["mount"],
        mount_path=None if arm["mount"] == "installed" else mount_path,
    )
    if "--seed" in argv:
        raise AdapterError("the recorded seed must not be sent as a provider flag.", 2)
    env = _git_env()
    env.update({
        "HOME": arm["home"],
        "AIC_BENCH_SEED": str(registry["seed"]),
        "AICBENCH_BASELINE_STUB": "1",
        "AICBENCH_STUB_REFERENCE": str(reference),
        "AICBENCH_STUB_REMOVE": "[]",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=workspace,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = _parse_payload(completed.stdout or "")
    graded = score_exercise(workspace, commands)
    elapsed = round(time.monotonic() - started, 6)
    treated = _observer(payload, arm, registry)
    cost = cost_text(cost_from_payload(payload))
    passed = (
        completed.returncode == 0
        and graded["passed"]
        and cost == "0"
        and payload.get("api_key_visible") is False
        and (arm["id"] == "aic") == treated
    )
    error = graded["harness_error"]
    if completed.returncode != 0 and error is None:
        error = "stub agent failed."
    if cost != "0" and error is None:
        error = "stub cost was not zero."
    return {
        "aic_treatment": treated,
        "argv": argv,
        "budget": dict(registry["budget"]),
        "cost_usd": cost,
        "exit_code": graded["exit_code"],
        "fetched": True,
        "harness_error": error,
        "invokes_model": False,
        "model": registry["model"],
        "mount": arm["mount"],
        "official_comparison": True,
        "pass_rate": _ratio(1 if passed else 0, 1),
        "passed": passed,
        "passed_cases": 1 if passed else 0,
        "attempted_cases": 1,
        "public_benchmark_scores": None,
        "sandbox": "none",
        "sandboxed": False,
        "seed": registry["seed"],
        "seed_sent_to_provider": False,
        "wall_time_seconds": elapsed,
        "arm": arm["id"],
    }


def _wiring(registry: dict, arm: dict, workspace: Path, root: Path, parent: dict[str, str]) -> dict:
    key = "polyglot-wiring-sentinel"
    bwrap = root / "bwrap"
    bwrap.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    bwrap.chmod(0o755)
    agent = root / "stub-agent.py"
    agent.write_bytes(STUB_AGENT.read_bytes())
    agent.chmod(0o755)
    home = root / "wiring-home"
    config = root / "wiring-config"
    probe = root / "wiring-work"
    for path in (home, config, probe):
        path.mkdir()
    proxies = PhaseProxies(root / "egress")
    try:
        skill = Path(arm["mount_path"]) if arm["mount"] == "plugin-dir" and arm["mount_path"] else None
        install = phase_invocation(
            ["git", "--version"],
            phase="install",
            key=key,
            bwrap=str(bwrap),
            proxies=proxies,
            workspace=probe,
            home=home,
            config=config,
            seed=registry["seed"],
            timeout=30,
            parent=parent,
        )
        agent_phase = phase_invocation(
            agent_argv(
                str(agent),
                prompt="Task id: polyglot-wiring\n",
                model=registry["model"],
                max_turns=registry["budget"]["max_turns"],
                max_usd=registry["budget"]["max_usd"],
                mount=arm["mount"],
                mount_path=skill,
            ),
            phase="agent",
            key=key,
            bwrap=str(bwrap),
            proxies=proxies,
            workspace=probe,
            home=home,
            config=config,
            seed=registry["seed"],
            timeout=30,
            parent=parent,
            skill_root=skill,
        )
        score = score_sandbox_command(
            [sys.executable, "-m", "unittest", "sum_digits_test"],
            workspace=workspace,
            home=home,
            config=config,
            bwrap=str(bwrap),
            parent=parent,
        )
    finally:
        proxies.close()
    if key in json.dumps({"install": install, "agent": agent_phase}):
        raise AdapterError("sandbox summary contains the wiring sentinel.", 1)
    policy = network_policy()
    return {
        "agent_env_has_key": agent_phase["agent_env_has_key"],
        "agent_command_has_key": agent_phase["command_has_key"],
        "agent_unshare_net": agent_phase["unshare_net"],
        "agent_uses_forwarder": agent_phase["uses_forwarder"],
        "install_env_has_key": install["install_env_has_key"],
        "install_unshare_net": install["unshare_net"],
        "repository_mounted": install["command_has_repository"] or agent_phase["command_has_repository"] or str(ROOT.resolve()) in score,
        "score_unshare_net": "--unshare-net" in score,
        "seed_sent_to_provider": install["seed_flag"] or agent_phase["seed_flag"] or "--seed" in score,
        "network": policy,
    }


def run_stub(registry: dict | None = None) -> dict:
    loaded = registry if registry is not None else load_registry()
    pins = load_pins()
    settings = load_pinned()
    stop = shared_stop(settings, loaded["budget"])
    if format_max_usd(loaded["budget"]["max_usd"]) != stop["max_usd"]:
        raise AdapterError("registry max_usd does not match the shared stop.", 2)
    if loaded["model"] != settings["model"] or loaded["seed"] != settings["seed"]:
        raise AdapterError("polyglot model and seed must match the pinned comparison.", 2)
    selected = planned_exercises(pins)
    root = _temp_root("aic-polyglot-stub-")
    prepared = None
    started = time.monotonic()
    try:
        source = root / "source"
        track = write_fixture(source)
        checkout = root / "checkout"
        fetch_track(track, checkout, FIXTURE_SLUG, url=str(source))
        if (checkout / "exercises" / "practice" / "decoy").exists():
            raise AdapterError("sparse fetch materialized an exercise that was not selected.", 1)
        if DECOY_MARKER in "\n".join(
            path.read_text(encoding="utf-8")
            for path in checkout.rglob("*")
            if path.is_file() and not path.is_symlink() and ".git" not in path.parts
        ):
            raise AdapterError("sparse fetch copied an unselected exercise.", 1)
        reference = root / "reference"
        reference.mkdir()
        (reference / "sum_digits.py").write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
        prepared = prepare_stand_in_arms(loaded)
        commands = track["test_commands"]
        arms = []
        for arm in prepared.arms:
            workspace = root / "work" / arm["id"]
            prepare_workspace(checkout, FIXTURE_SLUG, workspace)
            if (workspace / ".meta").exists():
                raise AdapterError("the agent workspace contains exemplar metadata.", 1)
            arms.append(_run_stub_arm(loaded, arm, workspace, reference, commands))
        aic = next(item for item in prepared.arms if item["id"] == "aic")
        wiring = _wiring(loaded, aic, root / "work" / "aic", root, dict(os.environ))
    finally:
        if prepared is not None:
            prepared.close()
        shutil.rmtree(root, ignore_errors=True)
    passed_cases = sum(item["passed_cases"] for item in arms)
    attempted = sum(item["attempted_cases"] for item in arms)
    treated = [item["arm"] for item in arms if item["aic_treatment"] is True]
    ok = (
        treated == ["aic"]
        and [item["arm"] for item in arms] == list(OFFICIAL_IDS)
        and passed_cases == attempted == len(OFFICIAL_IDS)
        and all(item["cost_usd"] == "0" and item["invokes_model"] is False for item in arms)
        and all(item["public_benchmark_scores"] is None for item in arms)
        and wiring["install_unshare_net"]
        and wiring["agent_unshare_net"]
        and wiring["score_unshare_net"]
        and wiring["agent_env_has_key"]
        and not wiring["install_env_has_key"]
        and not wiring["agent_command_has_key"]
        and not wiring["repository_mounted"]
        and not wiring["seed_sent_to_provider"]
    )
    return {
        "arms": [{key: value for key, value in item.items() if key != "argv"} for item in arms],
        "attempted_cases": attempted,
        "budget": dict(loaded["budget"]),
        "checked": pins["checked"],
        "cost_usd": "0" if all(item["cost_usd"] == "0" for item in arms) else None,
        "excluded_arms": ["superpowers"],
        "excluded_sources": [
            {"id": source["id"], "reason": source["reason"], "commit": source["commit"]}
            for source in pins["sources"]
        ],
        "fetched": True,
        "fixture_exercise": FIXTURE_SLUG,
        "invokes_model": False,
        "kind": "aider-polyglot-stub",
        "max_exercises": pins["max_exercises"],
        "model": loaded["model"],
        "official": False,
        "ok": ok,
        "pass_rate": _ratio(passed_cases, attempted),
        "passed_cases": passed_cases,
        "public_benchmark_scores": None,
        "sandbox": "none",
        "sandbox_wiring": wiring,
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "seed": loaded["seed"],
        "seed_sent_to_provider": False,
        "suite": "aider-polyglot",
        "tracks": [
            {
                "commit": track["commit"],
                "commit_date": track["commit_date"],
                "id": track["id"],
                "included": True,
                "license_sha256": track["license_sha256"],
                "license_spdx": track["license_spdx"],
            }
            for track in included_tracks(pins)
        ],
        "upstream_fetched": False,
        "upstream_selection": [
            {"commit": track["commit"], "exercise": slug, "track": track["id"]}
            for track, slug in selected
        ],
        "vendored": False,
        "wall_time_seconds": round(time.monotonic() - started, 6),
        "note": (
            "Local fixture fetch, container command, and unittest only. "
            "The Exercism tracks were not fetched. This is not a public benchmark score. "
            "The process sandbox is none, so the stub can apply its own reference solution."
        ),
    }


def _live_score(track: dict, workspace: Path, *, bwrap: str, parent: dict[str, str], home: Path, config: Path, timeout: int) -> dict:
    commands = []
    for argv in track["test_commands"]:
        try:
            commands.append(
                score_sandbox_command(argv, workspace=workspace, home=home, config=config, bwrap=bwrap, parent=parent)
            )
        except AdapterError as exc:
            return {"exit_code": 127, "harness_error": str(exc), "passed": False, "wall_time_seconds": 0}
    env = _git_env(parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    exit_code = 0
    error = None
    for argv in commands:
        if any("ANTHROPIC_API_KEY" in item for item in argv):
            raise AdapterError("refusing to put the API key on a score command.", 1)
        try:
            completed = subprocess.run(argv, cwd=workspace, env=env, check=False, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            error = "score command exceeded its timeout."
            exit_code = 124
            break
        exit_code = completed.returncode
        if completed.returncode != 0:
            error = "tests failed."
            break
    return {
        "exit_code": exit_code,
        "harness_error": error,
        "passed": error is None and exit_code == 0,
        "wall_time_seconds": round(time.monotonic() - started, 6),
    }


def run_live(parent: dict[str, str], registry: dict | None = None) -> dict:
    key = _key(parent)
    if key is None:
        raise AdapterError(MISSING_KEY, 3)
    bwrap = _require_bwrap(parent)
    loaded = registry if registry is not None else load_registry()
    pins = load_pins()
    settings = load_pinned()
    stop = shared_stop(settings, loaded["budget"])
    if format_max_usd(loaded["budget"]["max_usd"]) != stop["max_usd"]:
        raise AdapterError("registry max_usd does not match the shared stop.", 2)
    selected = planned_exercises(pins)
    if len(selected) != pins["max_exercises"]:
        raise AdapterError("the pinned exercise selection is short.", 2)
    try:
        system_python()
    except OSError as exc:
        raise AdapterError("official polyglot results refuse to run without the egress proxy.", 1) from exc
    root = _temp_root("aic-polyglot-live-")
    proxies = None
    prepared = None
    started = time.monotonic()
    try:
        proxies = PhaseProxies(root / "egress")
        checkouts: dict[tuple[str, str], Path] = {}
        for track, slug in selected:
            home = root / "fetch" / track["id"] / "home"
            config = root / "fetch" / track["id"] / "config"
            scratch = root / "fetch" / track["id"] / "scratch"
            for path in (home, config, scratch):
                path.mkdir(parents=True)
            dest = scratch / "checkout"

            def runner(argv, _home=home, _config=config, _scratch=scratch, **kwargs):
                return _run_in_container(
                    list(argv),
                    workspace=_scratch,
                    home=_home,
                    config=_config,
                    skill_root=None,
                    parent=parent,
                    timeout=kwargs.get("timeout", 180),
                    task=_PhaseTask(),
                    seed=loaded["seed"],
                    key=None,
                    bwrap=bwrap,
                    phase="install",
                    proxies=proxies,
                )

            fetch_track(track, dest, slug, url=github_url(track["repository"]), runner=runner, parent=parent)
            checkouts[(track["id"], slug)] = dest
        prepared = prepare_live_official_arms(parent, loaded)
        receipts = []
        for arm in prepared.arms:
            arm_passed = 0
            arm_started = time.monotonic()
            errors = []
            costs = []
            for track, slug in selected:
                workspace = root / "work" / arm["id"] / slug
                prepare_workspace(checkouts[(track["id"], slug)], slug, workspace)
                prompt = (
                    f"Task id: polyglot-{track['id']}-{slug}\n"
                    "Edit the solution files so the exercise tests pass. "
                    "Do not search outside this workspace.\n"
                )
                mount_path = None if arm["mount_path"] is None else Path(arm["mount_path"])
                argv = agent_argv(
                    "claude",
                    prompt=prompt,
                    model=loaded["model"],
                    max_turns=loaded["budget"]["max_turns"],
                    max_usd=loaded["budget"]["max_usd"],
                    mount=arm["mount"],
                    mount_path=None if arm["mount"] == "installed" else mount_path,
                )
                if key in argv or "--seed" in argv:
                    raise AdapterError("refusing to put the API key or seed on the agent command.", 1)
                skill = mount_path if arm["mount"] == "plugin-dir" else None
                agent_config = root / "agent-config" / arm["id"]
                score_config = root / "score-config" / arm["id"]
                agent_config.mkdir(parents=True, exist_ok=True)
                score_config.mkdir(parents=True, exist_ok=True)
                completed = _run_in_container(
                    argv,
                    workspace=workspace,
                    home=Path(arm["home"]),
                    config=agent_config,
                    skill_root=skill,
                    parent=parent,
                    timeout=loaded["budget"]["timeout_sec"],
                    task=_PhaseTask(),
                    seed=loaded["seed"],
                    key=key,
                    bwrap=bwrap,
                    phase="agent",
                    proxies=proxies,
                )
                payload = _parse_payload(completed.stdout or "")
                costs.append(cost_from_payload(payload))
                graded = _live_score(
                    track,
                    workspace,
                    bwrap=bwrap,
                    parent=parent,
                    home=Path(arm["home"]),
                    config=score_config,
                    timeout=loaded["budget"]["timeout_sec"],
                )
                if graded["passed"] and completed.returncode == 0:
                    arm_passed += 1
                elif graded["harness_error"]:
                    errors.append(graded["harness_error"])
            attempted = len(selected)
            passed = arm_passed == attempted and not errors
            receipts.append({
                "arm": arm["id"],
                "attempted_cases": attempted,
                "budget": dict(loaded["budget"]),
                "cost_usd": cost_text(sum(costs, decimal.Decimal(0))) if costs and all(item is not None for item in costs) else None,
                "fetched": True,
                "harness_error": errors[0] if errors else None,
                "invokes_model": True,
                "model": loaded["model"],
                "official_comparison": True,
                "pass_rate": _ratio(arm_passed, attempted),
                "passed": passed,
                "passed_cases": arm_passed,
                "public_benchmark_scores": None,
                "sandbox": "container",
                "sandboxed": True,
                "seed": loaded["seed"],
                "seed_sent_to_provider": False,
                "wall_time_seconds": round(time.monotonic() - arm_started, 6),
            })
    finally:
        if proxies is not None:
            proxies.close()
        if prepared is not None:
            prepared.close()
        shutil.rmtree(root, ignore_errors=True)
    return {
        "arms": receipts,
        "attempted_cases": sum(item["attempted_cases"] for item in receipts),
        "budget": dict(loaded["budget"]),
        "fetched": True,
        "invokes_model": True,
        "kind": "aider-polyglot-live",
        "model": loaded["model"],
        "network": network_policy(),
        "official": True,
        "ok": all(item["harness_error"] is None for item in receipts),
        "pass_rate": _ratio(sum(item["passed_cases"] for item in receipts), sum(item["attempted_cases"] for item in receipts)),
        "passed_cases": sum(item["passed_cases"] for item in receipts),
        "public_benchmark_scores": None,
        "sandbox": "container",
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "seed": loaded["seed"],
        "seed_sent_to_provider": False,
        "suite": "aider-polyglot",
        "upstream_fetched": True,
        "upstream_selection": [
            {"commit": track["commit"], "exercise": slug, "track": track["id"]}
            for track, slug in selected
        ],
        "vendored": False,
        "wall_time_seconds": round(time.monotonic() - started, 6),
    }


def _write_output(path: Path, report: dict) -> None:
    if path.exists() or path.is_symlink():
        raise AdapterError(f"refusing to overwrite {path}", 3)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "heldout-v2" in text:
        raise AdapterError("refusing to write a polyglot report that names the sealed pack.", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks.polyglot")
    parser.add_argument("command", choices=("stub", "live"))
    parser.add_argument("--output", type=Path)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return 2 if code is None else int(code)
    env = os.environ if environ is None else environ
    try:
        if args.command == "stub":
            report = run_stub()
        elif args.command == "live":
            report = run_live(dict(env))
        else:
            raise AdapterError("unknown polyglot command.", 2)
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            _write_output(args.output, report)
        print(text, end="")
    except AdapterError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
