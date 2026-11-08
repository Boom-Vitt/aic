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
import shutil
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
from benchmarks.aicbench.sandbox import container_command
from benchmarks.budget import ALLOWED_TOOLS, BudgetError, format_max_usd, shared_stop
from benchmarks.baselines.proxy import (
    PROXY_PORT,
    PROXY_URL,
    PhaseProxies,
    network_policy,
    system_python,
    write_forwarder,
)


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"
STUB_AGENT = ROOT / "benchmarks" / "aicbench" / "stub" / "agent.py"
PLUMBING_TASK = "bugfix-ledger-signs"
STAND_IN_MARK = "AIC baseline stub stand-in. Not upstream text."
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_ARM = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MOUNTS = frozenset({"none", "plugin-dir", "installed"})
_INSTALL_STATUSES = frozenset({"none", "documented", "unverified-install"})
_CHECKOUT = "{checkout}"
_SYSTEM_PREFIXES = ("/usr/", "/lib/", "/lib64/", "/bin/", "/sbin/")
_SHIPPED_FILES = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "LICENSE",
    "NOTICE",
    "README.md",
)
_SHIPPED_TREES = ("skills/aic", "src/aic_quickstart")
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
    "install_status",
    "install_commands",
    "install_note",
    "official_comparison",
})
# Live receipts copy this. Install has no secrets. The agent may reach only the model API.
NETWORK = network_policy()
_PROXY_REFUSAL = "official baseline results refuse to run without the egress proxy."


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


_INSTALL_FLAGS = frozenset({"--plugin-dir", "--yes", "--mode", "--scope", "--hooks"})


def _install_commands(entry: dict) -> list[list[str]]:
    commands = entry.get("install_commands")
    if not isinstance(commands, list):
        raise AdapterError(f"{entry.get('id')} install_commands must be a list.", 2)
    parsed: list[list[str]] = []
    for argv in commands:
        if not isinstance(argv, list) or not argv:
            raise AdapterError(f"{entry.get('id')} install command must be a non-empty argv.", 2)
        row: list[str] = []
        for token in argv:
            if not isinstance(token, str) or not token or len(token) > 400 or "\n" in token or "\x00" in token:
                raise AdapterError(f"{entry.get('id')} install command has an invalid token.", 2)
            if token.startswith("-") and token not in _INSTALL_FLAGS:
                raise AdapterError(f"{entry.get('id')} install command has an unexpected flag.", 2)
            if token.startswith("{") and token != _CHECKOUT:
                raise AdapterError(f"{entry.get('id')} install command has an unknown placeholder.", 2)
            row.append(token)
        parsed.append(row)
    return parsed


def _install_contract(entry: dict) -> None:
    status = entry.get("install_status")
    if status not in _INSTALL_STATUSES:
        raise AdapterError(f"{entry.get('id')} install_status is not supported.", 2)
    note = entry.get("install_note")
    if not isinstance(note, str) or "\n" in note or not 8 <= len(note) <= 700:
        raise AdapterError(f"{entry.get('id')} install_note must be one line.", 2)
    commands = _install_commands(entry)
    official = entry.get("official_comparison")
    if status == "none":
        if commands or official is not True:
            raise AdapterError(f"{entry.get('id')} has no install and stays in the comparison.", 2)
    elif status == "unverified-install":
        if not commands or official is not False:
            raise AdapterError(f"{entry.get('id')} unverified install is excluded from official comparisons.", 2)
    elif status == "documented":
        if not commands or official is not True:
            raise AdapterError(f"{entry.get('id')} documented install must stay in the comparison.", 2)
    else:
        raise AdapterError(f"{entry.get('id')} install_status is not supported.", 2)
    flat = [token for argv in commands for token in argv]
    if entry.get("mount") == "plugin-dir" and status == "documented":
        if "--plugin-dir" not in flat or _CHECKOUT not in flat:
            raise AdapterError(f"{entry.get('id')} plugin install must pass --plugin-dir and the checkout.", 2)
    if entry.get("mount") == "installed" and "--plugin-dir" in flat:
        raise AdapterError(f"{entry.get('id')} installed arm must not use --plugin-dir.", 2)
    if entry.get("id") == "gstack" and commands != [["./setup"]]:
        raise AdapterError("gstack install must be ./setup.", 2)
    if entry.get("id") == "ecc":
        expected = [[
            "npx", "--yes", "ecc-universal@2.2.3", "setup",
            "--mode", "claude-plugin", "--scope", "user", "--hooks", "standard", "--yes",
        ]]
        if commands != expected:
            raise AdapterError("ecc install must be the pinned npx setup.", 2)


def _plugin_shape(entry: dict) -> None:
    _relative_path(entry.get("plugin_manifest"), "plugin_manifest")
    if not isinstance(entry.get("plugin_name"), str) or not entry["plugin_name"]:
        raise AdapterError(f"{entry.get('id')} plugin name is required.", 2)
    if "skill_name" in entry or "skill_path" in entry:
        raise AdapterError(f"{entry.get('id')} plugin arm does not use a skill mount.", 2)


def _skill_shape(entry: dict) -> None:
    _relative_path(entry.get("skill_path"), "skill_path")
    if not isinstance(entry.get("skill_name"), str) or not entry["skill_name"]:
        raise AdapterError(f"{entry.get('id')} skill name is required.", 2)
    for field in ("plugin_manifest", "plugin_name", "plugin_version"):
        if field in entry:
            raise AdapterError(f"{entry.get('id')} skill arm does not use a plugin manifest.", 2)


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
    if mount == "plugin-dir" or (mount == "installed" and "plugin_manifest" in entry):
        _plugin_shape(entry)
        if not isinstance(entry.get("plugin_version"), str) or not entry["plugin_version"]:
            raise AdapterError(f"{entry.get('id')} plugin version is required.", 2)
    elif mount == "installed":
        _skill_shape(entry)
    else:
        raise AdapterError(f"{entry.get('id')} git mount must be plugin-dir or installed.", 2)
    _install_contract(entry)


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
    try:
        format_max_usd(spend)
    except BudgetError as exc:
        raise AdapterError(
            "baseline max_usd must be a positive number of cents. Official comparisons do not accept a null dollar cap.",
            2,
        ) from exc
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
        _install_contract(entry)
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
    try:
        expected = shared_stop(settings, registry["budget"])["max_usd"]
        observed = format_max_usd(registry["budget"]["max_usd"])
    except BudgetError as exc:
        raise AdapterError(str(exc), 2) from exc
    if observed != expected:
        raise AdapterError(
            f"baseline max_usd must be the shared stop {expected}. Official comparisons do not accept a null dollar cap.",
            2,
        )


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
    if "plugin_manifest" in entry:
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
    if "plugin_manifest" in entry:
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


def _copy_regular(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise AdapterError(f"refusing to ship a non-regular file: {source.name}", 3)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    os.chmod(target, source.stat().st_mode & 0o777)


def stage_shipped_plugin(dest: Path, root: Path = ROOT) -> None:
    """Copy the wheel and marketplace files. The rest of the checkout stays out."""
    if dest.exists() or dest.is_symlink():
        raise AdapterError("refusing to overwrite the shipped plugin directory.", 3)
    assert_outside_repo(dest, root)
    dest.mkdir(parents=True)
    for relative in _SHIPPED_FILES:
        _copy_regular(root / relative, dest / relative)
    for relative in _SHIPPED_TREES:
        source = root / relative
        if source.is_symlink() or not source.is_dir():
            raise AdapterError(f"shipped tree is missing: {relative}", 1)
        for path in sorted(source.rglob("*")):
            if any(part == "__pycache__" or part.endswith(".pyc") for part in path.relative_to(source).parts):
                continue
            if path.is_symlink():
                raise AdapterError(f"refusing to ship a symlink: {path.relative_to(root)}", 3)
            target = dest / relative / path.relative_to(source)
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                _copy_regular(path, target)
            else:
                raise AdapterError(f"refusing to ship an unsupported file: {path.relative_to(root)}", 3)
    assert_mount_closed(dest, root)


def _answer_roots(repo: Path) -> tuple[Path, ...]:
    routing = repo / "benchmarks" / "routing"
    return (
        repo / "benchmarks" / "aicbench" / "tasks",
        routing / "heldout-v2.json",
        routing / "heldout-v2-answers.json",
    )


def _forbidden(path: Path, repo: Path) -> bool:
    if path == repo or repo in path.parents:
        return True
    for banned in _answer_roots(repo):
        try:
            resolved = banned.resolve()
        except OSError:
            continue
        if path == resolved or resolved in path.parents:
            return True
    return False


def assert_mount_closed(path: Path, repo: Path = ROOT) -> None:
    """The mount must not resolve into this repository or its hidden answers."""
    try:
        resolved = path.resolve()
        repo_resolved = repo.resolve()
    except OSError as exc:
        raise AdapterError(f"cannot resolve a mount: {path}", 3) from exc
    if resolved == repo_resolved or repo_resolved in resolved.parents or resolved in repo_resolved.parents:
        raise AdapterError("refusing to mount the repository.", 3)
    if resolved.is_symlink() or not resolved.is_dir():
        raise AdapterError("a mount must be a real directory.", 3)
    for child in sorted(resolved.rglob("*")):
        if child.is_symlink():
            try:
                target = child.resolve()
            except OSError as exc:
                raise AdapterError("a mount symlink cannot be resolved.", 3) from exc
            if _forbidden(target, repo_resolved) or (target != resolved and resolved not in target.parents):
                raise AdapterError("a mount symlink reaches outside the installed tree.", 3)
            continue
        try:
            real = child.resolve()
        except OSError as exc:
            raise AdapterError("a mounted file cannot be resolved.", 3) from exc
        if _forbidden(real, repo_resolved):
            raise AdapterError(f"a mount reaches a hidden answer path: {child.name}", 3)


def _skill_label(entry: dict) -> str:
    value = entry.get("skill_name") or entry.get("plugin_name") or entry.get("id")
    if not isinstance(value, str) or not value:
        raise AdapterError(f"{entry.get('id')} has no skill label.", 2)
    return value


def _write_home_skill(entry: dict, home: Path) -> Path:
    skill = home / ".claude" / "skills" / _skill_label(entry)
    if skill.exists() or skill.is_symlink():
        raise AdapterError(f"refusing to overwrite a home skill: {entry['id']}", 3)
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {_skill_label(entry)}\n---\n\n{STAND_IN_MARK}\n",
        encoding="utf-8",
    )
    return skill


def concrete_install_commands(entry: dict, checkout: Path | None) -> list[list[str]]:
    commands: list[list[str]] = []
    for argv in entry["install_commands"]:
        row: list[str] = []
        for token in argv:
            if token == _CHECKOUT:
                if checkout is None:
                    raise AdapterError(f"{entry['id']} install is missing its checkout.", 2)
                row.append(str(checkout))
            else:
                row.append(token)
        commands.append(row)
    return commands


def stand_in_mount(entry: dict, dest: Path, home: Path | None = None) -> tuple[str, Path | None]:
    """Prepare one arm without network. Git arms get an AIC-authored stand-in."""
    if entry["kind"] == "builtin" and entry["id"] == "plain-claude-code":
        return "none", None
    if entry["kind"] == "builtin" and entry["id"] == "aic":
        stage_shipped_plugin(dest)
        return "plugin-dir", dest
    if entry["kind"] != "git":
        raise AdapterError(f"unsupported arm: {entry.get('id')}", 2)
    if entry["mount"] == "installed":
        if home is None or home.resolve() == dest.resolve():
            raise AdapterError(f"{entry['id']} installed stand-in needs a separate home.", 2)
        _write_git_standin(entry, dest)
        skill = _write_home_skill(entry, home)
        assert_mount_closed(home)
        assert_mount_closed(dest)
        return "installed", skill
    _write_git_standin(entry, dest)
    assert_mount_closed(dest)
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
    """Fetch a pin. The aic mount is the shipped directory, never the repository root."""
    if entry["kind"] == "builtin" and entry["id"] == "plain-claude-code":
        return "none", None
    if entry["kind"] == "builtin" and entry["id"] == "aic":
        stage_shipped_plugin(dest)
        return "plugin-dir", dest
    fetch_and_verify(entry, dest, runner)
    assert_mount_closed(dest)
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
    max_usd: object,
    mount: str,
    mount_path: Path | None,
) -> list[str]:
    if "\x00" in prompt or "\x00" in binary or "\x00" in model:
        raise AdapterError("refusing a NUL in the agent command.", 2)
    try:
        spend = format_max_usd(max_usd)
    except BudgetError as exc:
        raise AdapterError(str(exc), 2) from exc
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
        ALLOWED_TOOLS,
        "--max-turns",
        str(max_turns),
        "--max-budget-usd",
        spend,
        "--no-session-persistence",
        "--model",
        model,
    ]
    if mount == "none":
        if mount_path is not None:
            raise AdapterError("the plain arm must not receive a mount.", 2)
        return argv
    if mount == "installed":
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


def _scrub_path(value: str, repo: Path = ROOT) -> str:
    repo_resolved = repo.resolve()
    kept = []
    for entry in value.split(os.pathsep):
        if not entry:
            continue
        try:
            resolved = Path(entry).resolve()
        except OSError:
            continue
        if resolved == repo_resolved or repo_resolved in resolved.parents:
            continue
        kept.append(entry)
    return os.pathsep.join(kept)


def _child_env(
    parent: dict[str, str],
    *,
    task,
    seed: int,
    home: Path,
    stub: bool,
    key: str | None,
    config: Path | None = None,
    phase: str | None = None,
) -> dict[str, str]:
    env = {
        "AIC_BENCH_SEED": str(seed),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": parent.get("PATH", "") if stub else _scrub_path(parent.get("PATH", "")),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if config is not None:
        env["CLAUDE_CONFIG_DIR"] = str(config)
    if stub:
        env["AICBENCH_BASELINE_STUB"] = "1"
        env["AICBENCH_STUB_REFERENCE"] = str(task.reference.resolve())
        env["AICBENCH_STUB_REMOVE"] = json.dumps(list(task.remove))
        return env
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["TMPDIR"] = "/tmp"
    env.update({
        "HTTP_PROXY": PROXY_URL,
        "HTTPS_PROXY": PROXY_URL,
        "ALL_PROXY": PROXY_URL,
        "http_proxy": PROXY_URL,
        "https_proxy": PROXY_URL,
        "all_proxy": PROXY_URL,
        "NO_PROXY": "",
        "no_proxy": "",
    })
    if phase == "install":
        if "ANTHROPIC_API_KEY" in env or (key and any(key in value for value in env.values())):
            raise AdapterError("install phase environment contains a secret.", 1)
        return env
    if phase != "agent":
        raise AdapterError(_PROXY_REFUSAL, 1)
    if not key:
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    env["ANTHROPIC_API_KEY"] = key
    return env


def _require_bwrap(parent: dict[str, str]) -> str:
    found = shutil.which("bwrap", path=parent.get("PATH"))
    if not found:
        raise AdapterError(
            "Container sandbox requires bubblewrap (bwrap) on PATH. "
            "Without it, a live baseline cannot hide the checkout from the agent filesystem. "
            "official baseline results refuse sandbox none.",
            1,
        )
    return found


def _resolve_tool(name: str, parent: dict[str, str]) -> str:
    if name.startswith("/"):
        candidate = Path(name)
    else:
        found = shutil.which(name, path=_scrub_path(parent.get("PATH", "")))
        if not found:
            raise AdapterError(f"command not found for the sandbox: {name}", 1)
        candidate = Path(found)
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise AdapterError(f"cannot resolve sandbox command: {name}", 1) from exc
    if not resolved.is_file():
        raise AdapterError(f"sandbox command is not a file: {name}", 1)
    return str(resolved)


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


def _blank_receipt(
    entry: dict,
    registry: dict,
    *,
    invokes_model: bool,
    seconds: float,
    error: str,
    sandbox: str,
    excluded: bool = False,
) -> dict:
    return {
        "arm": entry["id"],
        "budget": dict(registry["budget"]),
        "commit": entry.get("commit"),
        "copyright_notice": entry.get("copyright_notice"),
        "cost_usd": None,
        "excluded": excluded,
        "exit_code": None,
        "fetch_commands": [],
        "fetched": False,
        "harness_error": error[:500],
        "install_commands": entry.get("install_commands") or [],
        "install_note": entry.get("install_note"),
        "install_status": entry.get("install_status"),
        "invalid": True,
        "invokes_model": False if excluded else invokes_model,
        "license_spdx": entry.get("license_spdx"),
        "model": registry["model"],
        "mount": entry["mount"],
        "official_comparison": False if excluded else entry.get("official_comparison"),
        "passed": False,
        "prompt_sha256": None,
        "public_benchmark_scores": None,
        "repository": entry.get("repository"),
        "network": NETWORK if sandbox == "container" else None,
        "sandbox": sandbox,
        "sandboxed": False,
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
    if payload.get("home_skill") not in {True, False}:
        return "stub did not report whether HOME contained a skill."
    if mount == "none":
        if payload.get("plugin_dir") is not None or payload.get("add_dir") is not None or payload.get("home_skill"):
            return "plain arm received a mount."
        return None
    expected = None if mount_path is None else str(mount_path)
    if mount == "plugin-dir":
        if payload.get("plugin_dir") != expected or payload.get("add_dir") is not None or payload.get("home_skill"):
            return "plugin mount was not visible to the stub."
        if payload.get("plugin_name") != entry.get("plugin_name"):
            return "stub read a different plugin name."
        return None
    if mount == "installed":
        if payload.get("plugin_dir") is not None or payload.get("add_dir") is not None:
            return "installed arm received a directory flag."
        if payload.get("home_skill") is not True or payload.get("home_skill_name") != _skill_label(entry):
            return "installed arm did not see its stand-in skill in HOME."
        return None
    if mount == "add-dir":
        if payload.get("add_dir") != expected or payload.get("plugin_dir") is not None:
            return "add-dir mount was not visible to the stub."
        if payload.get("skill_stand_in") is not True:
            return "stub did not see the stand-in skill marker."
        return None
    return f"unknown mount: {mount}"


def _tool_binds(argv: list[str], roots: tuple[Path, ...]) -> tuple[str, ...]:
    mounted = []
    for root in roots:
        try:
            mounted.append(root.resolve())
        except OSError:
            continue
    binds: list[str] = []
    repo = ROOT.resolve()
    for item in argv:
        if not item.startswith("/"):
            continue
        candidate = Path(item)
        if not candidate.is_file() and not candidate.is_symlink():
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        text = str(resolved)
        if text.startswith(_SYSTEM_PREFIXES) or resolved == repo or repo in resolved.parents:
            continue
        if any(resolved == root or root in resolved.parents for root in mounted):
            continue
        if text not in binds:
            binds.append(text)
    return tuple(binds)


def _run_in_container(
    argv: list[str],
    *,
    workspace: Path,
    home: Path,
    config: Path,
    skill_root: Path | None,
    parent: dict[str, str],
    timeout: int,
    task,
    seed: int,
    key: str | None,
    bwrap: str,
    phase: str,
    proxies: PhaseProxies,
) -> subprocess.CompletedProcess:
    if proxies is None or phase not in {"install", "agent"}:
        raise AdapterError(_PROXY_REFUSAL, 1)
    if not argv or any("\x00" in item for item in argv):
        raise AdapterError("refusing an unsafe sandbox command.", 2)
    try:
        python = system_python()
        socket_path = proxies.socket_for(phase)
    except (OSError, ValueError) as exc:
        raise AdapterError(_PROXY_REFUSAL, 1) from exc
    binary = _resolve_tool(argv[0], parent)
    real = [binary, *argv[1:]]
    forwarder = write_forwarder(workspace)
    inner = [python, str(forwarder), str(socket_path), str(PROXY_PORT), "--", *real]
    for path in (workspace, home, config):
        assert_mount_closed(path)
    if skill_root is not None:
        assert_mount_closed(skill_root)
    proxy_dir = str(socket_path.parent.resolve())
    try:
        command = container_command(
            inner,
            workspace=workspace,
            skill_root=skill_root,
            home=home,
            config=config,
            binary=Path(python),
            repo=ROOT,
            unshare_net=True,
            extra_binds=((proxy_dir, proxy_dir),),
            extra_ro_binds=_tool_binds(real, (workspace, home, config, skill_root) if skill_root else (workspace, home, config)),
        )
    except GradeError as exc:
        raise AdapterError(str(exc), 1) from exc
    command[0] = bwrap
    if "--unshare-net" not in command or str(ROOT.resolve()) in [str(item) for item in command]:
        raise AdapterError("sandbox command is missing the network unshare or includes the repository.", 1)
    if key and key in command:
        raise AdapterError("refusing to put the API key on a command line.", 1)
    env = _child_env(
        parent, task=task, seed=seed, home=home, stub=False, key=key, config=config, phase=phase,
    )
    return subprocess.run(
        command,
        cwd=str(workspace),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _gstack_dest(home: Path) -> Path:
    return home / ".claude" / "skills" / "gstack"


def _check_completed(entry: dict, completed: subprocess.CompletedProcess, label: str) -> None:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or label).strip()
        raise AdapterError(f"{entry['id']} {label} failed: {detail[:300]}", 1)


def _prepare_live(
    entry: dict,
    checkout: Path,
    home: Path,
    config: Path,
    scratch: Path,
    *,
    parent: dict[str, str],
    task,
    seed: int,
    bwrap: str,
    timeout: int,
    proxies: PhaseProxies,
) -> tuple[str, Path | None, bool, list[list[str]], list[list[str]]]:
    if entry["id"] == "plain-claude-code":
        return "none", None, False, [], []
    if entry["id"] == "aic":
        stage_shipped_plugin(checkout)
        return "plugin-dir", checkout, False, concrete_install_commands(entry, checkout), []

    def runner(argv, **kwargs):
        return _run_in_container(
            list(argv),
            workspace=scratch,
            home=home,
            config=config,
            skill_root=None,
            parent=parent,
            timeout=kwargs.get("timeout", 180),
            task=task,
            seed=seed,
            key=None,
            bwrap=bwrap,
            phase="install",
            proxies=proxies,
        )

    fetch_dest = scratch / "repo"
    if entry["id"] == "gstack":
        fetch_dest = _gstack_dest(home)
        fetch_dest.parent.mkdir(parents=True, exist_ok=True)
    fetch_commands = git_fetch_commands(entry["repository"], entry["commit"], fetch_dest)
    fetch_and_verify(entry, fetch_dest, runner)
    if entry["mount"] == "plugin-dir":
        commands = concrete_install_commands(entry, fetch_dest)
        return "plugin-dir", fetch_dest, True, commands, fetch_commands
    commands = concrete_install_commands(entry, None)
    for argv in commands:
        if argv == ["./setup"]:
            script = fetch_dest / "setup"
            if script.is_symlink() or not script.is_file():
                raise AdapterError(f"{entry['id']} setup script is missing at the pin.", 3)
            completed = _run_in_container(
                ["/bin/bash", str(script)],
                workspace=scratch,
                home=home,
                config=config,
                skill_root=None,
                parent=parent,
                timeout=timeout,
                task=task,
                seed=seed,
                key=None,
                bwrap=bwrap,
                phase="install",
                proxies=proxies,
            )
            _check_completed(entry, completed, "setup")
            continue
        if argv[0] == "npx":
            completed = _run_in_container(
                argv,
                workspace=scratch,
                home=home,
                config=config,
                skill_root=None,
                parent=parent,
                timeout=timeout,
                task=task,
                seed=seed,
                key=None,
                bwrap=bwrap,
                phase="install",
                proxies=proxies,
            )
            _check_completed(entry, completed, "install")
            continue
        if argv[0] in {"claude", "/plugin"}:
            raise AdapterError(f"{entry['id']} install is not a separate sandbox command.", 2)
        raise AdapterError(f"{entry['id']} install command cannot be reproduced.", 2)
    return "installed", fetch_dest if entry["id"] == "gstack" else None, True, commands, fetch_commands


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
    sandbox: str = "none",
) -> dict:
    prompt = _prompt(task)
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    expected = sha256_manifest(protected_bytes(task))
    receipts = []
    with tempfile.TemporaryDirectory(prefix="aic-baselines-", dir=outside_repository_temp()) as temporary:
        root = Path(temporary)
        bwrap = ""
        proxies = None
        if sandbox == "container":
            bwrap = _require_bwrap(parent_env)
            try:
                system_python()
                proxies = PhaseProxies(root / "egress")
            except OSError as exc:
                raise AdapterError(_PROXY_REFUSAL, 1) from exc
        try:
            for entry in registry["arms"]:
                started = time.perf_counter()
                arm_root = root / entry["id"]
                home = arm_root / "home"
                config = arm_root / "config"
                scratch = arm_root / "scratch"
                checkout = arm_root / "checkout"
                workspace = arm_root / "workspace"
                home.mkdir(parents=True)
                config.mkdir()
                scratch.mkdir()
                if invokes_model and entry.get("official_comparison") is not True:
                    receipts.append(
                        _blank_receipt(
                            entry,
                            registry,
                            invokes_model=False,
                            seconds=0,
                            error=str(entry.get("install_note") or "unverified-install"),
                            sandbox=sandbox,
                            excluded=True,
                        )
                    )
                    continue
                fetched = False
                install_commands: list[list[str]] = []
                fetch_commands: list[list[str]] = []
                sandboxed = False
                try:
                    if invokes_model:
                        mount, mount_path, fetched, install_commands, fetch_commands = _prepare_live(
                            entry,
                            checkout,
                            home,
                            config,
                            scratch,
                            parent=parent_env,
                            task=task,
                            seed=registry["seed"],
                            bwrap=bwrap,
                            timeout=registry["budget"]["timeout_sec"],
                            proxies=proxies,
                        )
                    else:
                        mount, mount_path = materialize(entry, checkout, home)
                        needs_checkout = any(
                            token == _CHECKOUT for argv in entry["install_commands"] for token in argv
                        )
                        install_commands = concrete_install_commands(entry, checkout if needs_checkout else None)
                    if key and mount_path is not None and key in str(mount_path):
                        raise AdapterError("refusing to put the API key in a path.", 1)
                    if mount_path is not None:
                        assert_mount_closed(mount_path)
                    prepare_workspace(task, workspace, solution=False)
                    assert_mount_closed(workspace)
                    argv = agent_argv(
                        binary,
                        prompt=prompt,
                        model=registry["model"],
                        max_turns=registry["budget"]["max_turns"],
                        max_usd=registry["budget"]["max_usd"],
                        mount=mount,
                        mount_path=None if mount == "installed" else mount_path,
                    )
                    if key and key in argv:
                        raise AdapterError("refusing to put the API key on a command line.", 1)
                    if ALLOWED_TOOLS not in argv:
                        raise AdapterError("agent command dropped the shared tool list.", 1)
                    if "--max-budget-usd" not in argv:
                        raise AdapterError("agent command dropped the shared dollar cap.", 1)
                    env = _child_env(
                        parent_env,
                        task=task,
                        seed=registry["seed"],
                        home=home,
                        stub=not invokes_model,
                        key=key,
                        config=config,
                        phase="agent" if invokes_model else None,
                    )
                    if sandbox == "container":
                        completed = _run_in_container(
                            argv,
                            workspace=workspace,
                            home=home,
                            config=config,
                            skill_root=mount_path if mount == "plugin-dir" else None,
                            parent=parent_env,
                            timeout=registry["budget"]["timeout_sec"],
                            task=task,
                            seed=registry["seed"],
                            key=key,
                            bwrap=bwrap,
                            phase="agent",
                            proxies=proxies,
                        )
                        sandboxed = True
                    else:
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
                            sandbox=sandbox,
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
                            sandbox=sandbox,
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
                    if payload.get("max_budget_usd") != format_max_usd(registry["budget"]["max_usd"]):
                        harness_error = harness_error or "stub did not observe the shared dollar cap."
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
                        "excluded": False,
                        "exit_code": completed.returncode,
                        "fetch_commands": fetch_commands,
                        "fetched": fetched,
                        "harness_error": harness_error,
                        "install_commands": install_commands,
                        "install_note": entry.get("install_note"),
                        "install_status": entry.get("install_status"),
                        "invalid": invalid,
                        "invokes_model": invokes_model,
                        "license_spdx": entry.get("license_spdx"),
                        "model": registry["model"],
                        "mount": mount,
                        "official_comparison": entry.get("official_comparison"),
                        "passed": passed,
                        "prompt_sha256": prompt_sha,
                        "public_benchmark_scores": None,
                        "repository": entry.get("repository"),
                        "sandbox": sandbox,
                        "sandboxed": sandboxed,
                        "seed": registry["seed"],
                        "wall_time_seconds": elapsed,
                        "network": NETWORK if sandbox == "container" else None,
                    }
                )
        finally:
            if proxies is not None:
                proxies.close()
    compared = [item for item in receipts if item.get("excluded") is not True]
    ok = bool(compared) and all(
        item["passed"] is True and item["public_benchmark_scores"] is None for item in compared
    )
    if not invokes_model:
        ok = ok and all(item["cost_usd"] == "0" and item["fetched"] is False for item in compared)
    official = sandbox == "container" and invokes_model
    return {
        "agent": "benchmarks/aicbench/stub/agent.py" if not invokes_model else binary,
        "budget": dict(registry["budget"]),
        "excluded_arms": [item["arm"] for item in receipts if item.get("excluded") is True],
        "invokes_model": invokes_model,
        "kind": kind,
        "measured": False,
        "model": registry["model"],
        "network": NETWORK if official else None,
        "note": (
            "Stub agent and oracle only. A pass here proves the adapter, the mount, and the grader. "
            "It is not a public benchmark score. The sandbox is none, so the stub can read the reference."
            if not invokes_model
            else "Live install and agent phases ran in a network-unshared bubblewrap container behind an "
            "allow-list CONNECT proxy. This report is not a public benchmark score. "
            "Unverified installs are excluded."
        ),
        "official": official,
        "ok": ok,
        "public_benchmark_scores": None,
        "receipts": receipts,
        "sample_size": 1,
        "sandbox": sandbox,
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
        sandbox="none",
    )
    if report["sandbox"] != "none" or report["official"] is not False:
        raise AdapterError("the stub proof stays unofficial.", 1)
    if report["public_benchmark_scores"] is not None:
        raise AdapterError("stub report must leave public scores null.", 1)
    return report


def run_live(
    parent: dict[str, str],
    *,
    binary: str = "claude",
    task_id: str = PLUMBING_TASK,
    registry: dict | None = None,
    sandbox: str = "container",
) -> dict:
    if sandbox != "container":
        raise AdapterError("official baseline results refuse sandbox none.", 2)
    key = _key(parent)
    if key is None:
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    _require_bwrap(parent)
    loaded = registry if registry is not None else load_registry()
    report = execute_arms(
        loaded,
        _task(task_id),
        binary=binary,
        parent_env=parent,
        materialize=stand_in_mount,
        kind="baseline-live",
        invokes_model=True,
        key=key,
        sandbox="container",
    )
    if report["sandbox"] != "container" or report["official"] is not True or report["public_benchmark_scores"] is not None:
        raise AdapterError("official baseline results refuse sandbox none.", 1)
    return report


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
    parser.add_argument("--model", default=None)
    parser.add_argument("--sandbox", choices=("none", "container"), default=None)
    parser.add_argument("--official", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return 2 if code is None else int(code)
    parent = os.environ if environ is None else environ
    try:
        loaded = load_registry()
        if args.model is not None and args.model != loaded["model"]:
            raise AdapterError("baseline --model must match benchmarks/pinned.json.", 2)
        if args.command == "stub":
            if args.official or args.sandbox not in {None, "none"}:
                raise AdapterError("the stub proof stays unofficial and uses sandbox none.", 2)
            if args.task != PLUMBING_TASK:
                raise AdapterError("the stub proof runs one plumbing task.", 2)
            report = run_stub(parent)
        else:
            if args.sandbox not in {None, "container"}:
                raise AdapterError("official baseline results refuse sandbox none.", 2)
            report = run_live(parent, binary=args.claude_bin, task_id=args.task, sandbox="container")
        _emit(report, args.output)
    except AdapterError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    return 0 if report.get("ok") else 1
