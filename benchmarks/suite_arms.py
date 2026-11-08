"""Load the official comparison arms into the pinned suite adapters.

The key-free stub stages mounts and runs the local stub agent. It does not
fetch a third-party repository, call a model, or start Terminal-Bench or
SWE-bench. A live run may fetch through the two-phase egress proxy. Receipts
set ``aic_treatment`` only when a process actually saw the AIC plugin.
``public_benchmark_scores`` stays null.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from benchmarks.baselines.adapter import (
    ROOT,
    STUB_AGENT,
    AdapterError,
    _key,
    _prepare_live,
    _require_bwrap,
    _task,
    agent_argv,
    load_registry,
    stand_in_mount,
)
from benchmarks.baselines.proxy import PhaseProxies
from benchmarks.budget import format_max_usd, shared_stop
from benchmarks.aicbench.grading import GradeError, outside_repository_temp
from benchmarks.swe_bench.contract import ContractError, claude_command


PINNED = ROOT / "benchmarks" / "pinned.json"
TERMINAL_IMPORT = "benchmarks.terminal_bench.claude_agent:RegistryClaudeAgent"
OFFICIAL_IDS = (
    "plain-claude-code",
    "aic",
    "ecc",
    "agent-skills",
    "planning-with-files",
    "gstack",
)
_KW = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_WIRING_PROMPT = "Suite arm wiring check. Do not call a model. Do not fetch a repository."


class ArmSet:
    def __init__(self, root: Path, arms: list[dict], cleanup) -> None:
        self.root = root
        self.arms = arms
        self._cleanup = cleanup

    def close(self) -> None:
        self._cleanup()


def load_pinned() -> dict:
    if PINNED.is_symlink():
        raise AdapterError("refusing a symlinked pin file.", 3)
    try:
        value = json.loads(PINNED.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError("pinned settings are unreadable.", 1) from exc
    if not isinstance(value, dict):
        raise AdapterError("pinned settings must be an object.", 1)
    return value


def official_entries(registry: dict) -> list[dict]:
    arms = registry.get("arms")
    if not isinstance(arms, list):
        raise AdapterError("baseline registry has no arms.", 2)
    selected = [item for item in arms if isinstance(item, dict) and item.get("official_comparison") is True]
    ids = [item.get("id") for item in selected]
    if ids != list(OFFICIAL_IDS):
        raise AdapterError("official comparison arms must be the six registered arms, without superpowers.", 2)
    excluded = [item.get("id") for item in arms if isinstance(item, dict) and item.get("official_comparison") is not True]
    if excluded != ["superpowers"]:
        raise AdapterError("superpowers stays unverified and is the only excluded arm.", 2)
    return selected


def _temp_root(prefix: str) -> Path:
    try:
        parent = outside_repository_temp()
    except GradeError as exc:
        raise AdapterError(str(exc), 1) from exc
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def _remove_tree(path: Path) -> None:
    if path.exists() or path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)


def prepare_stand_in_arms(registry: dict | None = None) -> ArmSet:
    """Stage local fixtures. Git arms are AIC-authored stand-ins, not upstream trees."""
    loaded = registry if registry is not None else load_registry()
    root = _temp_root("aic-suite-standin-")
    arms: list[dict] = []
    try:
        for entry in official_entries(loaded):
            home = root / entry["id"] / "home"
            checkout = root / entry["id"] / "checkout"
            home.mkdir(parents=True)
            mount, path = stand_in_mount(entry, checkout, home)
            arms.append(_prepared(entry, mount, path, home, fetched=False))
    except Exception:
        _remove_tree(root)
        raise
    return ArmSet(root, arms, lambda: _remove_tree(root))


def prepare_live_official_arms(parent: dict[str, str], registry: dict | None = None) -> ArmSet:
    """Fetch official git arms inside the install-phase proxy. The API key stays out of that phase."""
    key = _key(parent)
    if key is None:
        raise AdapterError("ANTHROPIC_API_KEY is required.", 3)
    bwrap = _require_bwrap(parent)
    loaded = registry if registry is not None else load_registry()
    task = _task("bugfix-ledger-signs")
    root = _temp_root("aic-suite-live-")
    proxies = None
    try:
        proxies = PhaseProxies(root / "egress")
        arms: list[dict] = []
        for entry in official_entries(loaded):
            home = root / entry["id"] / "home"
            config = root / entry["id"] / "config"
            scratch = root / entry["id"] / "scratch"
            checkout = root / entry["id"] / "checkout"
            for path in (home, config, scratch):
                path.mkdir(parents=True)
            mount, path, fetched, _installs, _fetches = _prepare_live(
                entry,
                checkout,
                home,
                config,
                scratch,
                parent=parent,
                task=task,
                seed=loaded["seed"],
                bwrap=bwrap,
                timeout=loaded["budget"]["timeout_sec"],
                proxies=proxies,
            )
            if key in str(path or "") or key in str(home):
                raise AdapterError("refusing to put the API key in a mount path.", 1)
            arms.append(_prepared(entry, mount, path, home, fetched=fetched))
    except Exception:
        if proxies is not None:
            proxies.close()
        _remove_tree(root)
        raise
    proxies.close()
    return ArmSet(root, arms, lambda: _remove_tree(root))


def _prepared(entry: dict, mount: str, path: Path | None, home: Path, *, fetched: bool) -> dict:
    return {
        "id": entry["id"],
        "mount": mount,
        "mount_path": None if path is None else str(path),
        "home": str(home),
        "fetched": fetched,
        "install_commands": entry.get("install_commands") or [],
        "entry": entry,
    }


def _kw(key: str, value: str) -> str:
    if _KW.fullmatch(key) is None or not value or any(character.isspace() or character in "=\x00" for character in value):
        raise AdapterError(f"refusing an unsafe agent kwarg: {key}.", 2)
    return f"{key}={value}"


def terminal_argv(settings: dict, registry: dict, arm: dict, output: Path, run_id: str) -> list[str]:
    pin = settings["terminal_bench"]
    budget = registry["budget"]
    spend = format_max_usd(budget["max_usd"])
    model = settings["model"]
    if model != registry["model"]:
        raise AdapterError("suite model drifted from the baseline registry.", 2)
    command = [
        sys.executable,
        "-m",
        "terminal_bench.cli.tb.main",
        "run",
        "--dataset",
        pin["dataset"],
        "--agent-import-path",
        TERMINAL_IMPORT,
        "--model",
        f"anthropic/{model}",
        "--n-tasks",
        str(pin["n_tasks"]),
        "--n-attempts",
        str(pin["n_attempts"]),
        "--n-concurrent",
        "1",
        "--global-agent-timeout-sec",
        str(budget["timeout_sec"]),
        "--output-path",
        str(output),
        "--run-id",
        run_id,
        "--agent-kwarg",
        _kw("arm_id", arm["id"]),
        "--agent-kwarg",
        _kw("mount", arm["mount"]),
        "--agent-kwarg",
        _kw("max_turns", str(budget["max_turns"])),
        "--agent-kwarg",
        _kw("max_budget_usd", spend),
        "--agent-kwarg",
        _kw("seed", str(registry["seed"])),
    ]
    if arm["mount"] == "plugin-dir":
        if not arm["mount_path"]:
            raise AdapterError(f"{arm['id']} plugin mount is missing.", 2)
        command.extend(["--agent-kwarg", _kw("plugin_dir", arm["mount_path"])])
    elif arm["mount"] == "installed":
        command.extend(["--agent-kwarg", _kw("home_dir", arm["home"])])
    elif arm["mount"] != "none":
        raise AdapterError(f"unsupported suite mount: {arm['mount']}.", 2)
    return command


def swe_agent_argv(registry: dict, arm: dict) -> list[str]:
    budget = registry["budget"]
    plugin = Path(arm["mount_path"]) if arm["mount"] == "plugin-dir" else None
    if plugin is not None and (plugin == ROOT or ROOT in plugin.parents):
        raise AdapterError("SWE-bench Lite refuses to mount the repository.", 2)
    try:
        return claude_command(
            prompt=_WIRING_PROMPT,
            plugin_dir=plugin,
            model=registry["model"],
            max_turns=budget["max_turns"],
            max_budget_usd=format_max_usd(budget["max_usd"]),
        )
    except ContractError as exc:
        raise AdapterError(str(exc), 2) from exc


def _observe_one(registry: dict, arm: dict, reference: Path, scratch: Path) -> dict:
    entry = arm["entry"]
    mount_path = None if arm["mount_path"] is None else Path(arm["mount_path"])
    prompt = f"Task id: suite-arm-{arm['id']}\n{_WIRING_PROMPT}\n"
    argv = agent_argv(
        str(STUB_AGENT),
        prompt=prompt,
        model=registry["model"],
        max_turns=registry["budget"]["max_turns"],
        max_usd=registry["budget"]["max_usd"],
        mount=arm["mount"],
        mount_path=None if arm["mount"] == "installed" else mount_path,
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": arm["home"],
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "AIC_BENCH_SEED": str(registry["seed"]),
        "AICBENCH_BASELINE_STUB": "1",
        "AICBENCH_STUB_REFERENCE": str(reference),
        "AICBENCH_STUB_REMOVE": "[]",
    }
    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=scratch,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload: dict = {}
    if completed.returncode == 0 and completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
    plugin_name = payload.get("plugin_name")
    observer = (
        arm["id"] == "aic"
        and plugin_name == "aic"
        and payload.get("invokes_model") is False
        and payload.get("api_key_visible") is False
        and payload.get("model") == registry["model"]
        and payload.get("max_turns") == str(registry["budget"]["max_turns"])
        and payload.get("max_budget_usd") == format_max_usd(registry["budget"]["max_usd"])
        and payload.get("seed") == str(registry["seed"])
    )
    return {
        "payload": payload,
        "observer_loaded_aic": observer,
        "exit_code": completed.returncode,
        "argv": argv,
    }


def observe_arms(
    prepared: ArmSet,
    settings: dict,
    registry: dict,
    *,
    run_id: str,
    output_root: Path | None = None,
) -> list[dict]:
    reference = prepared.root / "reference"
    scratch = prepared.root / "scratch"
    reference.mkdir(exist_ok=True)
    scratch.mkdir(exist_ok=True)
    spend = format_max_usd(registry["budget"]["max_usd"])
    records = []
    terminal_root = output_root or (prepared.root / "terminal-output")
    for arm in prepared.arms:
        seen = _observe_one(registry, arm, reference, scratch)
        output = terminal_root / arm["id"]
        terminal = terminal_argv(settings, registry, arm, output, f"{run_id}-{arm['id']}")
        swe = swe_agent_argv(registry, arm)
        records.append(
            {
                "arm": arm["id"],
                "aic_treatment": seen["observer_loaded_aic"],
                "observer_loaded_aic": seen["observer_loaded_aic"],
                "harness_loaded_aic": False,
                "budget": dict(registry["budget"]),
                "exit_code": seen["exit_code"],
                "fetched": arm["fetched"],
                "install_commands": arm["install_commands"],
                "invokes_model": False,
                "model": registry["model"],
                "mount": arm["mount"],
                "observer_plugin_name": seen["payload"].get("plugin_name"),
                "official_comparison": True,
                "public_benchmark_scores": None,
                "seed": registry["seed"],
                "seed_sent_to_provider": False,
                "swe_bench_command": swe,
                "terminal_bench_command": terminal,
                "max_usd": spend,
            }
        )
    return records


def apply_harness_marker(record: dict, output: Path) -> None:
    loaded = _marker_loaded(output, record["arm"])
    record["harness_loaded_aic"] = loaded
    record["aic_treatment"] = bool(record["observer_loaded_aic"] or loaded)


def _marker_loaded(output: Path, arm_id: str) -> bool:
    if not output.is_dir() or output.is_symlink():
        return False
    found = []
    for path in sorted(output.rglob("arm-load.json")):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            found.append(data)
    if len(found) != 1:
        return False
    data = found[0]
    return (
        arm_id == "aic"
        and data.get("arm") == "aic"
        and data.get("loaded") is True
        and data.get("plugin_name") == "aic"
        and data.get("install_has_api_key") is False
    )


def _command_problem(record: dict, registry: dict) -> str | None:
    spend = format_max_usd(registry["budget"]["max_usd"])
    model = registry["model"]
    turns = str(registry["budget"]["max_turns"])
    terminal = record["terminal_bench_command"]
    swe = record["swe_bench_command"]
    if terminal[terminal.index("--model") + 1] != f"anthropic/{model}":
        return "terminal-bench model drifted."
    if terminal[terminal.index("--global-agent-timeout-sec") + 1] != str(registry["budget"]["timeout_sec"]):
        return "terminal-bench timeout drifted."
    if f"max_budget_usd={spend}" not in terminal or f"max_turns={turns}" not in terminal:
        return "terminal-bench budget drifted."
    if swe[swe.index("--model") + 1] != model:
        return "swe-bench model drifted."
    if swe[swe.index("--max-turns") + 1] != turns or swe[swe.index("--max-budget-usd") + 1] != spend:
        return "swe-bench budget drifted."
    if "--seed" in swe or "--seed" in terminal:
        return "the recorded seed must not be sent as a provider flag."
    plugin_flags = [swe[index + 1] for index, item in enumerate(swe) if item == "--plugin-dir"]
    if any(flag == str(ROOT) or flag.startswith(str(ROOT) + os.sep) for flag in plugin_flags):
        return "a suite command mounted the repository."
    if record["arm"] == "plain-claude-code":
        if plugin_flags or "plugin_dir=" in " ".join(terminal):
            return "the plain arm received a plugin."
    if record["arm"] == "aic":
        if len(plugin_flags) != 1 or plugin_flags[0] == str(ROOT) or not record["observer_loaded_aic"]:
            return "the aic arm did not load the shipped plugin."
        if "plugin_dir=" not in " ".join(terminal):
            return "terminal-bench did not receive the aic plugin directory."
    elif record["observer_loaded_aic"]:
        return f"{record['arm']} was recorded as the AIC treatment."
    if record["arm"] not in {"aic", "agent-skills", "planning-with-files"} and plugin_flags:
        return f"{record['arm']} swe command received a plugin directory."
    return None


def run_stub(registry: dict | None = None) -> dict:
    loaded = registry if registry is not None else load_registry()
    settings = load_pinned()
    stop = shared_stop(settings, loaded["budget"])
    if format_max_usd(loaded["budget"]["max_usd"]) != stop["max_usd"]:
        raise AdapterError("registry max_usd does not match the shared stop.", 2)
    prepared = prepare_stand_in_arms(loaded)
    try:
        arms = observe_arms(prepared, settings, loaded, run_id="suite-arm-stub")
    finally:
        prepared.close()
    problems = [problem for record in arms if (problem := _command_problem(record, loaded))]
    treated = [record["arm"] for record in arms if record["aic_treatment"] is True]
    ok = (
        not problems
        and treated == ["aic"]
        and [record["arm"] for record in arms] == list(OFFICIAL_IDS)
        and all(record["fetched"] is False and record["invokes_model"] is False for record in arms)
        and all(record["public_benchmark_scores"] is None for record in arms)
        and all(record["harness_loaded_aic"] is False for record in arms)
        and all(record["budget"] == loaded["budget"] for record in arms)
    )
    return {
        "arms": arms,
        "budget": dict(loaded["budget"]),
        "budget_rule": (
            "Stop rule, not a predicted cost. "
            f"Input allowance is max_turns times timeout_sec ({stop['input_token_allowance']} tokens). "
            f"Output allowance is max_turns times pinned max_tokens ({stop['output_token_allowance']} tokens). "
            f"Priced at {stop['input_usd_per_million']} and {stop['output_usd_per_million']} USD per million. "
            f"Exact millionths {stop['exact_usd_millionths']}, sent cap {stop['max_usd']}."
        ),
        "excluded_arms": ["superpowers"],
        "fetched": False,
        "harness_invoked": False,
        "invokes_model": False,
        "kind": "suite-arm-stub",
        "model": loaded["model"],
        "official": False,
        "ok": ok,
        "problems": problems,
        "public_benchmark_scores": None,
        "revisions": {
            "swe-bench-lite": settings["swe_bench_lite"]["revision"],
            "terminal-bench": settings["terminal_bench"]["revision"],
        },
        "sandbox": "none",
        "score_includes_treatment": False,
        "seed": loaded["seed"],
        "seed_sent_to_provider": False,
        "suites": ["terminal-bench", "swe-bench-lite"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks.suite_arms")
    parser.add_argument("command", choices=("stub",))
    parser.add_argument("--output", type=Path)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return 2 if code is None else int(code)
    try:
        if args.command != "stub":
            raise AdapterError("the suite arm proof is the key-free stub.", 2)
        report = run_stub()
    except AdapterError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if args.output.exists() or args.output.is_symlink():
            print(f"refusing to overwrite {args.output}", file=sys.stderr)
            return 3
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
