"""Relative file references inside a skill directory."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from .model import Finding


_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})")
_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]*)\)")
_REFERENCE_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]+(\S+)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_PATH_PREFIXES = ("scripts/", "references/", "reference/", "assets/", "templates/", "examples/", "./", "../")


def reference_findings(root: Path, skill: Path, entry: Path, files: list[Path]) -> list[Finding]:
    """Check Markdown links and skill-local paths without following symlinks."""

    findings: list[Finding] = []
    nested = 0
    nested_example = ""
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line_number, kind, target in _references(text):
            status = _classify(skill, path, target)
            relative = _display(root, path)
            if status == "ok":
                if path != entry and kind == "link" and _is_markdown(target) and not _points_at_entry(target):
                    nested += 1
                    if not nested_example:
                        nested_example = f"{relative}:{line_number}"
                continue
            if status == "external":
                continue
            rule = {
                "missing": "missing-reference",
                "escape": "link-escapes",
                "symlink": "symlink-reference",
                "absolute": "absolute-reference",
                "invalid": "link-invalid",
            }[status]
            severity = "warning" if status == "absolute" else "error"
            findings.append(
                Finding(
                    severity,
                    rule,
                    relative,
                    line_number,
                    _message(status, target),
                )
            )
    if nested:
        findings.append(
            Finding(
                "warning",
                "nested-reference",
                _display(root, entry),
                1,
                (
                    f"{nested} markdown links from files other than the skill entry continue "
                    f"the reference chain (for example {nested_example}). Published guidance "
                    "keeps file references one level deep from SKILL.md."
                ),
            )
        )
    return findings


def _references(text: str) -> list[tuple[int, str, str]]:
    found: list[tuple[int, str, str]] = []
    fence: str | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        marker = _FENCE.match(line)
        if marker is not None:
            token = marker.group(2)[0]
            if fence is None:
                fence = token
            elif token == fence:
                fence = None
            continue
        if fence is not None:
            continue
        for is_code, segment in _split_code(line):
            if is_code:
                candidate = segment.strip()
                if _is_skill_path(candidate):
                    found.append((line_number, "code", candidate))
                continue
            for match in _LINK.finditer(segment):
                target = _clean_target(match.group(1))
                if target is not None and _looks_like_file_reference(target):
                    found.append((line_number, "link", target))
            definition = _REFERENCE_DEFINITION.match(segment)
            if definition is not None:
                target = _clean_target(definition.group(1))
                if target is not None and _looks_like_file_reference(target):
                    found.append((line_number, "link", target))
        stripped = line.strip()
        if _is_skill_path(stripped):
            found.append((line_number, "line", stripped))
    return found


def _split_code(line: str) -> list[tuple[bool, str]]:
    parts: list[tuple[bool, str]] = []
    index = 0
    while index < len(line):
        if line[index] != "`":
            nxt = line.find("`", index)
            if nxt == -1:
                parts.append((False, line[index:]))
                break
            parts.append((False, line[index:nxt]))
            index = nxt
            continue
        width = 1
        while index + width < len(line) and line[index + width] == "`":
            width += 1
        end = line.find("`" * width, index + width)
        if end == -1:
            parts.append((False, line[index:]))
            break
        parts.append((True, line[index + width : end]))
        index = end + width
    return parts


def _clean_target(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")].strip()
    elif value[0] not in "\"'":
        value = value.split()[0]
    else:
        return None
    if not value or value.startswith("#"):
        return None
    if _SCHEME.match(value):
        return None
    return value


def _looks_like_file_reference(target: str) -> bool:
    """True when a Markdown target is a relative file path rather than an identifier."""

    path = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not path:
        return False
    if path.startswith(("/", "./", "../")) or "/" in path:
        return True
    name = Path(path).name
    if "." not in name:
        return False
    suffix = name.rsplit(".", 1)[-1]
    return suffix.isalnum() and 1 <= len(suffix) <= 8


def _is_skill_path(token: str) -> bool:
    if not token or any(character in token for character in " \t*?<>|${}`"):
        return False
    if _SCHEME.match(token) or token.startswith("#"):
        return False
    return token.startswith(_PATH_PREFIXES)


def _is_markdown(target: str) -> bool:
    path = target.split("#", 1)[0].split("?", 1)[0]
    return path.lower().endswith(".md")


def _points_at_entry(target: str) -> bool:
    name = Path(target.split("#", 1)[0].split("?", 1)[0]).name.lower()
    return name in {"skill.md"}


def _classify(skill: Path, source: Path, target: str) -> str:
    if "\\" in target or "\x00" in target or "\n" in target:
        return "invalid"
    decoded = unquote(target).split("#", 1)[0].split("?", 1)[0]
    if not decoded or decoded.startswith("#"):
        return "external"
    if decoded.startswith("/") or re.match(r"^[A-Za-z]:", decoded):
        return "absolute"
    bases = [source.parent]
    if source.parent != skill and not decoded.startswith("../"):
        bases.append(skill)
    saw_missing = False
    for base in bases:
        status = _walk(skill, base, decoded)
        if status == "ok":
            return "ok"
        if status in {"escape", "symlink", "invalid"}:
            return status
        saw_missing = True
    return "missing" if saw_missing else "invalid"


def _walk(skill: Path, base: Path, decoded: str) -> str:
    current = base
    for part in Path(decoded).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if current == skill:
                return "escape"
            current = current.parent
            if skill != current and skill not in current.parents:
                return "escape"
            continue
        current = current / part
        try:
            if current.is_symlink():
                return "symlink"
        except OSError:
            return "invalid"
    try:
        if current.is_symlink():
            return "symlink"
        if current.exists():
            return "ok"
    except OSError:
        return "invalid"
    return "missing"


def _display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _message(status: str, target: str) -> str:
    shown = target if len(target) <= 120 else target[:117] + "..."
    if status == "missing":
        return f"Relative reference does not exist in the skill: {shown}"
    if status == "escape":
        return f"Relative reference leaves the skill directory: {shown}"
    if status == "symlink":
        return f"Relative reference is a symlink and was not followed: {shown}"
    if status == "absolute":
        return f"Reference is absolute rather than skill-relative: {shown}"
    return f"Relative reference is not a portable skill path: {shown}"
