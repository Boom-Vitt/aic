#!/usr/bin/env python3
"""Pipeline smoke test for the aicbench sandbox. Not a model result."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROBE_NAME = "pipeline-smoke.json"
LABEL = "pipeline smoke test"
TAMPER_BODY = "raise SystemExit('pipeline-smoke-tamper')\n"


def _refuse(message: str) -> int:
    print(f"pipeline smoke test: {message}", file=sys.stderr)
    return 2


def _readable(path: Path) -> bool:
    """True when this process can read the path. File bytes are not returned."""
    try:
        if path.is_symlink():
            return False
        if path.is_dir():
            tuple(path.iterdir())
            return True
        if path.is_file():
            path.read_bytes()
            return True
    except OSError:
        return False
    return False


def _probe() -> int:
    probe_path = Path.cwd() / PROBE_NAME
    try:
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _refuse("probe file is missing.")
    if not isinstance(probe, dict) or probe.get("role") != "pipeline-smoke":
        return _refuse("probe role is not pipeline-smoke.")
    try:
        reference = Path(probe["reference"])
        oracle = Path(probe["oracle"])
    except (KeyError, TypeError):
        return _refuse("probe paths are missing.")
    payload = {
        "api_key_visible": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "label": LABEL,
        "oracle_readable": _readable(oracle),
        "pythonpath_visible": "PYTHONPATH" in os.environ,
        "reference_readable": _readable(reference),
        "role": "pipeline-smoke",
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _tamper(target: Path) -> int:
    if target.is_symlink() or target.is_dir():
        return _refuse("refusing to tamper with that path.")
    target.write_text(TAMPER_BODY, encoding="utf-8")
    return 0


def main() -> int:
    if os.environ.get("AICBENCH_PIPELINE_SMOKE") != "1":
        return _refuse("refusing to run outside the aicbench harness. This is not a model.")
    if len(sys.argv) == 1:
        return _probe()
    if len(sys.argv) == 3 and sys.argv[1] == "tamper":
        return _tamper(Path(sys.argv[2]))
    return _refuse("usage is a probe with no arguments, or tamper PATH.")


if __name__ == "__main__":
    raise SystemExit(main())
