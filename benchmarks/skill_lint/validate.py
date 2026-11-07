"""Frontmatter checks from the Agent Skills specification and Anthropic's field rules."""

from __future__ import annotations

import re
import unicodedata

from .model import Finding
from .spec import (
    ALLOWED_FIELDS,
    MAX_COMPATIBILITY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_INSTRUCTION_UNITS,
    MAX_NAME_LENGTH,
    MAX_SKILL_LINES,
    TERSE_DESCRIPTION_LENGTH,
)


_XML_TAG = re.compile(r"</?[A-Za-z][^>\n]{0,80}>")
_TRIGGER = re.compile(
    r"(?i)("
    r"\buse when\b|\buse before\b|\buse after\b|\buse if\b|\buse for\b|\buse to\b|"
    r"\buse this\b|\buse during\b|\buse while\b|\bwhen the user\b|\bwhen working\b|"
    r"\bwhen asked\b|\bwhen you\b|\bif the user\b|\bwhenever\b|\bdon't use\b|\bdo not use\b"
    r")"
)
_PERSON = re.compile(
    r"(?i)\b(i'm|i am|i will|i can|we're|we are|you're|you are|you|your|we)\b"
)


def field_findings(
    fields: dict[str, object],
    field_lines: dict[str, int],
    *,
    directory_name: str,
    entry_path: str,
) -> list[Finding]:
    """Validate parsed frontmatter. ``entry_path`` is repo-relative and POSIX."""

    findings: list[Finding] = []
    unknown = sorted(set(fields) - ALLOWED_FIELDS)
    if unknown:
        findings.append(
            Finding(
                "error",
                "field-unknown",
                entry_path,
                field_lines.get(unknown[0], 1),
                "Unexpected frontmatter fields: "
                + ", ".join(unknown)
                + ". The Agent Skills specification allows only: "
                + ", ".join(sorted(ALLOWED_FIELDS))
                + ".",
            )
        )
    findings.extend(_name_findings(fields, field_lines, directory_name, entry_path))
    findings.extend(_description_findings(fields, field_lines, entry_path))
    findings.extend(_optional_findings(fields, field_lines, entry_path))
    return findings


def size_findings(*, entry_path: str, file_lines: int, body: str) -> list[Finding]:
    """Progressive-disclosure size recommendations. These are warnings."""

    findings: list[Finding] = []
    if file_lines >= MAX_SKILL_LINES:
        findings.append(
            Finding(
                "warning",
                "skill-line-limit",
                entry_path,
                1,
                f"SKILL.md has {file_lines} lines; published guidance keeps it under {MAX_SKILL_LINES}.",
            )
        )
    if not body.strip():
        findings.append(
            Finding(
                "warning",
                "empty-body",
                entry_path,
                max(file_lines, 1),
                "SKILL.md has no instruction body after the frontmatter.",
            )
        )
    units = (len(body.encode("utf-8")) + 3) // 4
    if units > MAX_INSTRUCTION_UNITS:
        findings.append(
            Finding(
                "warning",
                "instruction-size",
                entry_path,
                1,
                (
                    f"Instruction body is about {units} UTF-8-byte/4 units, above the published "
                    f"{MAX_INSTRUCTION_UNITS}-token recommendation. This checker does not run a tokenizer."
                ),
            )
        )
    return findings


def _name_findings(
    fields: dict[str, object], field_lines: dict[str, int], directory_name: str, entry_path: str
) -> list[Finding]:
    line = field_lines.get("name", 1)
    if "name" not in fields:
        return [Finding("error", "name-missing", entry_path, 1, "Frontmatter is missing required field 'name'.")]
    name = fields["name"]
    if not isinstance(name, str):
        return [Finding("error", "name-type", entry_path, line, "Field 'name' must be a string.")]
    normalized = unicodedata.normalize("NFKC", name.strip())
    if not normalized:
        return [Finding("error", "name-empty", entry_path, line, "Field 'name' must be a non-empty string.")]
    findings: list[Finding] = []
    if len(normalized) > MAX_NAME_LENGTH:
        findings.append(
            Finding(
                "error",
                "name-length",
                entry_path,
                line,
                f"Field 'name' has {len(normalized)} characters; the maximum is {MAX_NAME_LENGTH}.",
            )
        )
    if normalized != normalized.lower():
        findings.append(Finding("error", "name-case", entry_path, line, "Field 'name' must be lowercase."))
    if normalized.startswith("-") or normalized.endswith("-"):
        findings.append(
            Finding("error", "name-hyphen-affix", entry_path, line, "Field 'name' must not start or end with a hyphen.")
        )
    if "--" in normalized:
        findings.append(
            Finding(
                "error",
                "name-consecutive-hyphens",
                entry_path,
                line,
                "Field 'name' must not contain consecutive hyphens.",
            )
        )
    if any(not (character.isalnum() or character == "-") for character in normalized):
        findings.append(
            Finding(
                "error",
                "name-characters",
                entry_path,
                line,
                "Field 'name' may contain only lowercase letters, digits, and hyphens.",
            )
        )
    directory = unicodedata.normalize("NFKC", directory_name)
    if directory != normalized:
        findings.append(
            Finding(
                "error",
                "name-directory",
                entry_path,
                line,
                f"Directory name {directory_name!r} must match skill name {normalized!r}.",
            )
        )
    folded = normalized.lower()
    if "anthropic" in folded or "claude" in folded:
        findings.append(
            Finding(
                "error",
                "name-reserved",
                entry_path,
                line,
                "Field 'name' contains reserved word 'anthropic' or 'claude'.",
            )
        )
    if _XML_TAG.search(normalized):
        findings.append(
            Finding("error", "xml-tag", entry_path, line, "Field 'name' contains an XML tag.")
        )
    return findings


def _description_findings(
    fields: dict[str, object], field_lines: dict[str, int], entry_path: str
) -> list[Finding]:
    line = field_lines.get("description", 1)
    if "description" not in fields:
        return [
            Finding(
                "error",
                "description-missing",
                entry_path,
                1,
                "Frontmatter is missing required field 'description'.",
            )
        ]
    description = fields["description"]
    if not isinstance(description, str):
        return [
            Finding("error", "description-type", entry_path, line, "Field 'description' must be a string.")
        ]
    if not description.strip():
        return [
            Finding(
                "error",
                "description-empty",
                entry_path,
                line,
                "Field 'description' must be a non-empty string.",
            )
        ]
    findings: list[Finding] = []
    if len(description) > MAX_DESCRIPTION_LENGTH:
        findings.append(
            Finding(
                "error",
                "description-length",
                entry_path,
                line,
                f"Field 'description' has {len(description)} characters; the maximum is {MAX_DESCRIPTION_LENGTH}.",
            )
        )
    if _XML_TAG.search(description):
        findings.append(
            Finding("error", "xml-tag", entry_path, line, "Field 'description' contains an XML tag.")
        )
    if len(description.strip()) < TERSE_DESCRIPTION_LENGTH:
        findings.append(
            Finding(
                "warning",
                "description-terse",
                entry_path,
                line,
                f"Field 'description' has {len(description.strip())} non-whitespace characters; "
                f"trigger text shorter than {TERSE_DESCRIPTION_LENGTH} is treated as unclear.",
            )
        )
    if _TRIGGER.search(description) is None:
        findings.append(
            Finding(
                "warning",
                "description-trigger",
                entry_path,
                line,
                "Field 'description' does not say when to use the skill (no 'use when' style trigger).",
            )
        )
    if _PERSON.search(description):
        findings.append(
            Finding(
                "warning",
                "description-person",
                entry_path,
                line,
                "Field 'description' uses a first- or second-person pronoun; authoring guidance uses third person.",
            )
        )
    return findings


def _optional_findings(
    fields: dict[str, object], field_lines: dict[str, int], entry_path: str
) -> list[Finding]:
    findings: list[Finding] = []
    if "license" in fields and not isinstance(fields["license"], str):
        findings.append(
            Finding(
                "error",
                "license-type",
                entry_path,
                field_lines.get("license", 1),
                "Field 'license' must be a string.",
            )
        )
    if "compatibility" in fields:
        compatibility = fields["compatibility"]
        line = field_lines.get("compatibility", 1)
        if not isinstance(compatibility, str):
            findings.append(
                Finding("error", "compatibility-type", entry_path, line, "Field 'compatibility' must be a string.")
            )
        elif not 1 <= len(compatibility) <= MAX_COMPATIBILITY_LENGTH:
            findings.append(
                Finding(
                    "error",
                    "compatibility-length",
                    entry_path,
                    line,
                    f"Field 'compatibility' has {len(compatibility)} characters; the specification allows 1-{MAX_COMPATIBILITY_LENGTH}.",
                )
            )
    if "metadata" in fields:
        metadata = fields["metadata"]
        line = field_lines.get("metadata", 1)
        if not isinstance(metadata, dict):
            findings.append(
                Finding("error", "metadata-type", entry_path, line, "Field 'metadata' must be a mapping of strings.")
            )
        else:
            for key, value in metadata.items():
                if isinstance(key, str) and isinstance(value, str):
                    continue
                label = key if isinstance(key, str) and key.isidentifier() else "a nested entry"
                findings.append(
                    Finding(
                        "error",
                        "metadata-value",
                        entry_path,
                        line,
                        f"Field 'metadata' value for {label} must be a string.",
                    )
                )
    if "allowed-tools" in fields and not isinstance(fields["allowed-tools"], str):
        findings.append(
            Finding(
                "error",
                "allowed-tools-type",
                entry_path,
                field_lines.get("allowed-tools", 1),
                "Field 'allowed-tools' must be a space-separated string.",
            )
        )
    return findings
