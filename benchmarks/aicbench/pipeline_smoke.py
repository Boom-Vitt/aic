"""Run the offline aicbench sandbox smoke.

The stub under ``stub/`` is a pipeline smoke test. It is not a model, and the
report from this module is not a results-table row. ``official`` is true only
when the probe ran under the container sandbox.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from . import SCHEMA_VERSION, UNOFFICIAL_WARNING
from .catalog import CatalogError, load_catalog
from .grading import (
    IntegrityError,
    grade,
    outside_repository_temp,
    prepare_workspace,
    protected_bytes,
    sha256_manifest,
    verified_bytes,
)
from .sandbox import container_command, sandbox_runtime

SMOKE_TASK_ID = "bugfix-ledger-signs"
STUB_PATH = Path(__file__).resolve().parent / "stub" / "agent.py"
PROBE_NAME = "pipeline-smoke.json"
LABEL = "pipeline smoke test"
PROBE_TIMEOUT_SECONDS = 30
MODEL_RESULT_KEYS = ("arms", "cost_usd", "pass_at_1", "samples", "tokens", "total_cost_usd", "usage")


class SmokeError(RuntimeError):
    """The pipeline smoke could not be executed."""


def _interpreter(repo: Path) -> Path:
    candidates = (Path(sys.executable), Path("/usr/bin/python3"))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and resolved != repo and repo not in resolved.parents:
            return resolved
    raise SmokeError("Pipeline smoke needs a Python interpreter outside the repository.")


def _smoke_env(parent: dict[str, str], *, home: Path, tmp: Path) -> dict[str, str]:
    """Environment for the stub. Model credentials and PYTHONPATH are omitted."""
    return {
        "AICBENCH_PIPELINE_SMOKE": "1",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": parent.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "TMPDIR": str(tmp),
    }


def _task():
    matches = [item for item in load_catalog() if item.id == SMOKE_TASK_ID]
    if len(matches) != 1:
        raise CatalogError(f"Pipeline smoke task is missing: {SMOKE_TASK_ID}")
    return matches[0]


def _parse_probe(stdout: str) -> dict:
    try:
        payload = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise SmokeError("Pipeline smoke stub did not print JSON.") from exc
    if not isinstance(payload, dict) or payload.get("role") != "pipeline-smoke":
        raise SmokeError("Pipeline smoke stub returned an unexpected payload.")
    if payload.get("label") != LABEL:
        raise SmokeError("Pipeline smoke stub is not labeled as a pipeline smoke test.")
    for key in ("reference_readable", "oracle_readable", "api_key_visible", "pythonpath_visible"):
        if not isinstance(payload.get(key), bool):
            raise SmokeError(f"Pipeline smoke stub omitted {key}.")
    return payload


def _run_probe(sandbox: str, task, parent: dict[str, str]) -> dict:
    repo = Path(__file__).resolve().parents[2]
    interpreter = _interpreter(repo)
    if not STUB_PATH.is_file() or STUB_PATH.is_symlink():
        raise SmokeError("Pipeline smoke stub is missing.")
    stub_bytes = STUB_PATH.read_bytes()
    with tempfile.TemporaryDirectory(prefix="aicbench-smoke-", dir=outside_repository_temp()) as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        home = root / "home"
        config = root / "config"
        workspace.mkdir()
        home.mkdir()
        config.mkdir()
        script = workspace / "pipeline-smoke-agent.py"
        script.write_bytes(stub_bytes)
        probe = {
            "role": "pipeline-smoke",
            "reference": str(task.reference.resolve()),
            "oracle": str(task.oracle.resolve()),
        }
        (workspace / PROBE_NAME).write_text(
            json.dumps(probe, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        inner = [str(interpreter), str(script)]
        if sandbox == "container":
            command = container_command(
                inner,
                workspace=workspace,
                skill_root=None,
                home=home,
                config=config,
                binary=interpreter,
                repo=repo,
            )
            command[0] = sandbox_runtime()
        elif sandbox == "none":
            command = inner
        else:
            raise SmokeError("Pipeline smoke sandbox must be none or container.")
        hidden = str(task.reference.resolve())
        oracle = str(task.oracle.resolve())
        if sandbox == "container" and (str(repo.resolve()) in command or hidden in command or oracle in command):
            raise SmokeError("Container probe argv included a hidden repository path.")
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=_smoke_env(parent, home=home, tmp=root),
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SmokeError("Pipeline smoke stub timed out.") from exc
        except OSError as exc:
            raise SmokeError(f"Pipeline smoke stub failed to start: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "stub exited nonzero").strip()
            raise SmokeError(detail[:500])
        return _parse_probe(completed.stdout or "")


def _prove_grading(task) -> bool:
    with tempfile.TemporaryDirectory(prefix="aicbench-smoke-grade-", dir=outside_repository_temp()) as temporary:
        root = Path(temporary)
        starting = root / "starting"
        solved = root / "solved"
        prepare_workspace(task, starting, solution=False)
        prepare_workspace(task, solved, solution=True)
        started = grade(task, starting)
        reference = grade(task, solved)
    return started.passed is False and started.timed_out is False and reference.passed is True and reference.timed_out is False


def _prove_tamper(task, parent: dict[str, str]) -> bool:
    """Have the stub rewrite the oracle, require the manifest to notice, then restore."""
    original = task.oracle.read_bytes()
    expected = sha256_manifest(protected_bytes(task))
    detected = False
    try:
        completed = subprocess.run(
            [sys.executable, str(STUB_PATH), "tamper", str(task.oracle)],
            cwd=outside_repository_temp(),
            env=_smoke_env(parent, home=outside_repository_temp(), tmp=outside_repository_temp()),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0:
            return False
        try:
            verified_bytes(task, expected)
        except IntegrityError:
            detected = True
        return detected
    finally:
        task.oracle.write_bytes(original)
        if task.oracle.read_bytes() != original:
            raise SmokeError("Pipeline smoke did not restore the oracle after the tamper probe.")


def run_pipeline_smoke(sandbox: str, environ: dict[str, str] | None = None) -> dict:
    """Probe the sandbox, grade one task, and detect an oracle write.

    ``sandbox`` is ``container`` or ``none``. The container probe must be unable
    to read the reference and the oracle. The unsandboxed probe must be able to
    read both. Either report is a pipeline smoke test, not a model measurement.
    """
    if sandbox not in {"none", "container"}:
        raise SmokeError("Pipeline smoke sandbox must be none or container.")
    if sandbox == "container":
        sandbox_runtime()
    parent = os.environ if environ is None else environ
    task = _task()
    before = task.oracle.read_bytes()
    try:
        payload = _run_probe(sandbox, task, parent)
        grading_works = _prove_grading(task)
        tamper_detected = _prove_tamper(task, parent)
    finally:
        if task.oracle.read_bytes() != before:
            task.oracle.write_bytes(before)
            raise SmokeError("Pipeline smoke left the oracle changed.")
    hidden = sandbox == "container"
    checks = {
        "api_key_forwarded": payload["api_key_visible"] or payload["pythonpath_visible"],
        "grading_works": grading_works,
        "oracle_unreadable": not payload["oracle_readable"],
        "reference_unreadable": not payload["reference_readable"],
        "tamper_detected": tamper_detected,
    }
    official = hidden
    report = {
        "agent": "benchmarks/aicbench/stub/agent.py",
        "benchmark": "aicbench",
        "checks": checks,
        "invokes_model": False,
        "kind": "pipeline-smoke",
        "label": LABEL,
        "measured": False,
        "model_result": False,
        "official": official,
        "ok": (
            checks["reference_unreadable"] is hidden
            and checks["oracle_unreadable"] is hidden
            and checks["tamper_detected"] is True
            and checks["grading_works"] is True
            and checks["api_key_forwarded"] is False
        ),
        "publication_warning": None if official else UNOFFICIAL_WARNING,
        "sandbox": sandbox,
        "schema_version": SCHEMA_VERSION,
        "task_graded": task.id,
    }
    overlap = MODEL_RESULT_KEYS & report.keys()
    if overlap:
        raise SmokeError("Pipeline smoke report included a model metric: " + ", ".join(sorted(overlap)))
    return report
