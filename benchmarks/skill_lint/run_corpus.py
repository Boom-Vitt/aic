"""Clone the pinned comparison repositories and print a skill-lint summary.

The clones stay outside this repository. The script refuses to overwrite an
existing checkout at a different commit. It reads each root license file and
stops before linting a tree whose permissive-license marker is absent.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .corpus import COMPARISON_REPOS, LicenseError, assert_permissive_license
from .discover import LintError
from .lint import lint_path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure pinned skills repositories with skill-lint.")
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("/tmp/aic-skill-lint-corpus"),
        help="Directory outside this repository that will hold the clones.",
    )
    parser.add_argument(
        "--aic",
        type=Path,
        default=_REPO_ROOT,
        help="AIC checkout to measure. Defaults to this repository.",
    )
    args = parser.parse_args(argv)
    destination = args.dest.expanduser()
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    try:
        destination = destination.resolve()
    except OSError as exc:
        print(f"Cannot use destination: {exc}", file=sys.stderr)
        return 2
    repo_root = _REPO_ROOT.resolve()
    if destination == repo_root or repo_root in destination.parents:
        print("Refusing to clone comparison repositories inside the AIC repository.", file=sys.stderr)
        return 2
    records: list[dict[str, object]] = []
    try:
        aic_root = args.aic.resolve()
        aic_record = _measure_local("aic", aic_root)
        aic_record["url"] = "https://github.com/Boom-Vitt/aic"
        aic_record["commit"] = _git(aic_root, "rev-parse", "HEAD").strip()
        aic_record["commit_time"] = _git(aic_root, "log", "-1", "--format=%cI").strip()
        aic_record["license"] = "Apache-2.0"
        aic_record["license_file"] = assert_permissive_license(aic_root, "Apache License")
        records.append(aic_record)
        for spec in COMPARISON_REPOS:
            checkout = destination / spec.name.replace("/", "__")
            _prepare_checkout(checkout, spec.url, spec.commit)
            license_name = assert_permissive_license(checkout, spec.license_marker)
            record = _measure_local(spec.name, checkout)
            record["url"] = spec.url
            record["commit"] = spec.commit
            record["commit_time"] = _git(checkout, "log", "-1", "--format=%cI").strip()
            record["license"] = spec.license_id
            record["license_file"] = license_name
            records.append(record)
    except (LicenseError, LintError, subprocess.CalledProcessError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"repos": records}, indent=2, ensure_ascii=True))
    return 0


def _measure_local(name: str, root: Path) -> dict[str, object]:
    report = lint_path(root)
    payload = report.to_dict(summary=True)
    return {
        "name": name,
        "root": payload["root"],
        "skill_count": payload["skill_count"],
        "format_pass_count": payload["format_pass_count"],
        "format_pass_rate": payload["format_pass_rate"],
        "error_count": payload["error_count"],
        "warning_count": payload["warning_count"],
        "mean_score": payload["mean_score"],
        "rules": payload["rules"],
    }


def _prepare_checkout(dest: Path, url: str, commit: str) -> None:
    if dest.exists():
        if not (dest / ".git").is_dir():
            raise OSError(f"{dest} exists and is not a git checkout.")
        current = _git(dest, "rev-parse", "HEAD").strip()
        if current != commit:
            raise OSError(f"{dest} is {current}, expected {commit}. Refusing to modify it.")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", str(dest)])
    _run(["git", "-C", str(dest), "remote", "add", "origin", url])
    _run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", commit])
    _run(["git", "-C", str(dest), "checkout", "--detach", "FETCH_HEAD"])
    current = _git(dest, "rev-parse", "HEAD").strip()
    if current != commit:
        raise OSError(f"Checkout {dest} resolved to {current}, expected {commit}.")


def _git(dest: Path, *args: str) -> str:
    return _run(["git", "-C", str(dest), *args])


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise subprocess.CalledProcessError(completed.returncode, command, completed.stdout, detail)
    return completed.stdout


if __name__ == "__main__":
    raise SystemExit(main())
