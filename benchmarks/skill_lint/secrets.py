"""High-confidence secret patterns in skill files.

Matches are reported by pattern name, path, and line. The matched text is
never copied into the finding. Documentation placeholders that contain words
such as "example" or "redacted" are ignored, so this is not a general secret
scanner and it can miss credentials that do not match these patterns.
"""

from __future__ import annotations

import re
from pathlib import Path

from .model import Finding


_MAX_BYTES = 1024 * 1024
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("github-fine-grained-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "assigned-secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password)\b"
            r"\s*[:=]\s*['\"]([A-Za-z0-9+/=_\-]{16,})['\"]"
        ),
    ),
)
_PLACEHOLDER = re.compile(
    r"(?i)(example|placeholder|redacted|changeme|your[-_]|xxx+|sample|dummy|todo|insert|replace)"
)
_SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
    }
)


def secret_findings(root: Path, files: list[Path]) -> list[Finding]:
    """Scan regular skill files for filenames and credential patterns."""

    findings: list[Finding] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if _sensitive_name(path.name):
            findings.append(
                Finding(
                    "error",
                    "secret-filename",
                    relative,
                    1,
                    "Sensitive filename inside the skill directory.",
                )
            )
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(Finding("error", "unreadable", relative, 1, "Skill file could not be read."))
            continue
        if b"\x00" in data[:8192]:
            continue
        truncated = len(data) > _MAX_BYTES
        sample = data[:_MAX_BYTES]
        try:
            text = sample.decode("utf-8")
        except UnicodeError:
            continue
        if truncated:
            findings.append(
                Finding(
                    "warning",
                    "file-truncated",
                    relative,
                    1,
                    "Only the first 1 MiB of this text file was scanned.",
                )
            )
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in _PATTERNS:
                match = pattern.search(line)
                if match is None or _PLACEHOLDER.search(match.group(0)):
                    continue
                findings.append(
                    Finding(
                        "error",
                        "secret-pattern",
                        relative,
                        line_number,
                        f"High-confidence secret pattern matched ({name}).",
                    )
                )
    return findings


def _sensitive_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in _SENSITIVE_NAMES:
        return True
    if lowered.startswith(".env.") and not lowered.endswith((".example", ".sample", ".template")):
        return True
    return False
