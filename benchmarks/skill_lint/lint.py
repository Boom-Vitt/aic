"""Lint one skill directory or every skill in a repository tree."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .discover import LintError, discover_skills, iter_skill_files, open_root, read_text, relative_path
from .frontmatter import FrontmatterError, parse_skill_text
from .model import Finding
from .references import reference_findings
from .report import RepoReport, SkillReport, skill_score
from .secrets import secret_findings
from .validate import field_findings, size_findings


def lint_path(path: str | Path) -> RepoReport:
    """Lint ``path`` read-only. The final path component must not be a symlink."""

    root = open_root(path)
    discovered = discover_skills(root)
    skill_dirs = frozenset(skill for skill, _entry in discovered)
    skills = tuple(
        _lint_skill(root, skill, entry, skill_dirs) for skill, entry in discovered
    )
    return RepoReport(root=str(root), skills=skills)


def _lint_skill(root: Path, skill: Path, entry: Path, skill_dirs: frozenset[Path]) -> SkillReport:
    entry_path = relative_path(root, entry)
    skill_path = "." if skill == root else relative_path(root, skill)
    files = iter_skill_files(skill, skill_dirs)
    findings: list[Finding] = []
    name: str | None = None
    file_lines = 0
    units: int | None = None
    try:
        text = read_text(entry)
    except OSError:
        findings.append(Finding("error", "unreadable", entry_path, 1, "Skill entry could not be read."))
        text = None
    except UnicodeError:
        findings.append(Finding("error", "undecodable", entry_path, 1, "Skill entry is not valid UTF-8 text."))
        text = None
    if text is not None:
        file_lines = len(text.splitlines())
        try:
            parsed = parse_skill_text(text)
        except FrontmatterError as exc:
            findings.append(Finding("error", "frontmatter-invalid", entry_path, exc.line, str(exc)))
        else:
            if isinstance(parsed.fields.get("name"), str):
                name = parsed.fields["name"].strip() or None
            findings.extend(
                field_findings(
                    parsed.fields,
                    parsed.field_lines,
                    directory_name=skill.name,
                    entry_path=entry_path,
                )
            )
            findings.extend(
                size_findings(entry_path=entry_path, file_lines=parsed.file_lines, body=parsed.body)
            )
            units = (len(parsed.body.encode("utf-8")) + 3) // 4
            file_lines = parsed.file_lines
    findings.extend(reference_findings(root, skill, entry, files))
    findings.extend(secret_findings(root, files))
    ordered = tuple(sorted(findings, key=_finding_key))
    errors = sum(item.severity == "error" for item in ordered)
    warnings = sum(item.severity == "warning" for item in ordered)
    return SkillReport(
        path=skill_path,
        name=name,
        score=skill_score(errors, warnings),
        lines=file_lines,
        instruction_units=units,
        findings=ordered,
    )


def _finding_key(finding: Finding) -> tuple[int, str, str, int, str]:
    severity = 0 if finding.severity == "error" else 1
    return (severity, finding.rule, finding.path, finding.line, finding.message)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry. Exit 0 when no skill has an error, 1 when one does, 2 on usage failure."""

    parser = argparse.ArgumentParser(
        prog="skill-lint",
        description=(
            "Check SKILL.md files against the Agent Skills format. "
            "The checker is offline, read-only, and does not call a model."
        ),
    )
    parser.add_argument("path", help="Skill directory, SKILL.md file, or repository root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Omit per-finding lines. Counts and scores are unchanged.",
    )
    args = parser.parse_args(argv)
    try:
        report = lint_path(args.path)
    except LintError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(summary=args.summary), indent=2, ensure_ascii=True))
    else:
        sys.stdout.write(report.render(summary=args.summary))
    return 1 if report.error_count else 0
