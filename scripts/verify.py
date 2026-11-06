#!/usr/bin/env python3
"""Offline verification. This never starts a model, installer network or service."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.version_info < (3, 11):
        print("AIC verification requires Python 3.11 or newer.", file=sys.stderr)
        return 2
    (ROOT / ".work").mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    print("AIC offline verification: package, installation, routing contracts, privacy, memory and launch dry runs.", flush=True)
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, env=env, check=False)
    if result.returncode:
        return result.returncode
    print("PASS: offline checks. Live discovery, AI quality and operational launches require separately recorded evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
