#!/usr/bin/env python3
"""Run the distribution console script from a checkout.

Path setup has to precede the import: this checkout is not installed, and the
console script lives outside the portable skill tree.
"""
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print("AIC requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(2)
sys.dont_write_bytecode = True
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "skills"))
from aic_quickstart.cli import main

raise SystemExit(main())
