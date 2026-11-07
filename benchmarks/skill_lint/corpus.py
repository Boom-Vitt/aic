"""Pinned comparison repositories for the skill-hygiene measurement.

These are public skills repositories whose root license grant was read before
they were measured. The checker does not copy their files into AIC. Re-running
the measurement must check the license file again and stop if the marker is gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class LicenseError(Exception):
    """The comparison tree does not show the expected permissive license."""


@dataclass(frozen=True)
class ComparisonRepo:
    """One third-party repository pinned for a reproducible measurement."""

    name: str
    url: str
    commit: str
    license_id: str
    license_marker: str


COMPARISON_REPOS: tuple[ComparisonRepo, ...] = (
    ComparisonRepo(
        name="obra/superpowers",
        url="https://github.com/obra/superpowers.git",
        commit="22f0b463e7a5e579904dd6211a520321035526f7",
        license_id="MIT",
        license_marker="MIT License",
    ),
    ComparisonRepo(
        name="google/skills",
        url="https://github.com/google/skills.git",
        commit="2194d3b8b1f31975fef2f1a0ae6b9ab55bd7ceee",
        license_id="Apache-2.0",
        license_marker="Apache License",
    ),
    ComparisonRepo(
        name="microsoft/skills",
        url="https://github.com/microsoft/skills.git",
        commit="0696600436a9669184ce47e8d8b2ceac62e4bfac",
        license_id="MIT",
        license_marker="MIT License",
    ),
)

_LICENSE_NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING")


def assert_permissive_license(root: Path, marker: str) -> str:
    """Return the license filename when ``marker`` appears in a regular root license file.

    Symlinked license files are ignored. The marker is a short heading such as
    ``MIT License`` or ``Apache License``, not a copy of the license text.
    """

    for name in _LICENSE_NAMES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise LicenseError(f"Cannot read {path}: {exc.strerror or exc}") from exc
        if marker in text[:8000]:
            return name
    raise LicenseError(f"No root license file containing {marker!r} in {root}.")
