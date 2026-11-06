#!/usr/bin/env python3
"""Run deterministic helpers from this self-contained installed skill."""
import sys

if sys.version_info < (3, 11):
    print("AIC requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(2)
sys.dont_write_bytecode = True
from aiclib.cli import main

raise SystemExit(main())
