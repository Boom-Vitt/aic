"""Validate host-AI recommendations, never classify tasks or authorize execution.

Validation establishes schema and path boundaries, not the truth of observations,
quality of branch separation, or correctness of natural-language acceptance checks.
The host skill must require verification or independent review for high-risk work.
"""
from __future__ import annotations

import json
import stat
from copy import deepcopy
from pathlib import Path
from typing import NamedTuple

from .safety import AICError, checked_root, relative_path, safe_path


_PLAN_KEYS = frozenset({
    "schema_version", "task", "workflow", "template", "topology", "risk", "reasons",
    "evidence", "scope", "acceptance", "independent_subtasks", "next_action",
    "approval_required",
})
_CATALOG = json.loads((Path(__file__).resolve().parents[2] / "assets/workflows.json").read_text(encoding="utf-8"))
_WORKFLOWS = frozenset(item["id"] for item in _CATALOG["workflows"])
_TOPOLOGIES = frozenset(_CATALOG["topologies"])
_TEMPLATES = {item["id"]: frozenset(item["topologies"]) for item in _CATALOG["templates"]}
_TEMPLATE_IDS = frozenset(_TEMPLATES)
_RISKS = frozenset({"low", "medium", "high"})


def _object(value: object, keys: frozenset[str], label: str) -> dict:
    if type(value) is not dict:
        raise AICError(f"{label} must be an object.")
    if any(type(key) is not str for key in value) or set(value) != keys:
        raise AICError(f"{label} must contain exactly these fields: {', '.join(sorted(keys))}.")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise AICError(f"{label} must be a nonempty string.")
    return value


def _list(value: object, label: str, *, nonempty: bool = False) -> list:
    if type(value) is not list or (nonempty and not value):
        qualifier = "a nonempty list" if nonempty else "a list"
        raise AICError(f"{label} must be {qualifier}.")
    return value


def _texts(value: object, label: str) -> None:
    for index, item in enumerate(_list(value, label, nonempty=True)):
        _text(item, f"{label}[{index}]")


def _choice(value: object, choices: frozenset[str], label: str) -> None:
    if _text(value, label) not in choices:
        raise AICError(f"{label} must be one of: {', '.join(sorted(choices))}.")


def _path(value: object, label: str, project: Path | None, *, must_exist: bool = False) -> Path:
    if type(value) is not str:
        raise AICError(f"{label} must be a relative path string.")
    normalized = relative_path(value)
    if project is not None:
        try:
            safe_path(project, value, must_exist=must_exist)
        except OSError as exc:
            raise AICError(f"{label} cannot be inspected safely.") from exc
    return normalized


def _paths(value: object, label: str, project: Path | None, *, nonempty: bool = False) -> list[Path]:
    return [
        _path(item, f"{label}[{index}]", project)
        for index, item in enumerate(_list(value, label, nonempty=nonempty))
    ]


def _overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


class _PhysicalScope(NamedTuple):
    ancestors: tuple[tuple[int, int], ...]
    missing: tuple[str, ...]


def _physical_scope(root: Path, relative: Path) -> _PhysicalScope:
    """Inspect only selected prefixes; never scan directories or probe by writing."""
    try:
        metadata = root.lstat()
        if not stat.S_ISDIR(metadata.st_mode):
            raise AICError("The project directory changed during path inspection.")
        identities = [(metadata.st_dev, metadata.st_ino)]
        current = root
        for index, part in enumerate(relative.parts):
            current = current / part
            try:
                metadata = current.lstat()
            except FileNotFoundError:
                return _PhysicalScope(tuple(identities), relative.parts[index:])
            if stat.S_ISLNK(metadata.st_mode):
                raise AICError("Parallel paths must not contain symlinks.")
            if index < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
                raise AICError("A parallel path has a non-directory ancestor.")
            identities.append((metadata.st_dev, metadata.st_ino))
        return _PhysicalScope(tuple(identities), ())
    except OSError as exc:
        raise AICError("Parallel path identities cannot be inspected safely.") from exc


def _physical_overlap(first: _PhysicalScope, second: _PhysicalScope) -> bool:
    if not first.missing and first.ancestors[-1] in second.ancestors:
        return True
    if not second.missing and second.ancestors[-1] in first.ancestors:
        return True
    if first.ancestors[-1] != second.ancestors[-1]:
        return False
    # Unknown future names share an actual parent. Fail closed for case-only
    # collisions instead of claiming that a read-only probe proved sensitivity.
    first_suffix = tuple(part.casefold() for part in first.missing)
    second_suffix = tuple(part.casefold() for part in second.missing)
    return (
        first_suffix == second_suffix[:len(first_suffix)]
        or second_suffix == first_suffix[:len(second_suffix)]
    )


def validate_plan(plan: dict, *, project: Path | None = None) -> dict:
    """Return a detached, unchanged-value copy of a schema-version-2 plan.

    An optional existing project enables symlink checks for every selected path
    and existence checks for evidence. Without it, paths are checked lexically;
    successful validation does not assert that evidence exists. Empty evidence
    and scope lists are permitted; the host must judge evidential sufficiency.
    New write paths may be absent. Approval-required is a safety condition, not
    an approval token, and neither prose nor extra permission fields can grant
    execution. Only the literal next action ``recommend`` is accepted.
    With a project, parallel isolation also compares existing device/inode
    ancestry, catching filesystem case aliases and hard links. Missing suffixes
    under the same physical parent are conservatively case-folded; this can
    reject distinct future case-only names on a case-sensitive filesystem.
    These selected-path metadata checks are not global alias detection, a
    filesystem lock, or protection against subsequent filesystem changes.
    """
    value = _object(plan, _PLAN_KEYS, "Recommendation")
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        raise AICError("schema_version must be the integer 2; select a template explicitly.")
    _text(value["task"], "task")
    _choice(value["workflow"], _WORKFLOWS, "workflow")
    _choice(value["template"], _TEMPLATE_IDS, "template")
    _choice(value["topology"], _TOPOLOGIES, "topology")
    if value["topology"] not in _TEMPLATES[value["template"]]:
        raise AICError("The selected template does not support this topology.")
    _choice(value["risk"], _RISKS, "risk")
    _texts(value["reasons"], "reasons")
    _texts(value["acceptance"], "acceptance")
    if type(value["next_action"]) is not str or value["next_action"] != "recommend":
        raise AICError("next_action must be 'recommend'; execution is not a recommendation.")
    if value["approval_required"] is not True:
        raise AICError("approval_required must be the boolean true; validation does not grant approval.")

    root = checked_root(project) if project is not None else None
    for index, item in enumerate(_list(value["evidence"], "evidence")):
        label = f"evidence[{index}]"
        evidence = _object(item, frozenset({"path", "observation"}), label)
        _path(evidence["path"], f"{label}.path", root, must_exist=True)
        _text(evidence["observation"], f"{label}.observation")

    scope = _object(value["scope"], frozenset({"read", "write"}), "scope")
    _paths(scope["read"], "scope.read", root)
    _paths(scope["write"], "scope.write", root)

    branch_paths = []
    for index, item in enumerate(_list(value["independent_subtasks"], "independent_subtasks")):
        label = f"independent_subtasks[{index}]"
        branch = _object(item, frozenset({"goal", "allowed_paths", "acceptance"}), label)
        _text(branch["goal"], f"{label}.goal")
        _texts(branch["acceptance"], f"{label}.acceptance")
        branch_paths.append(_paths(branch["allowed_paths"], f"{label}.allowed_paths", root, nonempty=True))

    if value["topology"] != "parallel" and branch_paths:
        raise AICError("independent_subtasks must be empty unless topology is parallel.")

    if value["topology"] == "parallel":
        if len(branch_paths) < 2:
            raise AICError("Parallel recommendations require at least two separately checkable subtasks.")
        physical_branches = (
            [[_physical_scope(root, path) for path in paths] for paths in branch_paths]
            if root is not None else None
        )
        for index, paths in enumerate(branch_paths):
            for previous in branch_paths[:index]:
                if any(_overlap(first, second) for first in paths for second in previous):
                    raise AICError("Parallel subtasks must have non-overlapping allowed_paths, including ancestors and descendants.")
            if physical_branches is not None:
                for previous in physical_branches[:index]:
                    if any(_physical_overlap(first, second) for first in physical_branches[index] for second in previous):
                        raise AICError("Parallel subtasks select overlapping filesystem identities or future paths.")

    return deepcopy(value)
