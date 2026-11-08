"""Validate a changed-surface record. Never run the recorded command.

The host writes the record after it has already run the checks. This module
checks shape only. It does not execute a shell, read a project, or decide
that the observation text is true.
"""
from __future__ import annotations

import json
from copy import deepcopy

from .safety import AICError


_RECORD_KEYS = frozenset({
    "schema_version", "kind", "task", "outcome", "checks", "not_run",
})
_CHECK_KEYS = frozenset({"command", "phase", "observed", "exit_code"})
_OUTCOMES = frozenset({"passed", "partial", "blocked", "failed"})
_PHASES = frozenset({"before", "after"})
_KIND = "aic-changed-surface"

_MAX_BYTES = 16 * 1024
_MAX_CHECKS = 8
_MAX_NOT_RUN = 12
_MAX_TASK = 300
_MAX_COMMAND = 240
_MAX_OBSERVED = 500
_MAX_NOT_RUN_ITEM = 160


def validate_surface(record: dict) -> dict:
    """Return a detached copy of a schema-1 changed-surface record.

    ``passed`` requires an empty ``not_run`` list and the same command
    recorded before editing and again after, each with an exit code.
    Any other outcome may omit checks. No command is executed.
    """
    if type(record) is not dict:
        raise AICError("Changed-surface record must be an object.")
    if any(type(key) is not str for key in record) or set(record) != _RECORD_KEYS:
        raise AICError(
            "Changed-surface record must contain exactly these fields: "
            + ", ".join(sorted(_RECORD_KEYS))
            + "."
        )
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise AICError("schema_version must be the integer 1.")
    if record["kind"] != _KIND:
        raise AICError(f"kind must be {_KIND}.")
    task = _bounded_text(record["task"], "task", _MAX_TASK)
    outcome = _choice(record["outcome"], _OUTCOMES, "outcome")
    checks = _checks(record["checks"])
    not_run = _not_run(record["not_run"])
    if outcome == "passed":
        if not_run:
            raise AICError("A passed record must list no skipped checks. Use partial or blocked when a check was not run.")
        if not checks:
            raise AICError("A passed record needs at least one check.")
        _require_same_check(checks)
    value = {
        "schema_version": 1,
        "kind": _KIND,
        "task": task,
        "outcome": outcome,
        "checks": checks,
        "not_run": not_run,
    }
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        raise AICError("Changed-surface record exceeds the 16 KiB canonical JSON budget.")
    return deepcopy(value)


def _require_same_check(checks: list[dict]) -> None:
    phases: dict[str, set[str]] = {}
    for check in checks:
        phases.setdefault(check["command"], set()).add(check["phase"])
    paired = any({"before", "after"} <= seen for seen in phases.values())
    unfinished = any("before" in seen and "after" not in seen for seen in phases.values())
    if not paired or unfinished:
        raise AICError(
            "A passed record needs each check shown before editing recorded again after, on the same command, with an exit code."
        )


def _checks(value: object) -> list[dict]:
    if type(value) is not list or len(value) > _MAX_CHECKS:
        raise AICError(f"checks must be a list of at most {_MAX_CHECKS} objects.")
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(value):
        if type(item) is not dict or any(type(key) is not str for key in item) or set(item) != _CHECK_KEYS:
            raise AICError(
                f"checks[{index}] must contain exactly these fields: " + ", ".join(sorted(_CHECK_KEYS)) + "."
            )
        command = _command(item["command"], f"checks[{index}].command")
        phase = _choice(item["phase"], _PHASES, f"checks[{index}].phase")
        observed = _bounded_text(item["observed"], f"checks[{index}].observed", _MAX_OBSERVED)
        exit_code = _exit_code(item["exit_code"], f"checks[{index}].exit_code")
        identity = (command, phase)
        if identity in seen:
            raise AICError("A command may have only one check per phase.")
        seen.add(identity)
        found.append({
            "command": command,
            "phase": phase,
            "observed": observed,
            "exit_code": exit_code,
        })
    return found


def _not_run(value: object) -> list[str]:
    if type(value) is not list or len(value) > _MAX_NOT_RUN:
        raise AICError(f"not_run must be a list of at most {_MAX_NOT_RUN} strings.")
    found: list[str] = []
    for index, item in enumerate(value):
        text = _bounded_text(item, f"not_run[{index}]", _MAX_NOT_RUN_ITEM)
        if text in found:
            raise AICError("not_run must not repeat a string.")
        found.append(text)
    return found


def _command(value: object, label: str) -> str:
    command = _bounded_text(value, label, _MAX_COMMAND)
    if any(ord(character) < 32 for character in command):
        raise AICError(f"{label} must be a single line.")
    if _escaped_command(command):
        raise AICError(f"{label} must stay a relative command inside the approved workspace.")
    return command


def _escaped_command(command: str) -> bool:
    for token in command.split():
        if token.startswith(("/", "~")):
            return True
        normalized = token.replace("\\", "/")
        for raw in normalized.split("/"):
            piece = raw.strip("\"'`()[]{}:,")
            if piece == "..":
                return True
    return False


def _exit_code(value: object, label: str) -> int:
    if type(value) is not int or isinstance(value, bool) or not -128 <= value <= 255:
        raise AICError(f"{label} must be an integer exit code from -128 through 255.")
    return value


def _choice(value: object, choices: frozenset[str], label: str) -> str:
    if type(value) is not str or value not in choices:
        raise AICError(f"{label} must be one of: {', '.join(sorted(choices))}.")
    return value


def _bounded_text(value: object, label: str, limit: int) -> str:
    if type(value) is not str or value != value.strip() or value == "":
        raise AICError(f"{label} must be a nonempty trimmed string.")
    if len(value.encode("utf-8")) > limit:
        raise AICError(f"{label} exceeds {limit} UTF-8 bytes.")
    return value
