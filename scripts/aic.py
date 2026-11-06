#!/usr/bin/env python3
"""Run the same helper shipped with the portable AIC skill."""
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print("AIC requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(2)
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/aic/scripts"))
from aiclib.cli import main

raise SystemExit(main())
