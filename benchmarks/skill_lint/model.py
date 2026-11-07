"""Finding records shared by the skill checker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One deterministic lint finding. Messages never include secret material."""

    severity: str
    rule: str
    path: str
    line: int
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "rule": self.rule,
            "path": self.path,
            "line": self.line,
            "message": self.message,
        }
