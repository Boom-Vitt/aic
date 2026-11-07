"""Scores and serializes a skill-lint report."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .model import Finding
from .spec import (
    AIC_OWN_RULES,
    ANTHROPIC_BEST_PRACTICES,
    ANTHROPIC_SKILL_DOCS,
    ERROR_WEIGHT,
    MAX_REPORTED_FINDINGS,
    SPEC_CHECKED,
    SPEC_REVISION,
    SPEC_URL,
    WARNING_WEIGHT,
)


def skill_score(error_count: int, warning_count: int) -> int:
    """Return a 0-100 hygiene score. Errors cost 20 points and warnings cost 5."""

    return max(0, 100 - ERROR_WEIGHT * error_count - WARNING_WEIGHT * warning_count)


def format_mean(scores: list[int]) -> str:
    """Arithmetic mean rounded half up to two decimals. Empty input is ``0.00``."""

    if not scores:
        return "0.00"
    mean = Decimal(sum(scores)) / Decimal(len(scores))
    return format(mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def format_rate(numerator: int, denominator: int) -> str | None:
    """Ratio rounded half up to four decimals, or ``None`` when the denominator is zero."""

    if denominator == 0:
        return None
    rate = Decimal(numerator) / Decimal(denominator)
    return format(rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


@dataclass(frozen=True)
class SkillReport:
    """Lint result for one skill directory."""

    path: str
    name: str | None
    score: int
    lines: int
    instruction_units: int | None
    findings: tuple[Finding, ...]

    @property
    def error_count(self) -> int:
        return sum(finding.severity == "error" for finding in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(finding.severity == "warning" for finding in self.findings)

    @property
    def format_pass(self) -> bool:
        return self.error_count == 0

    @property
    def findings_without_aic_rules(self) -> tuple[Finding, ...]:
        """Findings other than ``description-trigger`` and ``link-escapes``."""

        return tuple(finding for finding in self.findings if finding.rule not in AIC_OWN_RULES)

    @property
    def score_without_aic_rules(self) -> int:
        errors, warnings = _counts(self.findings_without_aic_rules)
        return skill_score(errors, warnings)

    @property
    def format_pass_without_aic_rules(self) -> bool:
        errors, _warnings = _counts(self.findings_without_aic_rules)
        return errors == 0

    def to_dict(self, *, summary: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.path,
            "name": self.name,
            "score": self.score,
            "score_without_aic_rules": self.score_without_aic_rules,
            "format_pass": self.format_pass,
            "format_pass_without_aic_rules": self.format_pass_without_aic_rules,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "lines": self.lines,
            "instruction_units": self.instruction_units,
        }
        if summary:
            return payload
        shown = self.findings[:MAX_REPORTED_FINDINGS]
        payload["findings"] = [finding.to_dict() for finding in shown]
        payload["findings_omitted"] = max(0, len(self.findings) - len(shown))
        return payload


@dataclass(frozen=True)
class RepoReport:
    """Lint result for every skill discovered under one root."""

    root: str
    skills: tuple[SkillReport, ...]

    @property
    def skill_count(self) -> int:
        return len(self.skills)

    @property
    def error_count(self) -> int:
        return sum(skill.error_count for skill in self.skills)

    @property
    def warning_count(self) -> int:
        return sum(skill.warning_count for skill in self.skills)

    @property
    def format_pass_count(self) -> int:
        return sum(skill.format_pass for skill in self.skills)

    @property
    def mean_score(self) -> str:
        return format_mean([skill.score for skill in self.skills])

    @property
    def mean_score_without_aic_rules(self) -> str:
        return format_mean([skill.score_without_aic_rules for skill in self.skills])

    @property
    def format_pass_count_without_aic_rules(self) -> int:
        return sum(skill.format_pass_without_aic_rules for skill in self.skills)

    @property
    def error_count_without_aic_rules(self) -> int:
        return sum(
            finding.severity == "error"
            for skill in self.skills
            for finding in skill.findings_without_aic_rules
        )

    @property
    def warning_count_without_aic_rules(self) -> int:
        return sum(
            finding.severity == "warning"
            for skill in self.skills
            for finding in skill.findings_without_aic_rules
        )

    def rules(self) -> tuple[tuple[str, str, int], ...]:
        """``(rule, severity, count)`` sorted by count, then severity, then rule."""

        counts: dict[tuple[str, str], int] = {}
        for skill in self.skills:
            for finding in skill.findings:
                key = (finding.rule, finding.severity)
                counts[key] = counts.get(key, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0][1], item[0][0]))
        return tuple((rule, severity, count) for (rule, severity), count in ranked)

    def to_dict(self, *, summary: bool) -> dict[str, object]:
        return {
            "spec_url": SPEC_URL,
            "spec_revision": SPEC_REVISION,
            "spec_checked": SPEC_CHECKED,
            "anthropic_skill_docs": ANTHROPIC_SKILL_DOCS,
            "anthropic_best_practices": ANTHROPIC_BEST_PRACTICES,
            "root": self.root,
            "skill_count": self.skill_count,
            "format_pass_count": self.format_pass_count,
            "format_pass_rate": format_rate(self.format_pass_count, self.skill_count),
            "format_pass_count_without_aic_rules": self.format_pass_count_without_aic_rules,
            "format_pass_rate_without_aic_rules": format_rate(
                self.format_pass_count_without_aic_rules, self.skill_count
            ),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "error_count_without_aic_rules": self.error_count_without_aic_rules,
            "warning_count_without_aic_rules": self.warning_count_without_aic_rules,
            "mean_score": self.mean_score,
            "mean_score_without_aic_rules": self.mean_score_without_aic_rules,
            "aic_own_rules": sorted(AIC_OWN_RULES),
            "score_weights": {"error": ERROR_WEIGHT, "warning": WARNING_WEIGHT},
            "rules": [
                {"rule": rule, "severity": severity, "count": count}
                for rule, severity, count in self.rules()
            ],
            "skills": [skill.to_dict(summary=summary) for skill in self.skills],
        }

    def render(self, *, summary: bool) -> str:
        rate = format_rate(self.format_pass_count, self.skill_count)
        shown_rate = rate if rate is not None else "n/a"
        lines = [
            f"root: {self.root}",
            f"skills: {self.skill_count}",
            f"format_pass: {self.format_pass_count}/{self.skill_count} ({shown_rate})",
            f"errors: {self.error_count}",
            f"warnings: {self.warning_count}",
            f"mean_score: {self.mean_score}",
            f"mean_score_without_aic_rules: {self.mean_score_without_aic_rules}",
            "rules:",
        ]
        rule_rows = self.rules()
        if not rule_rows:
            lines.append("  none")
        for rule, severity, count in rule_rows:
            lines.append(f"  {count:5}  {severity:7}  {rule}")
        if not summary:
            for skill in self.skills:
                lines.append(
                    f"{skill.path}  score={skill.score}  errors={skill.error_count}  "
                    f"warnings={skill.warning_count}  lines={skill.lines}"
                )
                shown = skill.findings[:MAX_REPORTED_FINDINGS]
                for finding in shown:
                    lines.append(
                        f"  {finding.severity}  {finding.rule}  {finding.path}:{finding.line}  {finding.message}"
                    )
                omitted = len(skill.findings) - len(shown)
                if omitted:
                    lines.append(f"  ... {omitted} more findings omitted")
        return "\n".join(lines) + "\n"


def _counts(findings: tuple[Finding, ...] | list[Finding]) -> tuple[int, int]:
    errors = sum(finding.severity == "error" for finding in findings)
    warnings = sum(finding.severity == "warning" for finding in findings)
    return errors, warnings
