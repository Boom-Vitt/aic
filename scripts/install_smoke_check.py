#!/usr/bin/env python3
"""Check an installed aic hello-world payload and one stdio tools/list call.

The caller supplies the installed interpreter (so the mcp extra is importable),
AIC_BIN, AIC_PROJECT, and AIC_HELLO.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

EXPECTED_TOOLS = [
    "aic_get_guidance",
    "aic_get_workflow_catalog",
    "aic_inspect_project",
    "aic_validate_recommendation",
]


def main() -> int:
    payload = json.loads(Path(os.environ["AIC_HELLO"]).read_text(encoding="utf-8"))
    if (
        payload.get("hello") != "world"
        or payload.get("distribution") != "aiculture-skills"
        or not payload.get("version")
    ):
        print(f"unexpected hello-world payload: {payload}", file=sys.stderr)
        return 1
    bin_dir = Path(os.environ["AIC_BIN"])
    project = Path(os.environ["AIC_PROJECT"])

    async def list_tools() -> list[str]:
        parameters = StdioServerParameters(
            command=str(bin_dir / "aic-mcp"),
            args=["--project", str(project)],
            cwd=str(project),
        )
        async with Client(parameters) as client:
            listed = await client.list_tools()
        return sorted(tool.name for tool in listed.tools)

    names = asyncio.run(list_tools())
    if names != EXPECTED_TOOLS:
        print(f"tools/list returned {names}", file=sys.stderr)
        return 1
    print("hello-world", payload["version"])
    print("tools/list", " ".join(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
