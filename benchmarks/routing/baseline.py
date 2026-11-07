"""Write prompts for a routing pack.

The default pack is the dev fixture, tests/fixtures/routing-scenarios.json.

Prompt generation does not read ANTHROPIC_API_KEY and does not call a model.
The paired model run is ``python -m benchmarks.routing.compare``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmarks.routing.score import (
    EXIT_REFUSED,
    EXIT_USAGE,
    ScoreError,
    default_scenarios_path,
    load_pack,
    read_text,
    repo_root,
    write_exclusive,
)


WITHHELD = (
    "expected_template",
    "expected_topology",
    "expected_workflow",
    "required_invariants",
    "required_milestones",
    "stages",
)


def _catalog_ids(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list or not value:
        raise ScoreError(f"workflow catalog is missing {label}")
    ids: list[str] = []
    for item in value:
        ident = item.get("id") if type(item) is dict else item
        if type(ident) is not str or not ident or any(ord(character) < 32 for character in ident):
            raise ScoreError(f"workflow catalog {label} id is not a string")
        ids.append(ident)
    return tuple(ids)


def load_catalog(root: Path) -> dict[str, tuple[str, ...]]:
    path = root / "skills" / "aic" / "assets" / "workflows.json"
    try:
        body = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise ScoreError(f"workflow catalog is not JSON: {path}") from exc
    if type(body) is not dict:
        raise ScoreError("workflow catalog must be an object")
    topologies = body.get("topologies")
    if type(topologies) is not dict:
        raise ScoreError("workflow catalog is missing topologies")
    return {
        "workflows": _catalog_ids(body.get("workflows"), "workflows"),
        "templates": _catalog_ids(body.get("templates"), "templates"),
        "topologies": _catalog_ids(list(topologies), "topologies"),
    }


def instruction_for(catalog: dict[str, tuple[str, ...]]) -> str:
    return (
        "No-skill baseline. Do not load an AIC skill or any other skill. "
        "Read only this request. Choose one workflow, one template, and one topology "
        "from these ids. "
        f"workflow: {', '.join(catalog['workflows'])}. "
        f"template: {', '.join(catalog['templates'])}. "
        f"topology: {', '.join(catalog['topologies'])}. "
        "Reply with one JSON object whose keys are id, workflow, template, and topology. "
        "Do not execute the request."
    )


def prompt_rows(scenarios: Path) -> list[dict[str, str]]:
    pack = load_pack(scenarios)
    instruction = instruction_for(load_catalog(repo_root()))
    rows = [
        {"id": case.id, "instruction": instruction, "request": case.request}
        for case in pack.cases
    ]
    if pack.project is not None:
        rows.append({"id": pack.project.id, "instruction": instruction, "request": pack.project.request})
    return rows


def render_prompts(rows: list[dict[str, str]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def receipt(path: Path, count: int) -> str:
    body = {
        "arm": "no-skill-baseline",
        "calls_api": False,
        "executed": False,
        "invokes_model": False,
        "ok": True,
        "prompt_count": count,
        "prompts": str(path),
        "skill_loaded": False,
        "withheld": list(WITHHELD),
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks.routing.baseline",
        description="Write routing prompts from a routing pack. Does not call a model or read an API key.",
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        help="Routing pack JSON. Defaults to the dev pack tests/fixtures/routing-scenarios.json.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSONL prompt pack here. Refuses to overwrite.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.output is None:
        print("A prompt pack requires --output.", file=sys.stderr)
        return EXIT_USAGE
    try:
        rows = prompt_rows(args.scenarios if args.scenarios is not None else default_scenarios_path())
        write_exclusive(args.output, render_prompts(rows))
    except ScoreError as exc:
        print(str(exc), file=sys.stderr)
        if exc.code == EXIT_REFUSED:
            return EXIT_USAGE
        return exc.code
    print(receipt(args.output, len(rows)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
