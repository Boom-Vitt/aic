"""Console script for the aiculture-skills distribution.

``hello-world`` is the install check. Every other command delegates to the
skill's local helper. The host agent still does the reasoning.
"""
from __future__ import annotations

import json
import sys

from aic.scripts.aiclib import __version__
from aic.scripts.aiclib.cli import main as helper_main
from aic.scripts.aiclib.cli import parser as helper_parser

_HELLO = "hello-world"


def hello_payload() -> dict[str, object]:
    return {
        "hello": "world",
        "distribution": "aiculture-skills",
        "version": __version__,
        "channels": ["skill", "claude-code-plugin", "local-mcp"],
    }


def _print_help(stream) -> None:
    helper_parser().print_help(stream)
    print(
        "\nhello-world\n"
        "    Print the install check as JSON and exit. "
        "This does not read a project, copy the skill, or start the MCP server.",
        file=stream,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == [_HELLO]:
        if args[1:] in (["-h"], ["--help"]):
            print("usage: aic hello-world\n\nPrint the install check as JSON and exit.")
            return 0
        if args[1:]:
            print("AIC: hello-world takes no arguments.", file=sys.stderr)
            return 2
        print(json.dumps(hello_payload(), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    if args[:1] in (["-h"], ["--help"]):
        _print_help(sys.stdout)
        return 0
    if not args:
        _print_help(sys.stderr)
        return 2
    return helper_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
