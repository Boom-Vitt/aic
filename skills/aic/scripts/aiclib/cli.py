"""JSON CLI for deterministic helpers, not a standalone inference client."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .safety import AICError, checked_root, safe_path


def _json_file(value: str) -> dict:
    supplied = Path(value).absolute()
    path = safe_path(checked_root(supplied.parent), supplied.name, must_exist=True)
    if not path.is_file() or path.stat().st_size > 1_048_576:
        raise AICError("Input must be a JSON file no larger than 1 MiB.")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except RecursionError as exc:
        raise AICError("Input JSON nesting is too deep.") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AICError("Input is not valid UTF-8 JSON.") from exc
    if not isinstance(result, dict):
        raise AICError("Input must be a JSON object.")
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="AIC local helpers. Your host agent supplies AI reasoning.")
    root.add_argument("--version", action="version", version=f"AIC {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("agents", help="List documented skill discovery adapters.")
    for name in ("install", "uninstall"):
        item = commands.add_parser(name, help=f"{name.capitalize()} only a manifest-owned AIC skill.")
        item.add_argument("--agent", required=True)
        item.add_argument("--scope", choices=("project", "user"), default="project")
        item.add_argument("--project", type=Path)
        item.add_argument("--home", type=Path)
        item.add_argument("--destination", type=Path)
    inspect = commands.add_parser("inspect", help="Read a bounded codebase metadata inventory without executing code.")
    inspect.add_argument("project", type=Path)
    inspect.add_argument("--max-files", type=int, default=200)
    inspect.add_argument("--max-depth", type=int, default=4)
    check = commands.add_parser("check-plan", help="Validate a host-AI-authored recommendation, without executing it.")
    check.add_argument("file")
    check.add_argument("--project", type=Path)
    promote = commands.add_parser("memory-promote", help="Promote a reviewed note after explicit scope approval.")
    promote.add_argument("file")
    promote.add_argument("--project", type=Path, required=True)
    promote.add_argument("--approve", action="store_true")
    read = commands.add_parser("memory-read", help="Read scoped notes as untrusted reference data, with freshness status.")
    read.add_argument("--project", type=Path, required=True)
    handoff = commands.add_parser("check-handoff", help="Validate continuation data without replaying any action.")
    handoff.add_argument("file")
    plan = commands.add_parser("orca-plan", help="Print a non-mutating Orca/omp launch plan and its approval digest.")
    plan.add_argument("file")
    plan.add_argument("--project", type=Path, required=True)
    plan.add_argument("--name", required=True)
    plan.add_argument("--model")
    apply = commands.add_parser("orca-apply", help="Execute only a digest-approved local Orca handoff.")
    apply.add_argument("file")
    apply.add_argument("--approval", required=True)
    apply.add_argument("--orca-binary", default="orca")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "agents":
            path = Path(__file__).resolve().parents[2] / "assets/harnesses.json"
            result = json.loads(path.read_text(encoding="utf-8"))
        elif args.command in ("install", "uninstall"):
            from . import installer
            project = args.project or Path.cwd()
            target = installer.destination(args.agent, args.scope, project=project, home=args.home, destination=args.destination)
            result = installer.install(Path(__file__).resolve().parents[2], target) if args.command == "install" else installer.uninstall(target)
        elif args.command == "inspect":
            from .inspection import inspect_project
            result = inspect_project(checked_root(args.project), max_files=args.max_files, max_depth=args.max_depth)
        elif args.command == "check-plan":
            from .routing import validate_plan
            project = checked_root(args.project) if args.project else None
            result = validate_plan(_json_file(args.file), project=project)
        elif args.command == "memory-promote":
            from .memory import promote
            result = promote(checked_root(args.project), _json_file(args.file), approved=args.approve)
        elif args.command == "memory-read":
            from .memory import read_notes
            result = read_notes(checked_root(args.project))
        elif args.command == "check-handoff":
            from .memory import validate_handoff
            result = validate_handoff(_json_file(args.file))
        elif args.command == "orca-plan":
            from .orca import plan_handoff
            result = plan_handoff(checked_root(args.project, must_exist=False), _json_file(args.file), name=args.name, model=args.model)
        else:
            from .orca import apply_handoff
            result = apply_handoff(_json_file(args.file), approval=args.approval, orca_binary=args.orca_binary)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (AICError, OSError, ValueError) as exc:
        print(f"AIC: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
