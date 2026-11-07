"""Official two-arm mount check. Bubblewrap is the container sandbox.

The plain arm does not receive the skill directory. The AIC arm receives it
read-only. The probe only reports whether that mount is visible.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from aicbench.protocol import BenchError


def host_bind_args() -> list[str]:
    usr = Path("/usr")
    if usr.is_symlink() or not usr.is_dir():
        raise BenchError("container sandbox needs a real /usr directory.", 1)
    args = ["--ro-bind", "/usr", "/usr"]
    for name in ("/bin", "/lib", "/lib64"):
        path = Path(name)
        if path.is_symlink():
            args.extend(["--symlink", os.readlink(path), name])
        elif path.is_dir():
            args.extend(["--ro-bind", name, name])
    return args


def sandbox_argv(*, probe_dir: Path, skill_dir: Path | None) -> list[str]:
    argv = [
        "bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--setenv", "PATH", "/usr/bin",
    ]
    argv.extend(host_bind_args())
    argv.extend(["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"])
    argv.extend(["--ro-bind", str(probe_dir), "/task", "--chdir", "/task"])
    if skill_dir is not None:
        argv.extend(["--ro-bind", str(skill_dir), "/opt/aic"])
    argv.extend(["/usr/bin/python3", "/task/probe.py"])
    return argv


def _real_dir(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise BenchError(f"{label} is not a real directory.", 1)


def _real_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise BenchError(f"{label} is not a real file.", 1)


def _default_runner(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, check=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise BenchError("bubblewrap (bwrap) is required for --sandbox container.", 1) from exc
    except subprocess.TimeoutExpired as exc:
        raise BenchError("container probe timed out.", 1) from exc


def _trusted(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise BenchError(f"refusing a symlinked {label}.", 3)
    return path.resolve()


def run_official(root: Path, *, sandbox_runner=None, timeout: int = 30) -> dict:
    probe_dir = _trusted(root / "benchmarks" / "official", "official probe directory")
    skill_dir = _trusted(root / "skills" / "aic", "AIC skill directory")
    _real_dir(probe_dir, "official probe directory")
    _real_file(probe_dir / "probe.py", "official probe")
    _real_dir(skill_dir, "AIC skill directory")
    _real_file(skill_dir / "SKILL.md", "AIC skill file")
    runner = sandbox_runner or _default_runner
    runs = []
    for arm, mount in (("plain-claude-code", None), ("aic", skill_dir)):
        argv = sandbox_argv(probe_dir=probe_dir, skill_dir=mount)
        if mount is None and "/opt/aic" in argv:
            raise BenchError("plain arm must not mount the skill.", 1)
        completed = runner(argv, timeout)
        loaded = None
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("workflow_loaded"), bool):
            loaded = payload["workflow_loaded"]
        runs.append({
            "arm": arm,
            "exit_code": completed.returncode,
            "workflow_loaded": loaded,
            "sandbox": "container",
            "argv0": argv[0],
        })
    expected = {"plain-claude-code": False, "aic": True}
    ok = all(item["exit_code"] == 0 and item["workflow_loaded"] is expected[item["arm"]] for item in runs)
    return {
        "ok": ok,
        "executed": True,
        "suite": "official",
        "command": "python3 -m aicbench --sandbox container --official",
        "sandbox": "container",
        "arms": ["plain-claude-code", "aic"],
        "runs": runs,
        "invokes_model": False,
        "public_benchmark_scores": None,
        "note": "Bubblewrap mount check only. Not a public benchmark score.",
    }
